"""
SPA Crawler — Playwright-based private page discovery for SPA sites.

After successful login (cookies obtained), this crawler:
  1. Opens browser with auth cookies
  2. Navigates pages via BFS
  3. Extracts links from DOM (a[href], routerLink, data-href, onclick, etc.)
  4. Clicks navigation elements to discover client-side routes
  5. Captures XHR/fetch requests to find API endpoints
  6. Sends live progress events via SSE event_queue
"""

import asyncio
import logging
import re
import time
from collections import deque
from urllib.parse import urlparse, urlunparse, urljoin

logger = logging.getLogger("scanner.spa_crawler")

try:
    from playwright.async_api import async_playwright, Page
    _PW_AVAILABLE = True
except ImportError:
    _PW_AVAILABLE = False
    logger.warning("Playwright not available for SPA crawler")

try:
    from core.auth_helpers import get_random_ua
except ImportError:
    def get_random_ua():
        return "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"


# ── URL helpers ──────────────────────────────────────────────────────────────

_STATIC_EXT = frozenset([
    ".js", ".css", ".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico",
    ".woff", ".woff2", ".ttf", ".eot", ".mp3", ".mp4", ".webp",
    ".avif", ".map", ".pdf", ".zip", ".gz", ".tar", ".rar", ".7z",
])
_SKIP_SCHEMES = frozenset(["javascript", "data", "blob", "mailto", "tel", "ftp"])

# Common private route patterns for SPA sites
_ROUTE_RE = re.compile(
    r"""[\'\"/]((?:dashboard|account|profile|settings|panel|user|admin|cabinet|
    wallet|history|bonus|promo|deposit|withdraw|bet|coupon|ticket|personal|
    balance|transactions|notifications|messages|support|cashier|my|favorites|
    live|prematch|results|casino|games|sport|esport|virtual|fantasy|poker|
    bingo|lottery|slots|promotions|vip|loyalty|shop|store|cart|checkout|
    orders|payments|security|privacy|change-password|two-factor|kyc|
    verification|documents|upload|refer|affiliate|help|faq|contact|
    about|terms|rules|responsible)[a-zA-Z0-9_/-]*)[\'\"]""".replace("\n", "").replace("    ", ""),
    re.I,
)


def _norm(url):
    """Normalize URL: lowercase scheme/host, strip trailing slash, remove fragment."""
    try:
        p = urlparse(url)
        if p.scheme not in ("http", "https"):
            return ""
        path = p.path.rstrip("/") or "/"
        return urlunparse((p.scheme.lower(), p.netloc.lower(), path, p.params, p.query, ""))
    except Exception:
        return ""


def _same_domain(url, domain):
    """Check if URL belongs to the same domain."""
    try:
        host = urlparse(url).netloc.lower().split(":")[0]
        d = domain.lower()
        return host == d or host.endswith("." + d)
    except Exception:
        return False


def _is_static(url):
    """Check if URL points to a static asset."""
    return any(urlparse(url).path.lower().endswith(e) for e in _STATIC_EXT)


def _is_api(url):
    """Check if URL is an API endpoint."""
    p = urlparse(url).path.lower()
    return any(s in p for s in ["/api/", "/graphql", "/rest/", "/v1/", "/v2/", "/v3/"])


def _skip(url):
    """Check if URL should be skipped."""
    try:
        p = urlparse(url)
        return p.scheme in _SKIP_SCHEMES or _is_static(url)
    except Exception:
        return True


# ── Link extraction ─────────────────────────────────────────────────────────

async def _extract_links(page, domain):
    """
    Extract all links from current page DOM.
    Covers: <a href>, [data-href], [routerlink], [ng-href], [to],
    onclick handlers with URL patterns, and JS route strings.
    """
    links = set()

    try:
        # Standard and SPA framework attributes
        raw_urls = await page.evaluate("""() => {
            const urls = new Set();
            
            // <a href="...">
            document.querySelectorAll('a[href]').forEach(el => {
                const href = el.getAttribute('href');
                if (href && href.trim()) urls.add(href.trim());
            });
            
            // SPA framework attributes
            const attrs = ['data-href', 'routerlink', 'ng-href', 'to', 'data-url',
                           'data-link', 'data-route', 'data-path', 'data-navigate'];
            attrs.forEach(attr => {
                document.querySelectorAll(`[${attr}]`).forEach(el => {
                    const val = el.getAttribute(attr);
                    if (val && val.trim()) urls.add(val.trim());
                });
            });
            
            // onclick handlers with URLs
            document.querySelectorAll('[onclick]').forEach(el => {
                const onclick = el.getAttribute('onclick') || '';
                const matches = onclick.match(/['\"](\\/[a-zA-Z][a-zA-Z0-9_\\/-]*)['\"]|location\\.href\\s*=\\s*['\"]([^'\"]+)['\"]/g);
                if (matches) {
                    matches.forEach(m => {
                        const url = m.replace(/.*['\"]([^'\"]+)['\"].*/, '$1');
                        if (url.startsWith('/')) urls.add(url);
                    });
                }
            });
            
            // window.__ROUTES__, window.__NEXT_DATA__ etc.
            try {
                if (window.__NEXT_DATA__ && window.__NEXT_DATA__.props) {
                    const str = JSON.stringify(window.__NEXT_DATA__);
                    const routeMatches = str.match(/\"href\":\"([^\"]+)\"/g);
                    if (routeMatches) {
                        routeMatches.forEach(m => {
                            const url = m.replace(/"href":"([^"]+)"/, '$1');
                            if (url.startsWith('/')) urls.add(url);
                        });
                    }
                }
            } catch(e) {}
            
            // Look for route-like strings in inline scripts
            try {
                document.querySelectorAll('script:not([src])').forEach(script => {
                    const text = script.textContent || '';
                    if (text.length > 500000) return; // skip huge scripts
                    const routeMatches = text.match(/['\"\\/]((?:dashboard|account|profile|settings|cabinet|wallet|history|bonus|deposit|withdraw|personal|balance|transactions|notifications|cashier|my|favorites)[a-zA-Z0-9_\\/-]*)['\"\\/]/gi);
                    if (routeMatches) {
                        routeMatches.forEach(m => {
                            const url = m.replace(/^['\"\\//]|['\"\\//]$/g, '');
                            if (url && !url.includes(' ')) urls.add('/' + url.replace(/^\\//, ''));
                        });
                    }
                });
            } catch(e) {}
            
            return Array.from(urls);
        }""")

        base_url = page.url
        logger.debug(f"_extract_links: base_url={base_url}, raw_urls count={len(raw_urls)}")
        for raw in raw_urls:
            try:
                if raw.startswith("//"):
                    raw = "https:" + raw
                elif raw.startswith("/"):
                    raw = urljoin(base_url, raw)
                elif not raw.startswith("http"):
                    raw = urljoin(base_url, raw)

                normalized = _norm(raw)
                if normalized and _same_domain(normalized, domain) and not _skip(normalized):
                    links.add(normalized)
            except Exception:
                continue

    except Exception as e:
        logger.debug(f"Link extraction error: {e}")

    return links


# ── Click discovery ─────────────────────────────────────────────────────────

_CLICKABLE_SELECTORS = [
    "nav a",
    "header a",
    "[role='navigation'] a",
    ".sidebar a",
    ".menu a",
    ".nav a",
    "nav button",
    "header button",
    "[role='navigation'] button",
    ".sidebar button",
    "[role='tab']",
    "[role='menuitem']",
    "[role='link']",
    "[data-toggle]",
    "[aria-expanded]",
    ".menu-item",
    ".nav-item",
    ".nav-link",
    "a[class*='menu']",
    "a[class*='nav']",
    "a[class*='link']",
    "button[class*='menu']",
    "button[class*='nav']",
    # User icon / avatar (often leads to profile/cabinet)
    "[class*='user'] a",
    "[class*='avatar'] a",
    "[class*='account'] a",
    "[class*='profile'] a",
    "[class*='cabinet'] a",
    "[class*='user-icon']",
    "[class*='user-menu']",
    "[class*='header-user']",
    "[class*='balance']",
    "[class*='deposit']",
]


async def _click_and_discover(page, domain, visited, queue, current_depth, emit, max_clicks=20):
    """
    Click on navigation elements and discover new URLs from URL changes
    and network requests. Returns number of clicks performed.
    """
    clicks = 0
    discovered = set()
    initial_url = page.url

    logger.debug(f"_click_and_discover: starting on {initial_url}, max_clicks={max_clicks}, selectors={len(_CLICKABLE_SELECTORS)}")

    for selector in _CLICKABLE_SELECTORS:
        if clicks >= max_clicks:
            break

        try:
            elements = await page.query_selector_all(selector)
            for el in elements[:5]:  # max 5 elements per selector
                if clicks >= max_clicks:
                    break

                try:
                    # Check if element is visible
                    is_visible = await el.is_visible()
                    if not is_visible:
                        continue

                    # Get href before clicking
                    href = await el.get_attribute("href")
                    if href:
                        resolved = _norm(urljoin(page.url, href))
                        if resolved and _same_domain(resolved, domain) and not _skip(resolved):
                            if resolved not in visited:
                                discovered.add(resolved)
                                continue  # Don't click links, just collect href

                    # For buttons/non-link elements: click and check URL change
                    before_url = page.url

                    try:
                        await el.click(timeout=3000, force=False)
                        clicks += 1
                    except Exception:
                        continue

                    # Wait for potential navigation
                    await asyncio.sleep(1.0)

                    after_url = _norm(page.url)
                    if after_url and after_url != _norm(before_url):
                        if _same_domain(after_url, domain) and not _skip(after_url):
                            if after_url not in visited:
                                discovered.add(after_url)
                                logger.debug(f"Click discovered: {after_url}")
                                if emit:
                                    await emit({
                                        "type": "spa_navigated",
                                        "url": after_url,
                                        "source": "click",
                                    })

                        # Go back to original page
                        try:
                            await page.go_back(timeout=10000, wait_until="domcontentloaded")
                            await asyncio.sleep(0.5)
                        except Exception:
                            try:
                                await page.goto(initial_url, timeout=15000, wait_until="domcontentloaded")
                                await asyncio.sleep(0.5)
                            except Exception:
                                break

                    # Also extract new links from current DOM state
                    new_links = await _extract_links(page, domain)
                    for link in new_links:
                        if link not in visited:
                            discovered.add(link)

                except Exception:
                    continue

        except Exception:
            continue

    # Add all discovered URLs to queue
    for url in discovered:
        if url not in visited:
            queue.append((url, current_depth + 1))
            visited.add(url)

    return clicks, len(discovered)


# ── Smart page wait ─────────────────────────────────────────────────────────

async def _smart_wait(page, timeout=8):
    """
    Wait for SPA content to render. Don't use networkidle (SPAs never reach it).
    Instead, wait for DOM stability.
    """
    try:
        # Wait for load event first
        await page.wait_for_load_state("load", timeout=timeout * 1000)
    except Exception:
        pass

    # Wait a bit for SPA JS to render
    await asyncio.sleep(1.5)

    # Try to wait for main content container
    for sel in ["main", "#app", "#root", "#__next", "[role='main']", ".content", ".main-content"]:
        try:
            await page.wait_for_selector(sel, timeout=2000, state="attached")
            break
        except Exception:
            continue

    # Scroll to trigger lazy loading
    try:
        await page.evaluate("""() => {
            window.scrollTo(0, document.body.scrollHeight / 3);
        }""")
        await asyncio.sleep(0.5)
        await page.evaluate("() => window.scrollTo(0, 0)")
        await asyncio.sleep(0.3)
    except Exception:
        pass


# ── Main crawl function ────────────────────────────────────────────────────

async def crawl_spa(
    domain,
    cookies,
    start_url=None,
    max_pages=100,
    max_depth=4,
    overall_timeout=480,
    event_queue=None,
):
    """
    Crawl SPA site with authenticated browser session.

    Args:
        domain: Target domain (e.g. "1xbet.tj")
        cookies: Dict of cookies from successful login {name: value, ...}
                 OR list of cookie dicts [{name, value, domain, path}, ...]
        start_url: Starting URL (defaults to https://{domain})
        max_pages: Maximum pages to visit
        max_depth: Maximum BFS depth
        overall_timeout: Total timeout in seconds
        event_queue: asyncio.Queue for SSE events

    Returns:
        dict with keys: urls, api_endpoints, pages_visited, clicks_performed
    """
    if not _PW_AVAILABLE:
        logger.error("Playwright not available, cannot run SPA crawler")
        return {"urls": [], "api_endpoints": [], "pages_visited": 0, "clicks_performed": 0}

    start_time = time.time()
    base = start_url or f"https://{domain}"
    base_norm = _norm(base)

    visited = set()
    queue = deque()
    found_urls = []
    api_endpoints = set()
    total_clicks = 0

    async def emit(event):
        if event_queue:
            try:
                await event_queue.put(event)
            except Exception:
                pass

    async def on_timeout():
        return time.time() - start_time > overall_timeout

    logger.info(f"SPA crawler starting for {domain}, max_pages={max_pages}, max_depth={max_depth}, timeout={overall_timeout}s")

    pw = None
    browser = None

    try:
        logger.debug(f"SPA crawl starting: domain={domain}, cookies_type={type(cookies).__name__}, "
                    f"cookies_count={len(cookies) if cookies else 0}, start_url={start_url}, "
                    f"max_pages={max_pages}, max_depth={max_depth}, timeout={overall_timeout}s")
        pw = await async_playwright().start()
        browser = await pw.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-blink-features=AutomationControlled",
                "--disable-web-security",
                "--disable-features=VizDisplayCompositor",
            ],
        )
        logger.debug("Playwright browser launched successfully")

        context = await browser.new_context(
            user_agent=get_random_ua(),
            viewport={"width": 1920, "height": 1080},
            ignore_https_errors=True,
            java_script_enabled=True,
        )

        # ── Inject cookies ──────────────────────────────────────────────
        cookie_list = []
        if isinstance(cookies, dict):
            for name, value in cookies.items():
                if not name or not value:
                    continue
                # Add both domain variants for robust matching
                cookie_list.append({
                    "name": str(name),
                    "value": str(value),
                    "domain": f".{domain}",
                    "path": "/",
                    "httpOnly": False,
                    "secure": True,
                    "sameSite": "None",
                })
                cookie_list.append({
                    "name": str(name),
                    "value": str(value),
                    "domain": domain,
                    "path": "/",
                    "httpOnly": False,
                    "secure": True,
                    "sameSite": "None",
                })
        elif isinstance(cookies, list):
            for c in cookies:
                if isinstance(c, dict) and c.get("name") and c.get("value"):
                    cookie_list.append({
                        "name": str(c["name"]),
                        "value": str(c["value"]),
                        "domain": c.get("domain", f".{domain}"),
                        "path": c.get("path", "/"),
                        "httpOnly": c.get("httpOnly", False),
                        "secure": c.get("secure", True),
                        "sameSite": c.get("sameSite", "None"),
                    })

        if cookie_list:
            try:
                await context.add_cookies(cookie_list)
                logger.info(f"SPA crawler: injected {len(cookie_list)} auth cookies for {domain}")
            except Exception as e:
                logger.warning(f"SPA crawler: cookie injection error: {e}")
                # Try one by one
                injected = 0
                for c in cookie_list:
                    try:
                        await context.add_cookies([c])
                        injected += 1
                    except Exception:
                        pass
                logger.info(f"SPA crawler: injected {injected}/{len(cookie_list)} cookies (one-by-one)")
        else:
            logger.warning("SPA crawler: no cookies to inject!")

        # ── Stealth setup — comprehensive anti-detection ────────────────
        await context.add_init_script("""
            // Hide webdriver flag
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
            delete navigator.__proto__.webdriver;

            // Chrome runtime
            window.chrome = {
                runtime: {
                    onConnect: { addListener: function(){} },
                    onMessage: { addListener: function(){} },
                    connect: function(){ return { onMessage: { addListener: function(){} }, postMessage: function(){} }; },
                    sendMessage: function(){},
                    id: 'mhjfbmdgcfjbbpaeojofohoefgiehjai'
                },
                loadTimes: function(){ return {}; },
                csi: function(){ return {}; }
            };

            // Realistic plugins
            Object.defineProperty(navigator, 'plugins', {
                get: () => {
                    const plugins = [
                        { name: 'Chrome PDF Plugin', filename: 'internal-pdf-viewer', description: 'Portable Document Format' },
                        { name: 'Chrome PDF Viewer', filename: 'mhjfbmdgcfjbbpaeojofohoefgiehjai', description: '' },
                        { name: 'Native Client', filename: 'internal-nacl-plugin', description: '' }
                    ];
                    plugins.length = 3;
                    return plugins;
                }
            });

            // Languages
            Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en', 'ru']});
            Object.defineProperty(navigator, 'language', {get: () => 'en-US'});

            // Platform
            Object.defineProperty(navigator, 'platform', {get: () => 'Win32'});

            // Hardware concurrency
            Object.defineProperty(navigator, 'hardwareConcurrency', {get: () => 8});

            // Device memory
            Object.defineProperty(navigator, 'deviceMemory', {get: () => 8});

            // Max touch points
            Object.defineProperty(navigator, 'maxTouchPoints', {get: () => 0});

            // Connection
            Object.defineProperty(navigator, 'connection', {
                get: () => ({
                    effectiveType: '4g',
                    rtt: 50,
                    downlink: 10,
                    saveData: false,
                })
            });

            // Permissions API
            const originalQuery = window.Notification && Notification.permission;
            if (navigator.permissions) {
                const origQuery = navigator.permissions.query;
                navigator.permissions.query = (parameters) => {
                    if (parameters.name === 'notifications') {
                        return Promise.resolve({state: originalQuery || 'prompt'});
                    }
                    return origQuery.call(navigator.permissions, parameters);
                };
            }

            // WebGL vendor/renderer
            const getParameter = WebGLRenderingContext.prototype.getParameter;
            WebGLRenderingContext.prototype.getParameter = function(parameter) {
                if (parameter === 37445) return 'Google Inc. (NVIDIA)';
                if (parameter === 37446) return 'ANGLE (NVIDIA, NVIDIA GeForce GTX 1650 Direct3D11 vs_5_0 ps_5_0, D3D11)';
                return getParameter.call(this, parameter);
            };

            // Prevent iframe detection
            Object.defineProperty(HTMLIFrameElement.prototype, 'contentWindow', {
                get: function() { return window; }
            });

            // Fix toString for overridden functions
            const nativeToString = Function.prototype.toString;
            const proxyHandler = {
                apply: function(target, thisArg, args) {
                    if (args[0] === navigator.webdriver) return 'function webdriver() { [native code] }';
                    return nativeToString.call(thisArg);
                }
            };

            // Pass Cloudflare checks: canvas fingerprint noise
            const origGetContext = HTMLCanvasElement.prototype.getContext;
            HTMLCanvasElement.prototype.getContext = function(type, attrs) {
                const ctx = origGetContext.call(this, type, attrs);
                if (type === '2d' && ctx) {
                    const origFillText = ctx.fillText;
                    ctx.fillText = function() {
                        // Add tiny invisible noise to canvas fingerprinting
                        arguments[1] = arguments[1] + 0.0000001;
                        return origFillText.apply(this, arguments);
                    };
                }
                return ctx;
            };
        """)

        page = await context.new_page()

        # ── Network capture (XHR/fetch → API endpoints) ────────────────
        def on_request(request):
            try:
                url = request.url
                method = request.method
                res_type = request.resource_type
                if res_type in ("xhr", "fetch") and _same_domain(url, domain):
                    norm_url = _norm(url)
                    if norm_url and norm_url not in api_endpoints:
                        api_endpoints.add(norm_url)
                        logger.debug(f"API endpoint: {method} {norm_url}")
                        # Emit spa_api_found event in real-time
                        try:
                            asyncio.get_event_loop().create_task(emit({
                                "type": "spa_api_found",
                                "url": norm_url,
                                "method": method,
                            }))
                        except Exception:
                            pass
            except Exception:
                pass

        page.on("request", on_request)

        # ── Navigate to start URL ──────────────────────────────────────
        logger.info(f"SPA crawl [1/{max_pages}] depth=0 {base}")
        try:
            response = await page.goto(base, timeout=30000, wait_until="domcontentloaded")
            status = response.status if response else 0
        except Exception as e:
            logger.warning(f"SPA crawler: initial navigation failed: {e}, retrying...")
            await asyncio.sleep(2)
            try:
                response = await page.goto(base, timeout=45000, wait_until="commit")
                status = response.status if response else 0
            except Exception as e2:
                logger.error(f"SPA crawler: initial navigation failed completely: {e2}")
                return {"urls": [], "api_endpoints": [], "pages_visited": 0, "clicks_performed": 0}

        await _smart_wait(page)

        logger.debug(f"Initial navigation complete: status={status}, final_url={page.url}")

        # Check if we're actually logged in by looking at page content
        current_url = _norm(page.url)
        visited.add(current_url)
        if base_norm and base_norm != current_url:
            visited.add(base_norm)

        # Record start page
        found_urls.append({
            "url": current_url,
            "status_code": status,
            "depth": 0,
            "source": "spa",
            "is_internal": True,
            "external_domain": "",
        })

        await emit({
            "type": "spa_progress",
            "currentUrl": current_url,
            "pagesVisited": 1,
            "queueSize": 0,
            "urlsFound": 1,
            "apiFound": len(api_endpoints),
            "message": f"Started: {current_url}",
            "done": False,
        })

        # ── Extract initial links ──────────────────────────────────────
        initial_links = await _extract_links(page, domain)
        logger.info(f"SPA crawler: {len(initial_links)} links extracted from start page")
        if initial_links:
            logger.debug(f"Initial links: {list(initial_links)[:20]}{'...' if len(initial_links) > 20 else ''}")

        for link in initial_links:
            if link not in visited:
                visited.add(link)
                queue.append((link, 1))

        # ── Extract route patterns from page source ────────────────────
        try:
            page_content = await page.content()
            route_matches = _ROUTE_RE.findall(page_content)
            for route in route_matches:
                route_url = _norm(urljoin(base, "/" + route.lstrip("/")))
                if route_url and _same_domain(route_url, domain) and route_url not in visited:
                    visited.add(route_url)
                    queue.append((route_url, 1))
                    logger.debug(f"Route pattern found: {route_url}")
        except Exception as e:
            logger.debug(f"Route extraction error: {e}")

        # ── Click discovery on start page ──────────────────────────────
        logger.debug(f"Starting click discovery on start page, queue has {len(queue)} URLs")
        clicks, click_found = await _click_and_discover(
            page, domain, visited, queue, 0, emit, max_clicks=20
        )
        total_clicks += clicks
        logger.info(f"SPA crawler: click discovery on start page: {clicks} clicks, {click_found} new URLs")
        logger.debug(f"After start page analysis: visited={len(visited)}, queue={len(queue)}, found_urls={len(found_urls)}")

        await emit({
            "type": "spa_progress",
            "currentUrl": current_url,
            "pagesVisited": 1,
            "queueSize": len(queue),
            "urlsFound": len(found_urls),
            "apiFound": len(api_endpoints),
            "message": f"Queue: {len(queue)} URLs after start page analysis",
            "done": False,
        })

        # ── BFS crawl loop ─────────────────────────────────────────────
        pages_visited = 1

        while queue and pages_visited < max_pages:
            if await on_timeout():
                logger.info(f"SPA crawler: timeout reached after {pages_visited} pages")
                break

            url, depth = queue.popleft()

            if depth > max_depth:
                continue

            normalized = _norm(url)
            if not normalized or _skip(normalized):
                continue

            pages_visited += 1
            logger.info(f"SPA crawl [{pages_visited}/{max_pages}] depth={depth} {normalized}")

            await emit({
                "type": "spa_page_visited",
                "url": normalized,
                "depth": depth,
                "pageNumber": pages_visited,
            })

            try:
                response = await page.goto(normalized, timeout=20000, wait_until="domcontentloaded")
                status = response.status if response else 0
            except Exception as e:
                logger.debug(f"SPA crawl: navigation to {normalized} failed: {e}")
                # Try with commit (less strict)
                try:
                    response = await page.goto(normalized, timeout=15000, wait_until="commit")
                    status = response.status if response else 0
                except Exception:
                    status = 0
                    continue

            await _smart_wait(page)

            # Actual URL after redirects
            actual_url = _norm(page.url)
            if actual_url:
                visited.add(actual_url)

            found_urls.append({
                "url": actual_url or normalized,
                "status_code": status,
                "depth": depth,
                "source": "spa",
                "is_internal": True,
                "external_domain": "",
            })

            # Extract links
            page_links = await _extract_links(page, domain)
            new_count = 0
            for link in page_links:
                if link not in visited:
                    visited.add(link)
                    queue.append((link, depth + 1))
                    new_count += 1

            # Click discovery (less aggressive on sub-pages)
            if depth <= 2:
                clicks, click_found = await _click_and_discover(
                    page, domain, visited, queue, depth, emit, max_clicks=10
                )
                total_clicks += clicks

            await emit({
                "type": "spa_progress",
                "currentUrl": actual_url or normalized,
                "pagesVisited": pages_visited,
                "queueSize": len(queue),
                "urlsFound": len(found_urls),
                "apiFound": len(api_endpoints),
                "message": f"Page {pages_visited}: +{new_count} links",
                "done": False,
            })

            # Small delay between pages
            await asyncio.sleep(0.5)

        # ── Add API endpoints to found URLs ────────────────────────────
        api_list = []
        for api_url in api_endpoints:
            if api_url not in {u["url"] for u in found_urls}:
                api_list.append({
                    "url": api_url,
                    "status_code": 200,
                    "depth": 0,
                    "source": "api",
                    "is_internal": True,
                    "external_domain": "",
                })
                await emit({
                    "type": "spa_api_found",
                    "url": api_url,
                })

        found_urls.extend(api_list)

        elapsed = time.time() - start_time
        logger.info(
            f"SPA crawl complete for {domain}: {pages_visited} pages, "
            f"{len(found_urls)} URLs, {len(api_endpoints)} API endpoints, "
            f"{total_clicks} clicks in {elapsed:.1f}s"
        )

        await emit({
            "type": "spa_progress",
            "currentUrl": "",
            "pagesVisited": pages_visited,
            "queueSize": 0,
            "urlsFound": len(found_urls),
            "apiFound": len(api_endpoints),
            "message": f"Complete: {len(found_urls)} URLs, {len(api_endpoints)} APIs in {elapsed:.0f}s",
            "done": True,
        })

        return {
            "urls": found_urls,
            "api_endpoints": list(api_endpoints),
            "pages_visited": pages_visited,
            "clicks_performed": total_clicks,
        }

    except Exception as e:
        logger.error(f"SPA crawler error for {domain}: {e}", exc_info=True)
        await emit({
            "type": "spa_progress",
            "currentUrl": "",
            "pagesVisited": 0,
            "queueSize": 0,
            "urlsFound": 0,
            "apiFound": 0,
            "message": f"Error: {e}",
            "done": True,
        })
        return {"urls": found_urls, "api_endpoints": list(api_endpoints), "pages_visited": 0, "clicks_performed": 0}

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
