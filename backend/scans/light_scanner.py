"""
Light Scanner — fast, focused page checker for real-time monitoring.

Instead of a full BFS crawl, this module:
1. Fetches only a predefined list of key pages (/, /login, /checkout, etc.)
2. Hashes the aggregated HTML content (MD5)
3. Extracts external domains from each page
4. Compares against the previous scan's domain set to detect new/removed domains

This is designed to run every 15 minutes without hitting rate limits.
"""

import hashlib
import logging
import re
import time
from dataclasses import dataclass, field
from urllib.parse import urljoin, urlparse

import aiohttp

logger = logging.getLogger("scans.light_scanner")

# ─── Regex for extracting external URLs from HTML ────────────────────────────

# Matches src="...", href="...", url("..."), url('...')
_URL_ATTR_RE = re.compile(
    r"""(?:src|href|action|data-src|poster)\s*=\s*["']([^"']+)["']"""
    r"""|url\(\s*["']?([^"')]+)["']?\s*\)""",
    re.IGNORECASE,
)

# Matches full URLs in JS strings: "https://..." or 'https://...'
_JS_URL_RE = re.compile(
    r"""["'](https?://[a-zA-Z0-9._\-]+(?:\.[a-zA-Z]{2,})(?:/[^"'<>\s]*)?)["']""",
    re.IGNORECASE,
)


@dataclass
class PageResult:
    """Result of fetching a single page."""
    url: str
    status_code: int = 0
    content_hash: str = ""
    has_content: bool = False
    external_domains: set = field(default_factory=set)
    error: str = ""


@dataclass
class LightScanOutput:
    """Aggregated result of a light scan."""
    domain: str = ""
    content_hash: str = ""
    pages_checked: int = 0
    pages_data: list = field(default_factory=list)
    external_domains: set = field(default_factory=set)
    duration: float = 0.0
    error: str = ""


def _extract_domain(url: str) -> str:
    """Extract domain from a URL, stripping port."""
    try:
        parsed = urlparse(url)
        return parsed.netloc.lower().split(":")[0]
    except Exception:
        return ""


def _is_external(url: str, target_domain: str) -> bool:
    """Check if a URL points to a different domain."""
    domain = _extract_domain(url)
    if not domain:
        return False
    target = target_domain.lower()
    return domain != target and not domain.endswith(f".{target}")


def _extract_external_domains(html: str, page_url: str, target_domain: str) -> set[str]:
    """
    Extract external domains from HTML content.
    Finds all URLs via regex, resolves relative ones, and filters external.
    """
    domains: set[str] = set()

    # Extract from HTML attributes (src, href, etc.)
    for m in _URL_ATTR_RE.finditer(html):
        raw_url = m.group(1) or m.group(2)
        if not raw_url:
            continue
        # Skip data:, mailto:, javascript:, #anchors
        if raw_url.startswith(("data:", "mailto:", "javascript:", "tel:", "#")):
            continue
        # Resolve relative URLs
        try:
            full_url = urljoin(page_url, raw_url)
        except Exception:
            continue

        if _is_external(full_url, target_domain):
            domain = _extract_domain(full_url)
            if domain and "." in domain:
                domains.add(domain)

    # Extract URLs from JS strings
    for m in _JS_URL_RE.finditer(html):
        full_url = m.group(1)
        if _is_external(full_url, target_domain):
            domain = _extract_domain(full_url)
            if domain and "." in domain:
                domains.add(domain)

    return domains


async def _fetch_page(
    session: aiohttp.ClientSession,
    url: str,
    target_domain: str,
) -> PageResult:
    """Fetch a single page and extract external domains from it."""
    result = PageResult(url=url)
    try:
        async with session.get(url, allow_redirects=True, timeout=aiohttp.ClientTimeout(total=10)) as resp:
            result.status_code = resp.status
            content_type = resp.headers.get("Content-Type", "")

            if resp.status == 200 and "text/html" in content_type:
                html = await resp.text(errors="replace")
                result.has_content = bool(html.strip())
                result.content_hash = hashlib.md5(html.encode("utf-8", errors="replace")).hexdigest()
                result.external_domains = _extract_external_domains(html, url, target_domain)
            elif resp.status == 200:
                # Non-HTML (JS, JSON) — still hash it
                body = await resp.text(errors="replace")
                result.has_content = bool(body.strip())
                result.content_hash = hashlib.md5(body.encode("utf-8", errors="replace")).hexdigest()
            else:
                result.has_content = False
    except aiohttp.ClientError as e:
        result.error = str(e)
        logger.debug(f"Light scan fetch error for {url}: {e}")
    except Exception as e:
        result.error = str(e)
        logger.warning(f"Unexpected error fetching {url}: {e}")

    return result


async def run_light_scan(
    domain: str,
    key_pages: list[str] | None = None,
    auth_cookies: dict | None = None,
) -> LightScanOutput:
    """
    Run a light scan on the given domain.

    Args:
        domain: The target domain (e.g. "example.com")
        key_pages: List of relative paths to check. If None, uses defaults.
        auth_cookies: Optional dict of cookies for authenticated monitoring.

    Returns:
        LightScanOutput with aggregated hash, external domains, per-page data.
    """
    from .models import SiteMonitorConfig  # noqa: avoid circular at module level

    if key_pages is None:
        key_pages = list(SiteMonitorConfig.DEFAULT_KEY_PAGES)

    output = LightScanOutput(domain=domain)
    start = time.time()

    # Build full URLs
    base_https = f"https://{domain}"
    urls = []
    for page in key_pages:
        if page.startswith("http"):
            urls.append(page)
        else:
            path = page if page.startswith("/") else f"/{page}"
            urls.append(f"{base_https}{path}")

    # Add private entry points when authenticated
    if auth_cookies:
        private_paths = [
            "/admin/", "/dashboard/", "/account/", "/profile/",
            "/settings/", "/panel/", "/user/", "/my/",
        ]
        for path in private_paths:
            full_url = f"{base_https}{path}"
            if full_url not in urls:
                urls.append(full_url)

    connector = aiohttp.TCPConnector(limit=5, ssl=False)

    # Build session headers
    session_headers = {
        "User-Agent": "WScaner-Monitor/1.0 (+https://wscaner.dev)",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }

    # Build cookie jar from auth_cookies
    cookie_jar = aiohttp.CookieJar(unsafe=True)
    if auth_cookies:
        for k, v in auth_cookies.items():
            cookie_jar.update_cookies({k: v})

    try:
        async with aiohttp.ClientSession(
            connector=connector,
            headers=session_headers,
            cookie_jar=cookie_jar,
        ) as session:
            # Fetch all pages concurrently (limited to 5)
            import asyncio
            tasks = [_fetch_page(session, url, domain) for url in urls]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Aggregate hashes and domains
            hash_parts: list[str] = []
            for r in results:
                if isinstance(r, Exception):
                    logger.warning(f"Light scan page error: {r}")
                    continue
                if not isinstance(r, PageResult):
                    continue

                output.pages_checked += 1
                output.pages_data.append({
                    "url": r.url,
                    "status_code": r.status_code,
                    "hash": r.content_hash,
                    "has_content": r.has_content,
                    "error": r.error,
                })

                if r.content_hash:
                    hash_parts.append(r.content_hash)

                output.external_domains.update(r.external_domains)

            # Compute aggregated content hash
            if hash_parts:
                combined = "|".join(sorted(hash_parts))
                output.content_hash = hashlib.md5(combined.encode()).hexdigest()

    except Exception as e:
        output.error = str(e)
        logger.exception(f"Light scan failed for {domain}")

    output.duration = round(time.time() - start, 2)
    logger.info(
        f"Light scan {domain}: {output.pages_checked} pages, "
        f"{len(output.external_domains)} ext domains, "
        f"hash={output.content_hash[:12]}..., "
        f"{output.duration}s"
    )
    return output


def diff_domains(
    current: set[str] | list[str],
    previous: set[str] | list[str],
) -> tuple[list[str], list[str]]:
    """
    Compare current and previous domain sets.

    Returns:
        (new_domains, removed_domains)
    """
    current_set = set(current)
    previous_set = set(previous)
    new = sorted(current_set - previous_set)
    removed = sorted(previous_set - current_set)
    return new, removed
