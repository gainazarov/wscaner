"""Scanner Engine — the core crawling pipeline with real-time event streaming."""

import asyncio
import logging
import random
import time
from collections import deque
from typing import Any, Callable, Awaitable
from urllib.parse import urljoin, urlparse

import aiohttp

from core.auth_helpers import get_random_ua, get_realistic_headers
from modules.html_module import HTMLModule
from modules.js_module import JSModule
from modules.robots_module import RobotsModule
from modules.sitemap_module import SitemapModule
from modules.bruteforce_module import BruteforceModule
from utils.url_utils import normalize_url, is_same_domain, is_valid_url, extract_domain, is_external

logger = logging.getLogger("scanner.engine")

# Type for the async event callback
EventCallback = Callable[[dict[str, Any]], Awaitable[None]]


async def _noop_callback(event: dict[str, Any]) -> None:
    pass


class ScannerEngine:
    """
    Asynchronous web scanner that discovers URLs using multiple modules.
    Supports real-time progress streaming via an event callback.

    Events emitted:
      - scan_start:      {domain, max_depth, max_pages}
      - phase_start:     {phase, module}
      - phase_complete:  {phase, module, urls_found}
      - phase_error:     {phase, module, error}
      - phase_skip:      {phase, module, reason}
      - url_found:       {url, source, status_code, depth, is_internal, external_domain}
      - crawl_progress:  {visited, total, queue_size}
      - scan_complete:   {total_urls, duration, internal_count, external_count}
      - scan_error:      {error}
    """

    def __init__(
        self,
        domain: str,
        max_depth: int = 3,
        max_pages: int = 500,
        concurrency: int = 5,
        timeout: int = 20,
        on_event: EventCallback | None = None,
        stealth: bool = True,
    ):
        self.domain = domain.strip().lower()
        self.base_url = f"https://{self.domain}"
        self.max_depth = max_depth
        self.max_pages = max_pages
        self.concurrency = concurrency
        self.timeout = aiohttp.ClientTimeout(total=timeout)
        self.on_event = on_event or _noop_callback
        self.stealth = stealth

        # Persistent User-Agent for entire scan session (same browser fingerprint)
        self._ua = get_random_ua()
        self._headers = get_realistic_headers(self._ua)

        self.visited: set[str] = set()
        self.results: list[dict[str, Any]] = []
        self._start_time: float = 0
        self._internal_count: int = 0
        self._external_count: int = 0

        # Initialize modules
        self.modules = [
            HTMLModule(),
            JSModule(),
            RobotsModule(),
            SitemapModule(),
            BruteforceModule(),
        ]

    async def _emit(self, event_type: str, **data: Any) -> None:
        """Emit an event to the callback."""
        try:
            await self.on_event({"type": event_type, **data})
        except Exception as e:
            logger.debug(f"Event callback error: {e}")

    def _classify_url(self, url: str) -> tuple[bool, str]:
        """Classify a URL as internal/external and extract external domain."""
        url_is_internal = not is_external(url, self.domain)
        ext_domain = ""
        if not url_is_internal:
            ext_domain = extract_domain(url)
        return url_is_internal, ext_domain

    async def _get_cf_cookies(self) -> dict[str, str]:
        """
        Use Playwright to visit the site and solve Cloudflare / anti-bot challenges.
        Returns cookies that can be used with aiohttp for subsequent requests.
        """
        cookies = {}
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            logger.debug("Playwright not available for CF bypass")
            return cookies

        pw = None
        browser = None
        try:
            pw = await async_playwright().start()
            browser = await pw.chromium.launch(
                headless=True,
                args=[
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-blink-features=AutomationControlled",
                ],
            )
            context = await browser.new_context(
                user_agent=self._ua,
                viewport={"width": 1920, "height": 1080},
                ignore_https_errors=True,
            )
            # Stealth init script
            await context.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
                delete navigator.__proto__.webdriver;
                window.chrome = {runtime: {id: 'x'}, loadTimes: function(){}, csi: function(){}};
                Object.defineProperty(navigator, 'plugins', {get: () => [{name:'Chrome PDF Plugin'},{name:'Chrome PDF Viewer'},{name:'Native Client'}]});
                Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en', 'ru']});
            """)
            page = await context.new_page()
            logger.info(f"Playwright CF bypass: visiting {self.base_url}")
            await page.goto(self.base_url, timeout=30000, wait_until="domcontentloaded")
            # Wait for CF challenge to resolve (up to 10s)
            await asyncio.sleep(5)
            # Check if we got redirected to a challenge page, wait more
            content = await page.content()
            if "challenge" in content.lower() or "checking" in content.lower():
                logger.info("CF challenge detected, waiting for resolution...")
                await asyncio.sleep(8)
            # Extract cookies
            all_cookies = await context.cookies()
            for c in all_cookies:
                if c.get("domain", "").replace(".", "").endswith(self.domain.replace(".", "")):
                    cookies[c["name"]] = c["value"]
            logger.info(f"CF bypass: got {len(cookies)} cookies: {list(cookies.keys())}")
        except Exception as e:
            logger.warning(f"CF cookie bypass failed: {e}")
        finally:
            try:
                if browser:
                    await browser.close()
            except Exception:
                pass
            try:
                if pw:
                    await pw.stop()
            except Exception:
                pass
        return cookies

    async def run(self) -> list[dict[str, Any]]:
        """Execute the full scanning pipeline."""
        self._start_time = time.time()
        await self._emit("scan_start", domain=self.domain, max_depth=self.max_depth, max_pages=self.max_pages)
        logger.info(f"Starting scan: {self.domain} (depth={self.max_depth}, max_pages={self.max_pages})")

        connector = aiohttp.TCPConnector(limit=self.concurrency, ssl=False)
        jar = aiohttp.CookieJar(unsafe=True)  # Accept cookies like a real browser
        try:
            async with aiohttp.ClientSession(
                connector=connector,
                timeout=self.timeout,
                headers=self._headers,
                cookie_jar=jar,
            ) as session:
                # Pre-flight: check if site has anti-bot protection
                if self.stealth:
                    try:
                        async with session.get(self.base_url, allow_redirects=True) as resp:
                            pre_status = resp.status
                            pre_body = await resp.text(errors="replace")
                            has_protection = (
                                pre_status == 403
                                or pre_status == 503
                                or "cf-browser-verification" in pre_body.lower()
                                or "challenge-platform" in pre_body.lower()
                                or "just a moment" in pre_body.lower()
                                or "_cf_chl" in pre_body.lower()
                                or "ddos-guard" in pre_body.lower()
                                or len(pre_body) < 1000 and pre_status != 200
                            )
                            if has_protection:
                                logger.info(f"Anti-bot protection detected (status={pre_status}), using Playwright bypass...")
                                await self._emit("phase_start", phase="anti_bot_bypass", module="Stealth Browser")
                                cf_cookies = await self._get_cf_cookies()
                                if cf_cookies:
                                    # Inject cookies into aiohttp session
                                    for name, value in cf_cookies.items():
                                        jar.update_cookies({name: value})
                                    logger.info(f"Injected {len(cf_cookies)} bypass cookies into session")
                                await self._emit("phase_complete", phase="anti_bot_bypass", module="Stealth Browser", urls_found=0)
                    except Exception as e:
                        logger.debug(f"Pre-flight check failed: {e}")

                # Phase 1-3: Run special modules one-by-one so we can stream progress
                await self._run_single_special_module(session, "robots", RobotsModule)
                await self._run_single_special_module(session, "sitemap", SitemapModule)
                await self._run_single_special_module(session, "bruteforce", BruteforceModule)

                # Phase 4: BFS crawling
                await self._emit("phase_start", phase="crawl", module="HTML + JS Crawler")
                await self._bfs_crawl(session)
                await self._emit("phase_complete", phase="crawl", module="HTML + JS Crawler", urls_found=len(self.results))

                # Phase 5: Playwright browser crawl (behavior-driven)
                # Run when aiohttp found few URLs (anti-bot blocked most requests)
                if self.stealth:
                    aiohttp_count = len(self.results)
                    if aiohttp_count < 50:
                        logger.info(f"Running Playwright browser crawl (aiohttp found {aiohttp_count} URLs)...")
                        await self._emit("phase_start", phase="browser_crawl", module="Behavior-Driven Browser Scanner")
                        browser_urls = await self._playwright_crawl()
                        new_found = 0
                        for url_info in browser_urls:
                            url = url_info.get("url", "")
                            if url and url not in self.visited:
                                self.visited.add(url)
                                url_is_internal, ext_domain = self._classify_url(url)
                                url_info["is_internal"] = url_is_internal
                                url_info["external_domain"] = ext_domain
                                if url_is_internal:
                                    self._internal_count += 1
                                else:
                                    self._external_count += 1
                                self.results.append(url_info)
                                new_found += 1
                                await self._emit("url_found",
                                    url=url, source="browser",
                                    status_code=url_info.get("status_code"),
                                    depth=url_info.get("depth", 0),
                                    is_internal=url_is_internal,
                                    external_domain=ext_domain,
                                )
                        await self._emit("phase_complete", phase="browser_crawl",
                            module="Behavior-Driven Browser Scanner", urls_found=new_found)
                    else:
                        logger.info(f"aiohttp found {aiohttp_count} URLs, skipping browser crawl")
        except Exception as e:
            await self._emit("scan_error", error=str(e))
            raise

        duration = round(time.time() - self._start_time, 2)
        await self._emit(
            "scan_complete",
            total_urls=len(self.results),
            duration=duration,
            internal_count=self._internal_count,
            external_count=self._external_count,
        )
        logger.info(f"Scan complete: {len(self.results)} URLs discovered in {duration}s "
                    f"({self._internal_count} internal, {self._external_count} external)")
        return self.results

    async def _run_single_special_module(
        self, session: aiohttp.ClientSession, phase_name: str, module_class: type
    ):
        """Run a single special module with event tracking."""
        module = None
        for m in self.modules:
            if isinstance(m, module_class):
                module = m
                break

        if not module:
            await self._emit("phase_skip", phase=phase_name, module=phase_name, reason="Module not found")
            return

        module_name = module.__class__.__name__
        await self._emit("phase_start", phase=phase_name, module=module_name)

        try:
            results = await module.run(self.base_url, session, self.domain)
            found_count = 0
            if isinstance(results, list):
                for url_info in results:
                    url = url_info.get("url", "")
                    if url and url not in self.visited:
                        self.visited.add(url)
                        # Classify internal/external
                        url_is_internal, ext_domain = self._classify_url(url)
                        url_info["is_internal"] = url_is_internal
                        url_info["external_domain"] = ext_domain
                        if url_is_internal:
                            self._internal_count += 1
                        else:
                            self._external_count += 1
                        self.results.append(url_info)
                        found_count += 1
                        await self._emit("url_found",
                            url=url_info.get("url", ""),
                            source=url_info.get("source", phase_name),
                            status_code=url_info.get("status_code"),
                            depth=url_info.get("depth", 0),
                            is_internal=url_is_internal,
                            external_domain=ext_domain,
                        )
            await self._emit("phase_complete", phase=phase_name, module=module_name, urls_found=found_count)
        except Exception as e:
            logger.warning(f"Module {module_name} failed: {e}")
            await self._emit("phase_error", phase=phase_name, module=module_name, error=str(e))

    async def _bfs_crawl(self, session: aiohttp.ClientSession):
        """BFS crawl starting from base URL."""
        queue: deque[tuple[str, int]] = deque()
        queue.append((self.base_url, 0))

        # Also try http variant
        http_url = f"http://{self.domain}"
        queue.append((http_url, 0))

        page_modules = [
            m for m in self.modules if isinstance(m, (HTMLModule, JSModule))
        ]

        while queue and len(self.results) < self.max_pages:
            # Process batch
            batch: list[tuple[str, int]] = []
            while queue and len(batch) < self.concurrency:
                url, depth = queue.popleft()
                normalized = normalize_url(url)

                if normalized in self.visited:
                    continue
                if depth > self.max_depth:
                    continue
                if not is_valid_url(normalized):
                    continue

                self.visited.add(normalized)
                batch.append((normalized, depth))

            if not batch:
                break

            # Emit crawl progress
            await self._emit("crawl_progress",
                visited=len(self.visited),
                total=len(self.results),
                queue_size=len(queue),
            )

            # Random delay between batches to avoid bot detection
            if self.stealth:
                await asyncio.sleep(random.uniform(0.5, 2.0))

            # Fetch all pages in batch concurrently
            tasks = [
                self._fetch_and_extract(session, url, depth, page_modules)
                for url, depth in batch
            ]
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)

            for result in batch_results:
                if isinstance(result, Exception):
                    logger.debug(f"Fetch error: {result}")
                    continue
                if result is None:
                    continue

                url_info, new_links = result

                # Classify internal/external
                url_is_internal, ext_domain = self._classify_url(url_info["url"])
                url_info["is_internal"] = url_is_internal
                url_info["external_domain"] = ext_domain
                if url_is_internal:
                    self._internal_count += 1
                else:
                    self._external_count += 1

                # Add this URL to results
                if len(self.results) < self.max_pages:
                    self.results.append(url_info)
                    await self._emit("url_found",
                        url=url_info.get("url", ""),
                        source=url_info.get("source", "html"),
                        status_code=url_info.get("status_code"),
                        depth=url_info.get("depth", 0),
                        is_internal=url_is_internal,
                        external_domain=ext_domain,
                    )

                # Add discovered links to queue (only internal ones for crawling)
                for link in new_links:
                    normalized_link = normalize_url(link)
                    if (
                        normalized_link not in self.visited
                        and is_valid_url(normalized_link)
                        and len(self.results) < self.max_pages
                    ):
                        link_is_internal = not is_external(normalized_link, self.domain)
                        if link_is_internal:
                            new_depth = url_info["depth"] + 1
                            if new_depth <= self.max_depth:
                                queue.append((normalized_link, new_depth))
                        else:
                            # Still record external links as discovered
                            if normalized_link not in self.visited:
                                self.visited.add(normalized_link)
                                ext_dom = extract_domain(normalized_link)
                                ext_info = {
                                    "url": normalized_link,
                                    "source": url_info.get("source", "html"),
                                    "status_code": None,
                                    "content_type": "",
                                    "depth": url_info["depth"] + 1,
                                    "is_internal": False,
                                    "external_domain": ext_dom,
                                    "source_url": url_info.get("url", ""),
                                }
                                self._external_count += 1
                                if len(self.results) < self.max_pages:
                                    self.results.append(ext_info)
                                    await self._emit("url_found",
                                        url=normalized_link,
                                        source=url_info.get("source", "html"),
                                        status_code=None,
                                        depth=url_info["depth"] + 1,
                                        is_internal=False,
                                        external_domain=ext_dom,
                                        source_url=url_info.get("url", ""),
                                    )

    async def _fetch_and_extract(
        self,
        session: aiohttp.ClientSession,
        url: str,
        depth: int,
        modules: list,
    ) -> tuple[dict, list[str]] | None:
        """Fetch a URL and extract links using modules."""
        # Small random delay per request for stealth
        if self.stealth:
            await asyncio.sleep(random.uniform(0.1, 0.5))

        # Add Referer header (looks like real browsing)
        extra_headers = {}
        if depth > 0:
            extra_headers["Referer"] = self.base_url + "/"

        max_retries = 2
        for attempt in range(max_retries):
            try:
                async with session.get(url, allow_redirects=True, headers=extra_headers) as response:
                    status_code = response.status
                    content_type = response.headers.get("Content-Type", "")
                    html = ""

                    # Handle Cloudflare / anti-bot challenge pages
                    if status_code == 403 and attempt < max_retries - 1:
                        logger.debug(f"Got 403 on {url}, retrying after delay...")
                        await asyncio.sleep(random.uniform(2.0, 5.0))
                        continue

                    if status_code == 429:  # Rate limited
                        retry_after = int(response.headers.get("Retry-After", "5"))
                        logger.debug(f"Rate limited on {url}, waiting {retry_after}s")
                        await asyncio.sleep(min(retry_after, 30))
                        if attempt < max_retries - 1:
                            continue

                    if "text/html" in content_type:
                        html = await response.text(errors="replace")
                    elif "javascript" in content_type or "application/json" in content_type:
                        html = await response.text(errors="replace")

                    url_info = {
                        "url": str(response.url),
                        "source": "html",
                        "status_code": status_code,
                        "content_type": content_type.split(";")[0].strip(),
                        "depth": depth,
                        "is_internal": is_same_domain(str(response.url), self.domain),
                        "external_domain": "",
                    }

                    # Extract links
                    all_links: list[str] = []
                    for module in modules:
                        try:
                            links = module.extract(str(response.url), html, self.domain)
                            all_links.extend(links)
                        except Exception as e:
                            logger.debug(f"Module {module.__class__.__name__} error on {url}: {e}")

                    return url_info, all_links

            except asyncio.TimeoutError:
                if attempt < max_retries - 1:
                    logger.debug(f"Timeout on {url}, retrying...")
                    await asyncio.sleep(random.uniform(1.0, 3.0))
                    continue
                logger.debug(f"Timeout: {url}")
                return {
                    "url": url,
                    "source": "html",
                    "status_code": 0,
                    "content_type": "",
                    "depth": depth,
                    "is_internal": is_same_domain(url, self.domain),
                    "external_domain": "",
                }, []
            except Exception as e:
                logger.debug(f"Error fetching {url}: {e}")
                return None

        return None

    async def _playwright_crawl(self) -> list[dict[str, Any]]:
        """
        Behavior-driven Playwright crawl for sites with anti-bot protection.
        Uses a real browser with:
          - Action-based clicking (buttons, [role=button], div[onclick], etc.)
          - Navigation detection (URL change + DOM hash)
          - BFS queue through browser
          - Click deduplication
          - Network capture with source page mapping
          - Smart wait for SPA rendering
          - Retry logic for navigation and clicks
        """
        results = []
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            logger.debug("Playwright not available for browser crawl")
            return results

        pw = None
        browser = None

        # ── State ──
        visited_urls: set[str] = set()
        visited_actions: set[tuple[str, str]] = set()  # (page_url, selector) dedup
        api_endpoints: dict[str, str] = {}  # api_url -> found_on_page
        page_hashes: set[str] = set()  # DOM fingerprints for dedup
        bfs_queue: deque[tuple[str, int, str]] = deque()  # (url, depth, found_on)
        total_clicks = 0

        # ── Clickable selectors (priority ordered) ──
        CLICK_SELECTORS = [
            # Navigation
            "nav a", "header a", "[role='navigation'] a",
            ".sidebar a", ".menu a", ".nav a",
            # Buttons
            "nav button", "header button", "[role='navigation'] button",
            ".sidebar button",
            # ARIA roles
            "[role='button']", "[role='tab']", "[role='menuitem']",
            "[role='link']",
            # Interactive elements
            "[data-toggle]", "[aria-expanded]",
            "div[onclick]", "span[onclick]", "li[onclick]",
            "[data-href]", "[data-url]", "[data-link]",
            # Menu / nav classes
            ".menu-item", ".nav-item", ".nav-link",
            "a[class*='menu']", "a[class*='nav']",
            "button[class*='menu']", "button[class*='nav']",
            # User-area (critical for 1xbet-like sites)
            "[class*='user'] a", "[class*='avatar'] a",
            "[class*='account'] a", "[class*='profile'] a",
            "[class*='cabinet'] a", "[class*='balance']",
            "[class*='deposit']", "[class*='sport']",
            "[class*='casino']", "[class*='live']",
            "[class*='promo']", "[class*='bonus']",
            # Footer links
            "footer a",
        ]

        async def _get_dom_hash(page) -> str:
            """Get a fast DOM fingerprint for change detection."""
            try:
                return await page.evaluate("""() => {
                    const el = document.querySelector('main, #app, #root, [role=main], .content, body');
                    if (!el) return '';
                    const text = el.innerText || '';
                    const links = document.querySelectorAll('a').length;
                    const inputs = document.querySelectorAll('input').length;
                    return text.substring(0, 500).replace(/\\s+/g, ' ') + '|L' + links + '|I' + inputs;
                }""")
            except Exception:
                return ""

        async def _smart_wait_page(page, timeout_s=8):
            """Wait for SPA content to render — body, containers, network settle."""
            try:
                await page.wait_for_load_state("domcontentloaded", timeout=timeout_s * 1000)
            except Exception:
                pass
            # Wait for any main container
            for sel in ["main", "#app", "#root", "#__next", "[role='main']", ".content"]:
                try:
                    await page.wait_for_selector(sel, timeout=2000, state="attached")
                    break
                except Exception:
                    continue
            # Let JS render
            await asyncio.sleep(1.5)
            # Scroll to trigger lazy loading
            try:
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight / 3)")
                await asyncio.sleep(0.5)
                await page.evaluate("window.scrollTo(0, 0)")
            except Exception:
                pass

        async def _goto_with_retry(page, url, retries=3):
            """Navigate with retry logic."""
            for attempt in range(retries):
                try:
                    resp = await page.goto(url, timeout=20000, wait_until="domcontentloaded")
                    return resp
                except Exception as e:
                    if attempt < retries - 1:
                        logger.debug(f"Goto retry {attempt+1}/{retries} for {url}: {e}")
                        await asyncio.sleep(random.uniform(1, 3))
                    else:
                        # Last attempt: try with 'commit' (less strict)
                        try:
                            resp = await page.goto(url, timeout=15000, wait_until="commit")
                            return resp
                        except Exception:
                            logger.debug(f"Goto failed completely for {url}")
                            return None

        async def _extract_all_links(page, domain) -> set[str]:
            """Extract links from DOM: a[href], button hrefs, data-*, onclick, router, window.location."""
            try:
                raw_urls = await page.evaluate("""() => {
                    const urls = new Set();

                    // Standard <a href>
                    document.querySelectorAll('a[href]').forEach(el => {
                        const href = el.getAttribute('href');
                        if (href && href.trim() && !href.startsWith('#') &&
                            !href.startsWith('javascript:') && !href.startsWith('mailto:') &&
                            !href.startsWith('tel:') && !href.startsWith('data:')) {
                            urls.add(href.trim());
                        }
                    });

                    // SPA framework attrs
                    ['data-href', 'routerlink', 'ng-href', 'to', 'data-url',
                     'data-link', 'data-route', 'data-path', 'data-navigate'].forEach(attr => {
                        document.querySelectorAll('[' + attr + ']').forEach(el => {
                            const val = el.getAttribute(attr);
                            if (val && val.trim()) urls.add(val.trim());
                        });
                    });

                    // [role=link] with data attributes
                    document.querySelectorAll('[role="link"]').forEach(el => {
                        for (const attr of el.attributes) {
                            if (attr.value && attr.value.startsWith('/') && attr.value.length > 1) {
                                urls.add(attr.value);
                            }
                        }
                    });

                    // onclick with URLs
                    document.querySelectorAll('[onclick]').forEach(el => {
                        const onclick = el.getAttribute('onclick') || '';
                        const m = onclick.match(/['\"](\\/[a-zA-Z][a-zA-Z0-9_\\/-]*)['\"]|location[\\s.]*(?:href)?[\\s]*=[\\s]*['\"]([^'\"]+)['\"]/g);
                        if (m) m.forEach(match => {
                            const url = match.replace(/.*['\"]([^'\"]+)['\"].*/, '$1');
                            if (url.startsWith('/') || url.startsWith('http')) urls.add(url);
                        });
                    });

                    // window.__NEXT_DATA__
                    try {
                        if (window.__NEXT_DATA__) {
                            const s = JSON.stringify(window.__NEXT_DATA__);
                            (s.match(/"href":"([^"]+)"/g) || []).forEach(m => {
                                const url = m.replace(/"href":"([^"]+)"/, '$1');
                                if (url.startsWith('/')) urls.add(url);
                            });
                        }
                    } catch(e) {}

                    // Route patterns in inline scripts
                    try {
                        document.querySelectorAll('script:not([src])').forEach(script => {
                            const text = script.textContent || '';
                            if (text.length > 500000) return;
                            // Path-like strings
                            const paths = text.match(/['\"\\/]((?:dashboard|account|profile|settings|cabinet|wallet|history|bonus|deposit|withdraw|personal|balance|transactions|notifications|cashier|my|favorites|live|prematch|casino|games|sport|esport|virtual|poker|lottery|slots|promotions|vip|help|faq|contact|about|terms|rules|support)[a-zA-Z0-9_\\/-]*)['\"\\/]/gi);
                            if (paths) paths.forEach(m => {
                                const url = m.replace(/^['\"\\//]|['\"\\//]$/g, '');
                                if (url && !url.includes(' ')) urls.add('/' + url.replace(/^\\//, ''));
                            });
                            // Router definitions
                            const routerPaths = text.match(/path\\s*:\\s*['\"](\\/[^'\"]+)['\"]/g);
                            if (routerPaths) routerPaths.forEach(m => {
                                const url = m.replace(/path\\s*:\\s*['\"]([^'\"]+)['\"]/, '$1');
                                if (url.startsWith('/')) urls.add(url);
                            });
                        });
                    } catch(e) {}

                    return Array.from(urls);
                }""")

                links = set()
                base_url = page.url
                for raw in raw_urls:
                    try:
                        if raw.startswith("//"):
                            raw = "https:" + raw
                        elif raw.startswith("/"):
                            raw = urljoin(base_url, raw)
                        elif not raw.startswith("http"):
                            raw = urljoin(base_url, raw)
                        normalized = normalize_url(raw)
                        if normalized and is_valid_url(normalized):
                            links.add(normalized)
                    except Exception:
                        continue
                return links
            except Exception as e:
                logger.debug(f"Link extraction error: {e}")
                return set()

        async def _click_interactive_elements(page, domain, current_depth):
            """Click buttons, [role=button], etc. and detect new pages via URL + DOM change."""
            nonlocal total_clicks
            discovered = set()
            page_url = normalize_url(page.url) or page.url

            for selector in CLICK_SELECTORS:
                try:
                    elements = await page.query_selector_all(selector)
                except Exception:
                    continue

                for el in elements[:5]:
                    if total_clicks >= 100:  # Global click limit
                        return discovered
                    try:
                        is_visible = await el.is_visible()
                        if not is_visible:
                            continue

                        # Get element identifier for dedup
                        el_id = ""
                        try:
                            el_id = await page.evaluate("""(el) => {
                                const tag = el.tagName.toLowerCase();
                                const text = (el.textContent || '').trim().substring(0, 50);
                                const href = el.getAttribute('href') || '';
                                const cls = (el.className || '').toString().trim().substring(0, 50);
                                return tag + '|' + text + '|' + href + '|' + cls;
                            }""", el)
                        except Exception:
                            el_id = selector

                        dedup_key = (page_url, el_id)
                        if dedup_key in visited_actions:
                            continue
                        visited_actions.add(dedup_key)

                        # For <a> with href: just collect, don't click
                        href = await el.get_attribute("href")
                        if href:
                            try:
                                resolved = normalize_url(urljoin(page.url, href))
                                if resolved and is_valid_url(resolved) and not is_external(resolved, domain):
                                    if resolved not in visited_urls:
                                        discovered.add(resolved)
                            except Exception:
                                pass
                            continue  # Don't click links — just queue them

                        # For non-link elements: click and detect navigation
                        before_url = page.url
                        before_dom = await _get_dom_hash(page)

                        try:
                            await el.click(timeout=3000, force=False)
                            total_clicks += 1
                            await self._emit("browser_click",
                                selector=selector, page=page_url,
                                element=el_id[:80], clicks_total=total_clicks)
                        except Exception:
                            continue

                        await asyncio.sleep(random.uniform(0.8, 1.5))

                        # ── Navigation detection ──
                        after_url = page.url
                        after_dom = await _get_dom_hash(page)

                        url_changed = normalize_url(after_url) != normalize_url(before_url)
                        dom_changed = after_dom != before_dom and len(after_dom) > 10

                        if url_changed:
                            new_url = normalize_url(after_url)
                            if new_url and not is_external(new_url, domain):
                                if new_url not in visited_urls:
                                    discovered.add(new_url)
                                    await self._emit("browser_nav",
                                        url=new_url, source="click",
                                        trigger=el_id[:80])
                                    logger.debug(f"Click→Nav: {new_url}")

                            # Go back
                            try:
                                await page.go_back(timeout=10000, wait_until="domcontentloaded")
                                await asyncio.sleep(0.5)
                            except Exception:
                                try:
                                    await _goto_with_retry(page, page_url)
                                    await _smart_wait_page(page)
                                except Exception:
                                    break

                        elif dom_changed:
                            # DOM changed but URL didn't — SPA route or modal
                            # Extract new links from changed DOM
                            new_links = await _extract_all_links(page, domain)
                            for link in new_links:
                                if link not in visited_urls and not is_external(link, domain):
                                    discovered.add(link)

                    except Exception:
                        continue

            return discovered

        try:
            pw = await async_playwright().start()
            browser = await pw.chromium.launch(
                headless=True,
                args=[
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-blink-features=AutomationControlled",
                ],
            )
            context = await browser.new_context(
                user_agent=self._ua,
                viewport={"width": 1920, "height": 1080},
                ignore_https_errors=True,
            )
            # Stealth
            await context.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
                delete navigator.__proto__.webdriver;
                window.chrome = {runtime: {id: 'x'}, loadTimes: function(){return {};}, csi: function(){return {};}};
                Object.defineProperty(navigator, 'plugins', {get: () => [{name:'Chrome PDF Plugin'},{name:'Chrome PDF Viewer'},{name:'Native Client'}]});
                Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en', 'ru']});
                Object.defineProperty(navigator, 'platform', {get: () => 'Win32'});
                Object.defineProperty(navigator, 'hardwareConcurrency', {get: () => 8});
                Object.defineProperty(navigator, 'deviceMemory', {get: () => 8});
                const gp = WebGLRenderingContext.prototype.getParameter;
                WebGLRenderingContext.prototype.getParameter = function(p) {
                    if (p === 37445) return 'Google Inc. (NVIDIA)';
                    if (p === 37446) return 'ANGLE (NVIDIA, NVIDIA GeForce GTX 1650)';
                    return gp.call(this, p);
                };
            """)
            page = await context.new_page()

            # ── Network capture with source mapping ──
            current_page_url = [self.base_url]  # mutable ref for closure

            def on_request(req):
                try:
                    if req.resource_type in ("xhr", "fetch"):
                        url = normalize_url(req.url)
                        if url and is_valid_url(url):
                            if url not in api_endpoints:
                                api_endpoints[url] = current_page_url[0]
                                logger.debug(f"API: {req.method} {url} (from {current_page_url[0]})")
                except Exception:
                    pass

            def on_response(resp):
                try:
                    if resp.request.resource_type in ("xhr", "fetch"):
                        url = normalize_url(resp.url)
                        if url and is_valid_url(url) and url not in api_endpoints:
                            api_endpoints[url] = current_page_url[0]
                except Exception:
                    pass

            page.on("request", on_request)
            page.on("response", on_response)

            # ── Visit main page ──
            logger.info(f"Browser crawl: visiting {self.base_url}")
            await self._emit("browser_crawl_start", domain=self.domain, mode="behavior_driven")

            resp = await _goto_with_retry(page, self.base_url)
            if not resp:
                return results
            await _smart_wait_page(page)

            start_url_norm = normalize_url(page.url) or normalize_url(self.base_url)
            visited_urls.add(start_url_norm)
            dom_hash = await _get_dom_hash(page)
            if dom_hash:
                page_hashes.add(dom_hash[:200])

            results.append({
                "url": start_url_norm,
                "source": "browser",
                "status_code": resp.status if resp else 0,
                "content_type": "text/html",
                "depth": 0,
                "found_on": "",
            })

            await self._emit("browser_page_visited",
                url=start_url_norm, depth=0, pages_total=1, queue_size=0)

            # ── Extract links from start page ──
            initial_links = await _extract_all_links(page, self.domain)
            # Also extract from HTML using our modules
            try:
                html = await page.content()
                for module in self.modules:
                    if isinstance(module, (HTMLModule, JSModule)):
                        try:
                            module_links = module.extract(self.base_url, html, self.domain)
                            for l in module_links:
                                nl = normalize_url(l)
                                if nl and is_valid_url(nl):
                                    initial_links.add(nl)
                        except Exception:
                            pass
            except Exception:
                pass

            for link in initial_links:
                if link not in visited_urls and not is_external(link, self.domain):
                    bfs_queue.append((link, 1, start_url_norm))

            # ── Click interactive elements on start page ──
            click_discovered = await _click_interactive_elements(page, self.domain, 0)
            for url in click_discovered:
                if url not in visited_urls:
                    bfs_queue.append((url, 1, start_url_norm))

            logger.info(f"Start page: {len(initial_links)} links, {len(click_discovered)} from clicks, queue={len(bfs_queue)}")

            await self._emit("browser_progress",
                pages_visited=1, queue_size=len(bfs_queue),
                urls_found=len(results), api_found=len(api_endpoints),
                clicks=total_clicks,
                message=f"Queue: {len(bfs_queue)} URLs after start page")

            # ── BFS crawl loop ──
            pages_visited = 1
            scan_start = time.time()
            max_time = 300  # 5 min max for browser crawl

            while bfs_queue and pages_visited < self.max_pages:
                if time.time() - scan_start > max_time:
                    logger.info("Browser crawl: time limit reached")
                    break

                url, depth, found_on = bfs_queue.popleft()
                if depth > self.max_depth:
                    continue

                normalized = normalize_url(url)
                if not normalized or normalized in visited_urls:
                    continue

                visited_urls.add(normalized)
                current_page_url[0] = normalized
                pages_visited += 1

                # Random delay
                await asyncio.sleep(random.uniform(0.5, 1.5))

                # Navigate with retry
                resp = await _goto_with_retry(page, normalized)
                if not resp:
                    continue

                await _smart_wait_page(page)

                actual_url = normalize_url(page.url) or normalized
                visited_urls.add(actual_url)

                # Page fingerprint for dedup
                dom_hash = await _get_dom_hash(page)
                dom_key = dom_hash[:200] if dom_hash else ""
                if dom_key and dom_key in page_hashes:
                    logger.debug(f"Duplicate page content: {actual_url}")
                    continue  # Same content as another page
                if dom_key:
                    page_hashes.add(dom_key)

                results.append({
                    "url": actual_url,
                    "source": "browser",
                    "status_code": resp.status if resp else 0,
                    "content_type": "text/html",
                    "depth": depth,
                    "found_on": found_on,
                })

                await self._emit("browser_page_visited",
                    url=actual_url, depth=depth,
                    pages_total=pages_visited, queue_size=len(bfs_queue))

                # Extract links
                page_links = await _extract_all_links(page, self.domain)
                new_count = 0
                for link in page_links:
                    if link not in visited_urls:
                        if not is_external(link, self.domain):
                            bfs_queue.append((link, depth + 1, actual_url))
                            new_count += 1
                        else:
                            # Record external link
                            ext_dom = extract_domain(link)
                            if link not in visited_urls:
                                visited_urls.add(link)
                                results.append({
                                    "url": link,
                                    "source": "browser",
                                    "status_code": None,
                                    "content_type": "",
                                    "depth": depth + 1,
                                    "found_on": actual_url,
                                    "is_internal": False,
                                    "external_domain": ext_dom,
                                })

                # Click interactive elements (less aggressive on deeper pages)
                if depth <= 2:
                    max_cl = 15 if depth == 0 else 8
                    click_disc = await _click_interactive_elements(page, self.domain, depth)
                    for cu in click_disc:
                        if cu not in visited_urls:
                            bfs_queue.append((cu, depth + 1, actual_url))

                await self._emit("browser_progress",
                    pages_visited=pages_visited, queue_size=len(bfs_queue),
                    urls_found=len(results), api_found=len(api_endpoints),
                    clicks=total_clicks,
                    message=f"Page {pages_visited}: +{new_count} links")

            # ── Add API endpoints ──
            for api_url, source_page in api_endpoints.items():
                if api_url not in {r["url"] for r in results}:
                    results.append({
                        "url": api_url,
                        "source": "browser_api",
                        "status_code": None,
                        "content_type": "",
                        "depth": 0,
                        "found_on": source_page,
                    })
                    await self._emit("browser_api_found",
                        url=api_url, found_on=source_page)

            elapsed = time.time() - scan_start
            logger.info(
                f"Browser crawl complete: {pages_visited} pages, {len(results)} URLs, "
                f"{len(api_endpoints)} APIs, {total_clicks} clicks in {elapsed:.1f}s"
            )
            await self._emit("browser_crawl_complete",
                pages_visited=pages_visited, total_urls=len(results),
                api_endpoints=len(api_endpoints), clicks=total_clicks,
                duration=round(elapsed, 1))

        except Exception as e:
            logger.error(f"Browser crawl failed: {e}", exc_info=True)
        finally:
            try:
                if browser:
                    await browser.close()
            except Exception:
                pass
            try:
                if pw:
                    await pw.stop()
            except Exception:
                pass

        return results
