"""JS Module — extracts API endpoints and URLs from JavaScript."""

import logging
import re

from urllib.parse import urljoin

from utils.url_utils import normalize_url, is_valid_url

logger = logging.getLogger("scanner.modules.js")


class JSModule:
    """
    Extracts URLs from JavaScript code:
    - fetch() calls
    - axios calls
    - XMLHttpRequest
    - API endpoint strings
    - URL patterns in string literals
    """

    # Regex patterns for URL extraction from JS
    PATTERNS = [
        # fetch("url") or fetch('url')
        re.compile(r"""fetch\s*\(\s*['"]([^'"]+)['"]""", re.IGNORECASE),
        # axios.get("url"), axios.post("url"), etc.
        re.compile(r"""axios\.\w+\s*\(\s*['"]([^'"]+)['"]""", re.IGNORECASE),
        # $.ajax({url: "..."})
        re.compile(r"""url\s*:\s*['"]([^'"]+)['"]""", re.IGNORECASE),
        # XMLHttpRequest .open("METHOD", "url")
        re.compile(r"""\.open\s*\(\s*['"][A-Z]+['"]\s*,\s*['"]([^'"]+)['"]""", re.IGNORECASE),
        # window.location = "url" or window.location.href = "url"
        re.compile(r"""(?:window\.)?location(?:\.href)?\s*=\s*['"]([^'"]+)['"]""", re.IGNORECASE),
        # Generic URL-like strings in JS: "/api/...", "/path/..."
        re.compile(r"""['"](/(?:api|v[0-9]|rest|graphql|auth|admin|user|dashboard|search)[/\w.-]*?)['"]""", re.IGNORECASE),
        # Full URLs in strings
        re.compile(r"""['"]((https?://[^'"{\s]+))['"]""", re.IGNORECASE),
        # Router paths: path: "/..."
        re.compile(r"""path\s*:\s*['"](/[^'"]+)['"]""", re.IGNORECASE),
        # href in JS
        re.compile(r"""href\s*=\s*['"]([^'"]+)['"]""", re.IGNORECASE),
    ]

    def extract(self, page_url: str, html: str, domain: str) -> list[str]:
        """Extract URLs from JavaScript content."""
        if not html:
            return []

        links: list[str] = []
        seen: set[str] = set()

        for pattern in self.PATTERNS:
            for match in pattern.finditer(html):
                url = match.group(1).strip()

                # Skip common false positives
                if self._is_false_positive(url):
                    continue

                # Resolve relative URLs
                if url.startswith("/"):
                    full_url = urljoin(page_url, url)
                elif url.startswith("http"):
                    full_url = url
                else:
                    continue

                normalized = normalize_url(full_url)
                if normalized not in seen and is_valid_url(normalized):
                    seen.add(normalized)
                    links.append(normalized)

        return links

    @staticmethod
    def _is_false_positive(url: str) -> bool:
        """Filter out common false positives from JS parsing."""
        if not url or len(url) < 2:
            return True

        # Skip template literals and variables
        if any(c in url for c in ["${", "{{", "}}", "+", "\\n", "\\t"]):
            return True

        # Skip common non-URL patterns
        false_patterns = [
            "application/json",
            "text/html",
            "text/css",
            "image/",
            "font/",
            "multipart/",
            "charset=",
        ]
        for pattern in false_patterns:
            if pattern in url.lower():
                return True

        return False
