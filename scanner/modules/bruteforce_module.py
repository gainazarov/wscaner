"""Bruteforce Module — tries common paths to discover hidden pages."""

import logging
from urllib.parse import urljoin

import aiohttp

from utils.url_utils import normalize_url

logger = logging.getLogger("scanner.modules.bruteforce")


class BruteforceModule:
    """
    Tries common directory and file paths to discover hidden pages.
    """

    COMMON_PATHS = [
        # Admin panels
        "/admin",
        "/admin/",
        "/administrator",
        "/wp-admin",
        "/wp-login.php",
        "/cpanel",
        "/dashboard",
        "/panel",
        "/manage",
        "/management",
        # API endpoints
        "/api",
        "/api/",
        "/api/v1",
        "/api/v2",
        "/api/v3",
        "/rest",
        "/graphql",
        "/api-docs",
        "/swagger",
        "/swagger-ui",
        "/swagger.json",
        "/openapi.json",
        "/docs",
        # Development & Debug
        "/dev",
        "/debug",
        "/test",
        "/staging",
        "/beta",
        "/internal",
        "/phpinfo.php",
        "/info.php",
        "/.env",
        "/config",
        "/configuration",
        # Auth
        "/login",
        "/signin",
        "/signup",
        "/register",
        "/auth",
        "/oauth",
        "/sso",
        "/logout",
        "/forgot-password",
        "/reset-password",
        # Common pages
        "/about",
        "/contact",
        "/terms",
        "/privacy",
        "/faq",
        "/help",
        "/support",
        "/status",
        "/health",
        "/healthcheck",
        "/ping",
        "/version",
        # Files
        "/robots.txt",
        "/sitemap.xml",
        "/humans.txt",
        "/security.txt",
        "/.well-known/security.txt",
        "/crossdomain.xml",
        "/favicon.ico",
        "/manifest.json",
        "/browserconfig.xml",
        # Git / VCS
        "/.git",
        "/.git/config",
        "/.svn",
        "/.hg",
        # Backups
        "/backup",
        "/backups",
        "/db",
        "/database",
        "/dump",
        "/sql",
        # Search & Feed
        "/search",
        "/feed",
        "/rss",
        "/atom.xml",
        "/rss.xml",
        # User content
        "/uploads",
        "/files",
        "/media",
        "/assets",
        "/static",
        "/public",
        "/images",
        "/img",
        "/css",
        "/js",
        # CMS specific
        "/wp-content",
        "/wp-includes",
        "/wp-json",
        "/wp-json/wp/v2/posts",
        "/xmlrpc.php",
        # Server info
        "/server-status",
        "/server-info",
        "/.htaccess",
        "/web.config",
        "/nginx.conf",
    ]

    CONCURRENCY = 3  # Low concurrency to avoid rate limiting

    async def run(
        self, base_url: str, session: aiohttp.ClientSession, domain: str
    ) -> list[dict]:
        """Try all common paths and report what exists."""
        import random
        results: list[dict] = []
        seen: set[str] = set()

        import asyncio

        semaphore = asyncio.Semaphore(self.CONCURRENCY)

        async def check_path(path: str):
            url = urljoin(base_url, path)
            normalized = normalize_url(url)
            if normalized in seen:
                return None
            seen.add(normalized)

            async with semaphore:
                # Random delay between requests to avoid detection
                await asyncio.sleep(random.uniform(0.2, 1.0))
                try:
                    async with session.get(
                        url,
                        allow_redirects=False,
                        timeout=aiohttp.ClientTimeout(total=8),
                    ) as response:
                        status_code = response.status
                        content_type = response.headers.get("Content-Type", "")

                        # Consider it found if status is not 404
                        if status_code not in (404, 403, 410, 500, 502, 503):
                            return {
                                "url": normalized,
                                "source": "bruteforce",
                                "status_code": status_code,
                                "content_type": content_type.split(";")[0].strip(),
                                "depth": 0,
                                "is_internal": True,
                            }
                        # Also include 403 as it means the path exists but is forbidden
                        elif status_code == 403:
                            return {
                                "url": normalized,
                                "source": "bruteforce",
                                "status_code": status_code,
                                "content_type": content_type.split(";")[0].strip(),
                                "depth": 0,
                                "is_internal": True,
                            }

                except Exception:
                    pass
            return None

        tasks = [check_path(path) for path in self.COMMON_PATHS]
        check_results = await asyncio.gather(*tasks)

        for result in check_results:
            if result is not None:
                results.append(result)

        logger.info(f"Bruteforce found {len(results)} paths on {domain}")
        return results
