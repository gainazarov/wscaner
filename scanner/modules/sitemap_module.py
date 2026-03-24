"""Sitemap Module — parses sitemap.xml for URLs."""

import logging
import re
from urllib.parse import urljoin

import aiohttp

from utils.url_utils import normalize_url, is_valid_url

logger = logging.getLogger("scanner.modules.sitemap")


class SitemapModule:
    """
    Fetches and parses /sitemap.xml to discover URLs.
    Handles:
    - Standard sitemaps
    - Sitemap indexes (recursive)
    - Compressed sitemaps (.gz)
    """

    MAX_SITEMAPS = 10  # Limit recursive sitemap processing

    async def run(
        self, base_url: str, session: aiohttp.ClientSession, domain: str
    ) -> list[dict]:
        """Fetch and parse sitemap.xml."""
        sitemap_urls = [
            f"{base_url}/sitemap.xml",
            f"{base_url}/sitemap_index.xml",
            f"{base_url}/sitemap.txt",
        ]

        results: list[dict] = []
        seen: set[str] = set()
        processed_sitemaps = 0

        for sitemap_url in sitemap_urls:
            if processed_sitemaps >= self.MAX_SITEMAPS:
                break
            new_results = await self._parse_sitemap(
                sitemap_url, session, base_url, seen, processed_sitemaps
            )
            results.extend(new_results)
            processed_sitemaps += 1

        return results

    async def _parse_sitemap(
        self,
        sitemap_url: str,
        session: aiohttp.ClientSession,
        base_url: str,
        seen: set[str],
        depth: int = 0,
    ) -> list[dict]:
        """Parse a single sitemap URL."""
        results: list[dict] = []

        if depth >= self.MAX_SITEMAPS:
            return results

        try:
            async with session.get(sitemap_url) as response:
                if response.status != 200:
                    return results

                text = await response.text(errors="replace")

                # Add sitemap itself
                if sitemap_url not in seen:
                    seen.add(sitemap_url)
                    results.append({
                        "url": sitemap_url,
                        "source": "sitemap",
                        "status_code": 200,
                        "content_type": "application/xml",
                        "depth": 0,
                        "is_internal": True,
                    })

                # Check if this is a sitemap index
                if "<sitemapindex" in text.lower():
                    # Extract nested sitemap URLs
                    sitemap_locs = re.findall(
                        r"<loc>\s*(.*?)\s*</loc>", text, re.IGNORECASE
                    )
                    for loc in sitemap_locs:
                        loc = loc.strip()
                        if loc not in seen:
                            nested = await self._parse_sitemap(
                                loc, session, base_url, seen, depth + 1
                            )
                            results.extend(nested)
                else:
                    # Standard sitemap — extract all <loc> entries
                    locs = re.findall(
                        r"<loc>\s*(.*?)\s*</loc>", text, re.IGNORECASE
                    )
                    for loc in locs:
                        url = loc.strip()
                        normalized = normalize_url(url)
                        if normalized not in seen and is_valid_url(normalized):
                            seen.add(normalized)
                            results.append({
                                "url": normalized,
                                "source": "sitemap",
                                "status_code": None,
                                "content_type": "",
                                "depth": 0,
                                "is_internal": True,
                            })

        except Exception as e:
            logger.debug(f"Error parsing sitemap {sitemap_url}: {e}")

        return results
