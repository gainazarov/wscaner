"""
SPA Crawler — Behavior-driven Playwright-based page discovery for SPA sites.

Architecture:
  1. Opens browser with auth cookies + stealth
  2. BFS navigation through pages
  3. Action-based clicking (buttons, [role=button], div[onclick], etc.)
  4. Navigation detection (URL change + DOM hash comparison)
  5. Click deduplication (page_url, element_id)
  6. Enhanced DOM extraction (a, button, [role=link], router, onclick, etc.)
  7. Network capture (XHR/fetch) with source page mapping
  8. Smart wait for SPA rendering
  9. Retry logic for navigation and clicks
  10. Live progress events via SSE
"""

import asyncio
import hashlib
import logging
import random
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
        return "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"


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


def _skip(url):
    """Check if URL should be skipped."""
    try:
        p = urlparse(url)
        return p.scheme in _SKIP_SCHEMES or _is_static(url)
    except Exception:
        return True


# ── Stealth init script ─────────────────────────────────────────────────────

STEALTH_JS = """
    Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
    delete navigator.__proto__.webdriver;
    window.chrome = {
        runtime: {
            onConnect: {addListener: function(){}},
            onMessage: {addListener: function(){}},
            connect: function(){return {onMessage:{addListener:function(){}},postMessage:function(){}}; },
            sendMessage: function(){},
            id: 'mhjfbmdgcfjbbpaeojofohoefgiehjai'
        },
        loadTimes: function(){return {};},
        csi: function(){return {};}
    };
    Object.defineProperty(navigator, 'plugins', {
        get: () => {
            const p = [
                {name:'Chrome PDF Plugin', filename:'internal-pdf-viewer', description:'Portable Document Format'},
                {name:'Chrome PDF Viewer', filename:'mhjfbmdgcfjbbpaeojofohoefgiehjai', description:''},
                {name:'Native Client', filename:'internal-nacl-plugin', description:''}
            ];
            p.length = 3;
            return p;
        }
    });
    Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en', 'ru']});
    Object.defineProperty(navigator, 'language', {get: () => 'en-US'});
    Object.defineProperty(navigator, 'platform', {get: () => 'Win32'});
    Object.defineProperty(navigator, 'hardwareConcurrency', {get: () => 8});
    Object.defineProperty(navigator, 'deviceMemory', {get: () => 8});
    Object.defineProperty(navigator, 'maxTouchPoints', {get: () => 0});
    Object.defineProperty(navigator, 'connection', {
        get: () => ({effectiveType: '4g', rtt: 50, downlink: 10, saveData: false})
    });
    const gp = WebGLRenderingContext.prototype.getParameter;
    WebGLRenderingContext.prototype.getParameter = function(p) {
        if (p === 37445) return 'Google Inc. (NVIDIA)';
        if (p === 37446) return 'ANGLE (NVIDIA, NVIDIA GeForce GTX 1650 Direct3D11 vs_5_0 ps_5_0, D3D11)';
        return gp.call(this, p);
    };
    if (navigator.permissions) {
        const oq = navigator.permissions.query;
        navigator.permissions.query = (params) => {
            if (params.name === 'notifications') return Promise.resolve({state: 'prompt'});
            return oq.call(navigator.permissions, params);
        };
    }
    // Canvas fingerprint noise
    const origGetContext = HTMLCanvasElement.prototype.getContext;
    HTMLCanvasElement.prototype.getContext = function(type, attrs) {
        const ctx = origGetContext.call(this, type, attrs);
        if (type === '2d' && ctx) {
            const origFillText = ctx.fillText;
            ctx.fillText = function() {
                arguments[1] = arguments[1] + 0.0000001;
                return origFillText.apply(this, arguments);
            };
        }
        return ctx;
    };
"""

# ── Clickable selectors (priority ordered) ───────────────────────────────────

CLICK_SELECTORS = [
    # Navigation
    "nav a", "header a", "[role='navigation'] a",
    ".sidebar a", ".menu a", ".nav a",
    # Buttons
    "nav button", "header button", "[role='navigation'] button",
    ".sidebar button",
    # ARIA roles
    "[role='button']", "[role='tab']", "[role='menuitem']", "[role='link']",
    # Interactive elements
    "[data-toggle]", "[aria-expanded]",
    "div[onclick]", "span[onclick]", "li[onclick]",
    "[data-href]", "[data-url]", "[data-link]",
    # Menu / nav classes
    ".menu-item", ".nav-item", ".nav-link",
    "a[class*='menu']", "a[class*='nav']", "a[class*='link']",
    "button[class*='menu']", "button[class*='nav']",
    # User-area (critical for 1xbet-like sites)
    "[class*='user'] a", "[class*='avatar'] a",
    "[class*='account'] a", "[class*='profile'] a",
    "[class*='cabinet'] a", "[class*='user-icon']",
    "[class*='user-menu']", "[class*='header-user']",
    "[class*='balance']", "[class*='deposit']",
    "[class*='sport']", "[class*='casino']",
    "[class*='live']", "[class*='promo']",
    "[class*='bonus']",
    # Footer
    "footer a",
]

# ── Link extraction ─────────────────────────────────────────────────────────

async def _extract_links(page, domain):
    """
    Extract all links from DOM:
      a[href], button, [role=link], [data-testid], [onclick],
      router links (React/Vue/Angular), window.location patterns
    """
    links = set()

    try:
        raw_urls = await page.evaluate("""() => {
            const urls = new Set();

            // <a href>
            document.querySelectorAll('a[href]').forEach(el => {
                const href = el.getAttribute('href');
                if (href && href.trim() && !href.startsWith('#') &&
                    !href.startsWith('javascript:') && !href.startsWith('mailto:') &&
                    !href.startsWith('tel:') && !href.startsWith('data:')) {
                    urls.add(href.trim());
                }
            });

            // SPA framework attributes
            ['data-href', 'routerlink', 'ng-href', 'to', 'data-url',
             'data-link', 'data-route', 'data-path', 'data-navigate'].forEach(attr => {
                document.querySelectorAll('[' + attr + ']').forEach(el => {
                    const val = el.getAttribute(attr);
                    if (val && val.trim()) urls.add(val.trim());
                });
            });

            // [role=link] with useful attributes
            document.querySelectorAll('[role="link"]').forEach(el => {
                for (const attr of el.attributes) {
                    if (attr.value && attr.value.startsWith('/') && attr.value.length > 1) {
                        urls.add(attr.value);
                    }
                }
            });

            // [data-testid] that look like routes
            document.querySelectorAll('[data-testid]').forEach(el => {
                const tid = el.getAttribute('data-testid');
                if (tid && tid.includes('/')) urls.add(tid);
                const href = el.getAttribute('href');
                if (href && href.startsWith('/')) urls.add(href);
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

            // Route-like strings in inline scripts
            try {
                document.querySelectorAll('script:not([src])').forEach(script => {
                    const text = script.textContent || '';
                    if (text.length > 500000) return;
                    // Path patterns
                    const paths = text.match(/['\"\\/]((?:dashboard|account|profile|settings|cabinet|wallet|history|bonus|deposit|withdraw|personal|balance|transactions|notifications|cashier|my|favorites|live|prematch|casino|games|sport|esport|virtual|poker|lottery|slots|promotions|vip|help|faq|contact|about|terms|rules|support)[a-zA-Z0-9_\\/-]*)['\"\\/]/gi);
                    if (paths) paths.forEach(m => {
                        const url = m.replace(/^['\"\\//]|['\"\\//]$/g, '');
                        if (url && !url.includes(' ')) urls.add('/' + url.replace(/^\\//, ''));
                    });
                    // Router definitions
                    const rp = text.match(/path\\s*:\\s*['\"](\\/[^'\"]+)['\"]/g);
                    if (rp) rp.forEach(m => {
                        const url = m.replace(/path\\s*:\\s*['\"]([^'\"]+)['\"]/, '$1');
                        if (url.startsWith('/')) urls.add(url);
                    });
                });
            } catch(e) {}

            return Array.from(urls);
        }""")

        base_url = page.url
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

# ── DOM hash for navigation detection ────────────────────────────────────────

async def _get_dom_hash(page) -> str:
    """Get a fast DOM fingerprint for change detection."""
    try:
        return await page.evaluate("""() => {
            const el = document.querySelector('main, #app, #root, [role=main], .content, body');
            if (!el) return '';
            const text = el.innerText || '';
            const links = document.querySelectorAll('a').length;
            const btns = document.querySelectorAll('button').length;
            const inputs = document.querySelectorAll('input').length;
            return text.substring(0, 500).replace(/\\s+/g, ' ') + '|L' + links + '|B' + btns + '|I' + inputs;
        }""")
    except Exception:
        return ""


# ── Navigation with retry ───────────────────────────────────────────────────

async def _goto_retry(page, url, retries=3):
    """Navigate with retry logic and fallback wait strategy."""
    for attempt in range(retries):
        try:
            resp = await page.goto(url, timeout=20000, wait_until="domcontentloaded")
            return resp
        except Exception as e:
            if attempt < retries - 1:
                logger.debug(f"Goto retry {attempt+1}/{retries} for {url}: {e}")
                await asyncio.sleep(random.uniform(1, 3))
            else:
                try:
                    resp = await page.goto(url, timeout=15000, wait_until="commit")
                    return resp
                except Exception:
                    logger.debug(f"Goto failed completely: {url}")
                    return None


# ── Click discovery ─────────────────────────────────────────────────────────

async def _click_and_discover(
    page, domain, visited, visited_actions, queue,
    current_depth, emit, max_clicks=20,
):
    """
    Click interactive elements and detect new pages via:
      1. URL change
      2. DOM content hash change
    Deduplicates clicks by (page_url, element_id).
    Returns: (clicks_performed, urls_discovered)
    """
    clicks = 0
    discovered = set()
    page_url = _norm(page.url) or page.url

    for selector in CLICK_SELECTORS:
        if clicks >= max_clicks:
            break
        try:
            elements = await page.query_selector_all(selector)
        except Exception:
            continue

        for el in elements[:5]:
            if clicks >= max_clicks:
                break
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
                    resolved = _norm(urljoin(page.url, href))
                    if resolved and _same_domain(resolved, domain) and not _skip(resolved):
                        if resolved not in visited:
                            discovered.add(resolved)
                    continue  # Don't click links

                # For buttons/non-link elements: click and detect navigation
                before_url = page.url
                before_dom = await _get_dom_hash(page)

                try:
                    await el.click(timeout=3000, force=False)
                    clicks += 1
                except Exception:
                    continue

                await asyncio.sleep(random.uniform(0.8, 1.5))

                # ── Navigation detection ──
                after_url = page.url
                after_dom = await _get_dom_hash(page)

                url_changed = _norm(after_url) != _norm(before_url)
                dom_changed = after_dom != before_dom and len(after_dom) > 10

                if url_changed:
                    new_url = _norm(after_url)
                    if new_url and _same_domain(new_url, domain) and not _skip(new_url):
                        if new_url not in visited:
                            discovered.add(new_url)
                            logger.debug(f"Click→Nav: {new_url}")
                            if emit:
                                await emit({
                                    "type": "spa_navigated",
                                    "url": new_url,
                                    "source": "click",
                                    "trigger": el_id[:80],
                                })

                    # Go back
                    try:
                        await page.go_back(timeout=10000, wait_until="domcontentloaded")
                        await asyncio.sleep(0.5)
                    except Exception:
                        try:
                            await _goto_retry(page, page_url)
                            await _smart_wait(page)
                        except Exception:
                            break

                elif dom_changed:
                    # DOM changed but URL didn't — SPA route or modal
                    new_links = await _extract_links(page, domain)
                    for link in new_links:
                        if link not in visited:
                            discovered.add(link)
                    if emit:
                        await emit({
                            "type": "spa_dom_changed",
                            "page": page_url,
                            "trigger": el_id[:80],
                            "new_links": len([l for l in new_links if l not in visited]),
                        })

            except Exception:
                continue

    # Add discovered to queue
    for url in discovered:
        if url not in visited:
            queue.append((url, current_depth + 1))
            visited.add(url)

    return clicks, len(discovered)


# ── Smart page wait ─────────────────────────────────────────────────────────

async def _smart_wait(page, timeout=8):
    """
    Wait for SPA content to render:
      1. domcontentloaded
      2. Main container selector
      3. JS render time
      4. Scroll to trigger lazy loading
    """
    try:
        await page.wait_for_load_state("domcontentloaded", timeout=timeout * 1000)
    except Exception:
        pass

    # Wait for main content container
    for sel in ["main", "#app", "#root", "#__next", "[role='main']", ".content", ".main-content"]:
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
    Behavior-driven SPA crawl with authenticated browser session.

    Features:
      - Action-based clicking (buttons, [role=button], div[onclick], etc.)
      - Navigation detection (URL + DOM hash)
      - Click deduplication
      - Enhanced network capture with source mapping
      - Smart wait for SPA rendering
      - Retry logic
      - Page fingerprinting for dedup

    Args:
        domain: Target domain (e.g. "1xbet.tj")
        cookies: Dict or list of cookies from login
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

    # ── State ──
    visited = set()
    visited_actions: set[tuple[str, str]] = set()  # click dedup
    queue = deque()
    found_urls = []
    api_endpoints: dict[str, str] = {}  # url -> found_on_page
    page_hashes: set[str] = set()  # DOM fingerprints
    total_clicks = 0
    current_page_url = [base]  # mutable ref for closure

    async def emit(event):
        if event_queue:
            try:
                await event_queue.put(event)
            except Exception:
                pass

    logger.info(f"SPA crawler starting for {domain}, max_pages={max_pages}, max_depth={max_depth}, timeout={overall_timeout}s")

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
                "--disable-web-security",
                "--disable-features=VizDisplayCompositor",
            ],
        )

        context = await browser.new_context(
            user_agent=get_random_ua(),
            viewport={"width": 1920, "height": 1080},
            ignore_https_errors=True,
            java_script_enabled=True,
        )

        # ── Inject cookies ──
        cookie_list = []
        if isinstance(cookies, dict):
            for name, value in cookies.items():
                if not name or not value:
                    continue
                for d in [f".{domain}", domain]:
                    cookie_list.append({
                        "name": str(name), "value": str(value),
                        "domain": d, "path": "/",
                        "httpOnly": False, "secure": True, "sameSite": "None",
                    })
        elif isinstance(cookies, list):
            for c in cookies:
                if isinstance(c, dict) and c.get("name") and c.get("value"):
                    cookie_list.append({
                        "name": str(c["name"]), "value": str(c["value"]),
                        "domain": c.get("domain", f".{domain}"),
                        "path": c.get("path", "/"),
                        "httpOnly": c.get("httpOnly", False),
                        "secure": c.get("secure", True),
                        "sameSite": c.get("sameSite", "None"),
                    })

        if cookie_list:
            try:
                await context.add_cookies(cookie_list)
                logger.info(f"SPA crawler: injected {len(cookie_list)} cookies")
            except Exception as e:
                logger.warning(f"Cookie injection error: {e}")
                injected = 0
                for c in cookie_list:
                    try:
                        await context.add_cookies([c])
                        injected += 1
                    except Exception:
                        pass
                logger.info(f"Injected {injected}/{len(cookie_list)} cookies (one-by-one)")
        else:
            logger.warning("SPA crawler: no cookies to inject!")

        # ── Stealth ──
        await context.add_init_script(STEALTH_JS)

        page = await context.new_page()

        # ── Network capture with source mapping ──
        def on_request(request):
            try:
                if request.resource_type in ("xhr", "fetch") and _same_domain(request.url, domain):
                    norm_url = _norm(request.url)
                    if norm_url and norm_url not in api_endpoints:
                        api_endpoints[norm_url] = current_page_url[0]
                        logger.debug(f"API: {request.method} {norm_url} (from {current_page_url[0]})")
                        try:
                            asyncio.get_event_loop().create_task(emit({
                                "type": "spa_api_found",
                                "url": norm_url,
                                "method": request.method,
                                "found_on": current_page_url[0],
                            }))
                        except Exception:
                            pass
            except Exception:
                pass

        def on_response(response):
            try:
                if response.request.resource_type in ("xhr", "fetch"):
                    norm_url = _norm(response.url)
                    if norm_url and _same_domain(norm_url, domain) and norm_url not in api_endpoints:
                        api_endpoints[norm_url] = current_page_url[0]
            except Exception:
                pass

        page.on("request", on_request)
        page.on("response", on_response)

        # ── Navigate to start URL ──
        logger.info(f"SPA crawl [1/{max_pages}] depth=0 {base}")
        response = await _goto_retry(page, base)
        if not response:
            return {"urls": [], "api_endpoints": [], "pages_visited": 0, "clicks_performed": 0}

        await _smart_wait(page)

        current_url = _norm(page.url)
        visited.add(current_url)
        visited.add(_norm(base))

        dom_hash = await _get_dom_hash(page)
        if dom_hash:
            page_hashes.add(dom_hash[:200])

        found_urls.append({
            "url": current_url,
            "status_code": response.status if response else 0,
            "depth": 0,
            "source": "spa",
            "is_internal": True,
            "external_domain": "",
            "found_on": "",
        })

        await emit({
            "type": "spa_progress",
            "currentUrl": current_url,
            "pagesVisited": 1,
            "queueSize": 0,
            "urlsFound": 1,
            "apiFound": 0,
            "clicks": 0,
            "message": f"Started: {current_url}",
            "done": False,
        })

        # ── Extract initial links ──
        initial_links = await _extract_links(page, domain)
        logger.info(f"SPA crawler: {len(initial_links)} links from start page")

        # Also extract route patterns from page source
        try:
            page_content = await page.content()
            for route in _ROUTE_RE.findall(page_content):
                route_url = _norm(urljoin(base, "/" + route.lstrip("/")))
                if route_url and _same_domain(route_url, domain):
                    initial_links.add(route_url)
        except Exception:
            pass

        for link in initial_links:
            if link not in visited:
                visited.add(link)
                queue.append((link, 1))

        # ── Click discovery on start page ──
        clicks, click_found = await _click_and_discover(
            page, domain, visited, visited_actions, queue, 0, emit, max_clicks=25
        )
        total_clicks += clicks
        logger.info(f"Start page: {clicks} clicks, {click_found} new URLs, queue={len(queue)}")

        await emit({
            "type": "spa_progress",
            "currentUrl": current_url,
            "pagesVisited": 1,
            "queueSize": len(queue),
            "urlsFound": len(found_urls),
            "apiFound": len(api_endpoints),
            "clicks": total_clicks,
            "message": f"Queue: {len(queue)} URLs after start page",
            "done": False,
        })

        # ── BFS crawl loop ──
        pages_visited = 1

        while queue and pages_visited < max_pages:
            if time.time() - start_time > overall_timeout:
                logger.info(f"SPA crawler: timeout after {pages_visited} pages")
                break

            url, depth = queue.popleft()
            if depth > max_depth:
                continue

            normalized = _norm(url)
            if not normalized or _skip(normalized) or normalized in visited:
                continue

            visited.add(normalized)
            current_page_url[0] = normalized
            pages_visited += 1

            # Random delay
            await asyncio.sleep(random.uniform(0.5, 1.5))

            logger.info(f"SPA crawl [{pages_visited}/{max_pages}] depth={depth} {normalized}")

            await emit({
                "type": "spa_page_visited",
                "url": normalized,
                "depth": depth,
                "pageNumber": pages_visited,
            })

            # Navigate with retry
            response = await _goto_retry(page, normalized)
            if not response:
                continue

            await _smart_wait(page)

            actual_url = _norm(page.url)
            if actual_url:
                visited.add(actual_url)

            # Page fingerprint dedup
            dom_hash = await _get_dom_hash(page)
            dom_key = dom_hash[:200] if dom_hash else ""
            if dom_key and dom_key in page_hashes:
                logger.debug(f"Duplicate page content: {actual_url}")
                continue
            if dom_key:
                page_hashes.add(dom_key)

            found_urls.append({
                "url": actual_url or normalized,
                "status_code": response.status if response else 0,
                "depth": depth,
                "source": "spa",
                "is_internal": True,
                "external_domain": "",
                "found_on": current_page_url[0],
            })

            # Extract links
            page_links = await _extract_links(page, domain)
            new_count = 0
            for link in page_links:
                if link not in visited:
                    visited.add(link)
                    queue.append((link, depth + 1))
                    new_count += 1

            # Click discovery (less aggressive on deeper pages)
            if depth <= 2:
                max_cl = 20 if depth == 0 else (12 if depth == 1 else 6)
                clicks, click_found = await _click_and_discover(
                    page, domain, visited, visited_actions, queue,
                    depth, emit, max_clicks=max_cl,
                )
                total_clicks += clicks

            await emit({
                "type": "spa_progress",
                "currentUrl": actual_url or normalized,
                "pagesVisited": pages_visited,
                "queueSize": len(queue),
                "urlsFound": len(found_urls),
                "apiFound": len(api_endpoints),
                "clicks": total_clicks,
                "message": f"Page {pages_visited}: +{new_count} links, {total_clicks} clicks",
                "done": False,
            })

        # ── Add API endpoints ──
        api_list = []
        for api_url, source_page in api_endpoints.items():
            if api_url not in {u["url"] for u in found_urls}:
                api_list.append({
                    "url": api_url,
                    "status_code": 200,
                    "depth": 0,
                    "source": "api",
                    "is_internal": True,
                    "external_domain": "",
                    "found_on": source_page,
                })
        found_urls.extend(api_list)

        elapsed = time.time() - start_time
        logger.info(
            f"SPA crawl complete for {domain}: {pages_visited} pages, "
            f"{len(found_urls)} URLs, {len(api_endpoints)} APIs, "
            f"{total_clicks} clicks in {elapsed:.1f}s"
        )

        await emit({
            "type": "spa_progress",
            "currentUrl": "",
            "pagesVisited": pages_visited,
            "queueSize": 0,
            "urlsFound": len(found_urls),
            "apiFound": len(api_endpoints),
            "clicks": total_clicks,
            "message": f"Complete: {len(found_urls)} URLs, {len(api_endpoints)} APIs, {total_clicks} clicks in {elapsed:.0f}s",
            "done": True,
        })

        return {
            "urls": found_urls,
            "api_endpoints": list(api_endpoints.keys()),
            "pages_visited": pages_visited,
            "clicks_performed": total_clicks,
        }

    except Exception as e:
        logger.error(f"SPA crawler error for {domain}: {e}", exc_info=True)
        await emit({
            "type": "spa_progress",
            "currentUrl": "", "pagesVisited": 0, "queueSize": 0,
            "urlsFound": 0, "apiFound": 0, "clicks": 0,
            "message": f"Error: {e}", "done": True,
        })
        return {"urls": found_urls, "api_endpoints": list(api_endpoints.keys()),
                "pages_visited": 0, "clicks_performed": 0}

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
