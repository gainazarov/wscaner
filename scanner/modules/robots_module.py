"""Robots Module — parses robots.txt for URLs."""

import logging
from urllib.parse import urljoin

import aiohttp

from utils.url_utils import normalize_url, is_valid_url

logger = logging.getLogger("scanner.modules.robots")


class RobotsModule:
    """
    Fetches and parses /robots.txt to discover:
    - Allow paths
    - Disallow paths (often hidden/interesting)
    - Sitemap references
    """

    async def run(
        self, base_url: str, session: aiohttp.ClientSession, domain: str
    ) -> list[dict]:
        """Fetch and parse robots.txt."""
        robots_url = f"{base_url}/robots.txt"
        results: list[dict] = []

        try:
            async with session.get(robots_url) as response:
                if response.status != 200:
                    logger.debug(f"robots.txt not found at {robots_url}")
                    return results

                text = await response.text(errors="replace")

                # Add robots.txt itself
                results.append({
                    "url": robots_url,
                    "source": "robots",
                    "status_code": 200,
                    "content_type": "text/plain",
                    "depth": 0,
                    "is_internal": True,
                })

                seen: set[str] = set()

                for line in text.splitlines():
                    line = line.strip()

                    # Skip comments and empty lines
                    if not line or line.startswith("#"):
                        continue

                    parts = line.split(":", 1)
                    if len(parts) != 2:
                        continue

                    directive = parts[0].strip().lower()
                    value = parts[1].strip()

                    if directive in ("allow", "disallow") and value:
                        # Remove wildcard characters for URL construction
                        clean_path = value.replace("*", "").replace("$", "")
                        if clean_path and clean_path != "/":
                            full_url = urljoin(base_url, clean_path)
                            normalized = normalize_url(full_url)
                            if normalized not in seen and is_valid_url(normalized):
                                seen.add(normalized)
                                results.append({
                                    "url": normalized,
                                    "source": "robots",
                                    "status_code": None,
                                    "content_type": "",
                                    "depth": 0,
                                    "is_internal": True,
                                })

                    elif directive == "sitemap" and value:
                        normalized = normalize_url(value)
                        if normalized not in seen and is_valid_url(normalized):
                            seen.add(normalized)
                            results.append({
                                "url": normalized,
                                "source": "robots",
                                "status_code": None,
                                "content_type": "",
                                "depth": 0,
                                "is_internal": True,
                            })

        except Exception as e:
            logger.warning(f"Error fetching robots.txt: {e}")

        return results
