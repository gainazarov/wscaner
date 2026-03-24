"""URL utility functions for normalization, validation, and filtering."""

from urllib.parse import urlparse, urlunparse, urljoin, parse_qs, urlencode
import re


# Extensions to skip (binary files, etc.)
SKIP_EXTENSIONS = {
    ".jpg", ".jpeg", ".png", ".gif", ".svg", ".webp", ".bmp", ".ico",
    ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
    ".zip", ".rar", ".tar", ".gz", ".7z",
    ".mp3", ".mp4", ".avi", ".mov", ".wmv", ".flv", ".webm",
    ".woff", ".woff2", ".ttf", ".eot", ".otf",
    ".exe", ".dmg", ".msi", ".apk",
    ".css",
}


def normalize_url(url: str) -> str:
    """
    Normalize a URL:
    - Lowercase scheme and host
    - Remove default ports
    - Remove fragment
    - Remove trailing slash (except for root)
    - Sort query parameters
    """
    if not url:
        return ""

    try:
        parsed = urlparse(url)

        # Lowercase scheme and host
        scheme = parsed.scheme.lower() or "https"
        netloc = parsed.netloc.lower()

        # Remove default ports
        if netloc.endswith(":80") and scheme == "http":
            netloc = netloc[:-3]
        elif netloc.endswith(":443") and scheme == "https":
            netloc = netloc[:-4]

        # Clean path
        path = parsed.path or "/"
        # Remove trailing slash (but keep root /)
        if path != "/" and path.endswith("/"):
            path = path.rstrip("/")

        # Sort query parameters for consistency
        query = ""
        if parsed.query:
            params = parse_qs(parsed.query, keep_blank_values=True)
            sorted_params = sorted(params.items())
            query = urlencode(sorted_params, doseq=True)

        # Remove fragment
        return urlunparse((scheme, netloc, path, parsed.params, query, ""))
    except Exception:
        return url


def is_same_domain(url: str, domain: str) -> bool:
    """Check if a URL belongs to the same domain (including subdomains)."""
    try:
        parsed = urlparse(url)
        url_domain = parsed.netloc.lower()
        domain = domain.lower()

        # Remove port from comparison
        url_domain = url_domain.split(":")[0]
        domain = domain.split(":")[0]

        # Exact match or subdomain match
        return url_domain == domain or url_domain.endswith(f".{domain}")
    except Exception:
        return False


def is_valid_url(url: str) -> bool:
    """Check if a URL is valid and worth visiting."""
    if not url:
        return False

    try:
        parsed = urlparse(url)

        # Must have scheme and host
        if not parsed.scheme or not parsed.netloc:
            return False

        # Only http/https
        if parsed.scheme not in ("http", "https"):
            return False

        # Check for skip extensions
        path_lower = parsed.path.lower()
        for ext in SKIP_EXTENSIONS:
            if path_lower.endswith(ext):
                return False

        # Skip very long URLs (likely garbage)
        if len(url) > 2000:
            return False

        return True
    except Exception:
        return False


def extract_domain(url: str) -> str:
    """Extract the domain from a URL (without port)."""
    try:
        parsed = urlparse(url)
        return parsed.netloc.lower().split(":")[0]
    except Exception:
        return ""


def get_root_domain(domain: str) -> str:
    """
    Get the root domain from a hostname.
    e.g. 'api.example.com' -> 'example.com'
    """
    parts = domain.split(".")
    if len(parts) <= 2:
        return domain
    # Handle TLDs like .co.uk
    known_multi_tlds = {"co.uk", "com.au", "co.jp", "co.kr", "co.in", "com.br"}
    if len(parts) >= 3:
        possible_tld = f"{parts[-2]}.{parts[-1]}"
        if possible_tld in known_multi_tlds:
            return ".".join(parts[-3:])
    return ".".join(parts[-2:])


def is_external(url: str, main_domain: str) -> bool:
    """
    Check if a URL is external to the main domain.
    Subdomains are considered INTERNAL.
    """
    url_domain = extract_domain(url)
    if not url_domain:
        return False
    main_domain = main_domain.lower().split(":")[0]
    # Exact match
    if url_domain == main_domain:
        return False
    # Subdomain match (api.example.com is internal to example.com)
    if url_domain.endswith(f".{main_domain}"):
        return False
    # Check root domain match
    url_root = get_root_domain(url_domain)
    main_root = get_root_domain(main_domain)
    if url_root == main_root:
        return False
    return True


def make_absolute(url: str, base_url: str) -> str:
    """Convert a relative URL to absolute."""
    if not url:
        return ""
    if url.startswith(("http://", "https://")):
        return url
    return urljoin(base_url, url)
