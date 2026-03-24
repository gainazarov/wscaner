"""HTML Module — extracts links from HTML tags."""

import logging
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from utils.url_utils import normalize_url, is_same_domain, is_valid_url

logger = logging.getLogger("scanner.modules.html")


class HTMLModule:
    """
    Extracts URLs from HTML elements:
    - <a href="...">
    - <link href="...">
    - <img src="...">
    - <script src="...">
    - <form action="...">
    - <iframe src="...">
    - <video src="..."> / <source src="...">
    - <area href="...">
    """

    # Tags and their URL attributes
    TAG_ATTRS = [
        ("a", "href"),
        ("link", "href"),
        ("img", "src"),
        ("script", "src"),
        ("form", "action"),
        ("iframe", "src"),
        ("video", "src"),
        ("source", "src"),
        ("area", "href"),
        ("embed", "src"),
        ("object", "data"),
    ]

    def extract(self, page_url: str, html: str, domain: str) -> list[str]:
        """Extract all URLs from HTML content."""
        if not html:
            return []

        links: list[str] = []

        try:
            soup = BeautifulSoup(html, "lxml")
        except Exception:
            try:
                soup = BeautifulSoup(html, "html.parser")
            except Exception:
                return []

        for tag_name, attr_name in self.TAG_ATTRS:
            for tag in soup.find_all(tag_name):
                value = tag.get(attr_name)
                if not value:
                    continue

                value = value.strip()

                # Skip anchors, javascript, mailto, tel
                if value.startswith(("#", "javascript:", "mailto:", "tel:", "data:")):
                    continue

                # Resolve relative URLs
                full_url = urljoin(page_url, value)
                normalized = normalize_url(full_url)

                if is_valid_url(normalized):
                    links.append(normalized)

        # Also extract URLs from meta refresh tags
        for meta in soup.find_all("meta"):
            http_equiv = meta.get("http-equiv", "").lower()
            if http_equiv == "refresh":
                content = meta.get("content", "")
                if "url=" in content.lower():
                    url_part = content.split("url=", 1)[-1].strip().strip("'\"")
                    full_url = urljoin(page_url, url_part)
                    normalized = normalize_url(full_url)
                    if is_valid_url(normalized):
                        links.append(normalized)

        return links
