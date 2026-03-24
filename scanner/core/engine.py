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

                # Phase 5: If aiohttp found very few URLs, try Playwright browser crawl
                if self.stealth and len(self.results) < 10:
                    logger.info(f"Only {len(self.results)} URLs found with aiohttp, trying Playwright browser crawl...")
                    await self._emit("phase_start", phase="browser_crawl", module="Stealth Browser Crawler")
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
                    await self._emit("phase_complete", phase="browser_crawl", module="Stealth Browser Crawler", urls_found=new_found)
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
        Fallback Playwright-based crawl for sites with heavy anti-bot protection.
        Uses a real browser to render pages and extract links via DOM.
        """
        results = []
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            logger.debug("Playwright not available for browser crawl")
            return results

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
            # Stealth
            await context.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
                delete navigator.__proto__.webdriver;
                window.chrome = {runtime: {id: 'x'}, loadTimes: function(){}, csi: function(){}};
                Object.defineProperty(navigator, 'plugins', {get: () => [{name:'Chrome PDF Plugin'},{name:'Chrome PDF Viewer'},{name:'Native Client'}]});
                Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en', 'ru']});
                Object.defineProperty(navigator, 'platform', {get: () => 'Win32'});
            """)
            page = await context.new_page()

            # Capture XHR/fetch API calls
            api_urls = set()
            def on_request(req):
                if req.resource_type in ("xhr", "fetch"):
                    url = normalize_url(req.url)
                    if url and is_valid_url(url):
                        api_urls.add(url)
            page.on("request", on_request)

            # Visit main page
            logger.info(f"Playwright crawl: visiting {self.base_url}")
            try:
                resp = await page.goto(self.base_url, timeout=30000, wait_until="domcontentloaded")
                status = resp.status if resp else 0
            except Exception as e:
                logger.warning(f"Playwright crawl: initial navigation failed: {e}")
                return results

            # Wait for JS rendering
            await asyncio.sleep(3)

            # Scroll to trigger lazy loading
            try:
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight / 2)")
                await asyncio.sleep(1)
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await asyncio.sleep(1)
                await page.evaluate("window.scrollTo(0, 0)")
            except Exception:
                pass

            # Extract all links from DOM
            links = await page.evaluate("""() => {
                const urls = new Set();
                document.querySelectorAll('a[href]').forEach(el => {
                    const href = el.getAttribute('href');
                    if (href && href.trim() && !href.startsWith('#') && 
                        !href.startsWith('javascript:') && !href.startsWith('mailto:')) {
                        urls.add(href.trim());
                    }
                });
                // Also check for data-href, ng-href, routerLink etc.
                ['data-href', 'routerlink', 'ng-href'].forEach(attr => {
                    document.querySelectorAll('[' + attr + ']').forEach(el => {
                        const val = el.getAttribute(attr);
                        if (val && val.trim()) urls.add(val.trim());
                    });
                });
                return Array.from(urls);
            }""")

            logger.info(f"Playwright crawl: found {len(links)} raw links on main page")

            # Also extract links from page HTML (using our modules)
            html = await page.content()
            for module in self.modules:
                if isinstance(module, (HTMLModule, JSModule)):
                    try:
                        module_links = module.extract(self.base_url, html, self.domain)
                        links.extend(module_links)
                    except Exception:
                        pass

            # Process all discovered links
            seen = set()
            for link in links:
                try:
                    if link.startswith("//"):
                        link = "https:" + link
                    elif link.startswith("/"):
                        link = urljoin(self.base_url, link)
                    elif not link.startswith("http"):
                        link = urljoin(self.base_url, link)

                    normalized = normalize_url(link)
                    if normalized and normalized not in seen and normalized not in self.visited and is_valid_url(normalized):
                        seen.add(normalized)
                        results.append({
                            "url": normalized,
                            "source": "browser",
                            "status_code": None,
                            "content_type": "",
                            "depth": 1,
                        })
                except Exception:
                    continue

            # Add API endpoints
            for api_url in api_urls:
                if api_url not in seen and api_url not in self.visited:
                    seen.add(api_url)
                    results.append({
                        "url": api_url,
                        "source": "browser_api",
                        "status_code": None,
                        "content_type": "",
                        "depth": 0,
                    })

            # Visit a few internal pages to discover more links (BFS depth 1)
            internal_pages = [r for r in results if not is_external(r["url"], self.domain)][:15]
            for page_info in internal_pages:
                if len(results) >= self.max_pages:
                    break
                try:
                    await asyncio.sleep(random.uniform(0.5, 1.5))
                    resp = await page.goto(page_info["url"], timeout=15000, wait_until="domcontentloaded")
                    page_info["status_code"] = resp.status if resp else 0
                    await asyncio.sleep(1.5)

                    sub_links = await page.evaluate("""() => {
                        const urls = new Set();
                        document.querySelectorAll('a[href]').forEach(el => {
                            const href = el.getAttribute('href');
                            if (href && href.trim() && !href.startsWith('#') && 
                                !href.startsWith('javascript:') && !href.startsWith('mailto:')) {
                                urls.add(href.trim());
                            }
                        });
                        return Array.from(urls);
                    }""")

                    for link in sub_links:
                        try:
                            if link.startswith("//"):
                                link = "https:" + link
                            elif link.startswith("/"):
                                link = urljoin(self.base_url, link)
                            elif not link.startswith("http"):
                                link = urljoin(self.base_url, link)
                            normalized = normalize_url(link)
                            if normalized and normalized not in seen and normalized not in self.visited and is_valid_url(normalized):
                                seen.add(normalized)
                                results.append({
                                    "url": normalized,
                                    "source": "browser",
                                    "status_code": None,
                                    "content_type": "",
                                    "depth": 2,
                                })
                        except Exception:
                            continue
                except Exception as e:
                    logger.debug(f"Playwright sub-page crawl error: {e}")
                    continue

            logger.info(f"Playwright crawl complete: {len(results)} URLs discovered")

        except Exception as e:
            logger.error(f"Playwright crawl failed: {e}", exc_info=True)
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
