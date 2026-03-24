"""Models for the scans app."""

import base64
import os

from django.db import models
from django.utils import timezone


# ─── Encryption helpers (AES-like via Fernet) ───────────────────────────────

def _get_fernet():
    """Get Fernet cipher using DJANGO_SECRET_KEY-derived key."""
    from cryptography.fernet import Fernet
    from django.conf import settings
    import hashlib
    key = hashlib.sha256(settings.SECRET_KEY.encode()).digest()
    return Fernet(base64.urlsafe_b64encode(key))


def encrypt_value(plaintext: str) -> str:
    """Encrypt a string, return base64 ciphertext."""
    if not plaintext:
        return ""
    f = _get_fernet()
    return f.encrypt(plaintext.encode()).decode()


def decrypt_value(ciphertext: str) -> str:
    """Decrypt a base64 ciphertext back to string."""
    if not ciphertext:
        return ""
    f = _get_fernet()
    return f.decrypt(ciphertext.encode()).decode()


class Scan(models.Model):
    """Represents a scan job for a domain."""

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        RUNNING = "running", "Running"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"

    domain = models.CharField(max_length=255, db_index=True)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDING, db_index=True
    )
    total_urls = models.IntegerField(default=0)
    new_urls = models.IntegerField(default=0)
    internal_urls = models.IntegerField(default=0)
    external_urls = models.IntegerField(default=0)
    hidden_urls = models.IntegerField(default=0)
    error_urls = models.IntegerField(default=0)
    private_urls = models.IntegerField(default=0)
    max_depth = models.IntegerField(default=3)
    max_pages = models.IntegerField(default=500)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(blank=True, default="")
    # Auth integration fields
    auth_success = models.BooleanField(null=True, blank=True, default=None)
    auth_method = models.CharField(max_length=50, blank=True, default="")
    auth_error = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Scan #{self.id} — {self.domain} [{self.status}]"

    @property
    def duration_seconds(self):
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None

    def mark_running(self):
        self.status = self.Status.RUNNING
        self.started_at = timezone.now()
        self.save(update_fields=["status", "started_at", "updated_at"])

    def mark_completed(self, total_urls=0, new_urls=0):
        self.status = self.Status.COMPLETED
        self.completed_at = timezone.now()
        self.total_urls = total_urls
        self.new_urls = new_urls
        # Compute extra stats from discovered URLs
        self.internal_urls = self.urls.filter(is_internal=True).count()
        self.external_urls = self.urls.filter(is_internal=False).count()
        self.hidden_urls = self.urls.filter(status_code=403).count()
        self.error_urls = self.urls.filter(
            status_code__isnull=False, status_code__gte=400
        ).count()
        self.private_urls = self.urls.filter(is_private=True).count()
        self.save(
            update_fields=[
                "status",
                "completed_at",
                "total_urls",
                "new_urls",
                "internal_urls",
                "external_urls",
                "hidden_urls",
                "error_urls",
                "private_urls",
                "updated_at",
            ]
        )

    def mark_failed(self, error_message=""):
        self.status = self.Status.FAILED
        self.completed_at = timezone.now()
        self.error_message = error_message
        self.save(
            update_fields=["status", "completed_at", "error_message", "updated_at"]
        )


class DiscoveredURL(models.Model):
    """A URL discovered during scanning."""

    class Source(models.TextChoices):
        HTML = "html", "HTML Link"
        JS = "js", "JavaScript"
        ROBOTS = "robots", "robots.txt"
        SITEMAP = "sitemap", "sitemap.xml"
        BRUTEFORCE = "bruteforce", "Bruteforce"

    scan = models.ForeignKey(Scan, on_delete=models.CASCADE, related_name="urls")
    url = models.URLField(max_length=2048, db_index=True)
    source = models.CharField(
        max_length=20, choices=Source.choices, default=Source.HTML
    )
    status_code = models.IntegerField(null=True, blank=True)
    content_type = models.CharField(max_length=255, blank=True, default="")
    depth = models.IntegerField(default=0)
    is_internal = models.BooleanField(default=True, db_index=True)
    is_new = models.BooleanField(default=False)
    external_domain = models.CharField(
        max_length=255, blank=True, default="", db_index=True,
        help_text="For external URLs, the domain they point to"
    )
    source_url = models.URLField(
        max_length=2048, blank=True, default="",
        help_text="The page where this URL was discovered"
    )
    is_private = models.BooleanField(
        default=False, db_index=True,
        help_text="True if this URL was discovered via authenticated scanning"
    )
    is_sensitive = models.BooleanField(
        default=False, db_index=True,
        help_text="True if URL matches sensitive page patterns (/admin, /settings, /billing, etc.)"
    )
    first_seen = models.DateTimeField(auto_now_add=True)
    last_seen = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-first_seen"]
        unique_together = ["scan", "url"]
        indexes = [
            models.Index(fields=["scan", "is_new"]),
            models.Index(fields=["scan", "source"]),
            models.Index(fields=["scan", "is_internal"]),
            models.Index(fields=["scan", "status_code"]),
            models.Index(fields=["scan", "external_domain"]),
        ]

    def __str__(self):
        return f"{self.url} ({self.source})"

    @property
    def is_hidden(self):
        return self.status_code == 403

    @property
    def is_error(self):
        return self.status_code is not None and self.status_code >= 400

    @property
    def status_category(self):
        if self.status_code is None:
            return "unknown"
        if 200 <= self.status_code < 300:
            return "success"
        if 300 <= self.status_code < 400:
            return "redirect"
        if self.status_code == 403:
            return "hidden"
        if 400 <= self.status_code < 500:
            return "client_error"
        if self.status_code >= 500:
            return "server_error"
        return "unknown"


class ScanDiff(models.Model):
    """Tracks differences between scans for the same domain."""

    current_scan = models.ForeignKey(
        Scan, on_delete=models.CASCADE, related_name="diffs_as_current"
    )
    previous_scan = models.ForeignKey(
        Scan, on_delete=models.CASCADE, related_name="diffs_as_previous"
    )
    new_urls_count = models.IntegerField(default=0)
    removed_urls_count = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Diff: Scan #{self.current_scan_id} vs #{self.previous_scan_id}"


class DiffURL(models.Model):
    """Individual URL that appeared or disappeared between scans."""

    class ChangeType(models.TextChoices):
        ADDED = "added", "Added"
        REMOVED = "removed", "Removed"

    diff = models.ForeignKey(ScanDiff, on_delete=models.CASCADE, related_name="diff_urls")
    url = models.URLField(max_length=2048)
    change_type = models.CharField(max_length=10, choices=ChangeType.choices)

    def __str__(self):
        return f"[{self.change_type}] {self.url}"


# ─── External Domain Monitoring ─────────────────────────────────────────────

SUSPICIOUS_TLDS = {
    "xyz", "top", "cc", "tk", "ml", "ga", "cf", "gq", "pw",
    "buzz", "club", "icu", "cam", "bid", "loan", "win", "racing",
    "download", "stream", "click", "link", "gdn", "men", "work",
}

SUSPICIOUS_KEYWORDS = [
    "login", "secure", "verify", "account", "update", "confirm",
    "banking", "paypal", "crypto", "wallet", "free-money", "prize",
    "alert", "suspend", "urgent", "password", "credential",
]


def normalize_domain(domain: str) -> str:
    """Normalize a domain: strip www., m., mobile. prefixes."""
    domain = domain.lower().strip()
    for prefix in ("www.", "m.", "mobile.", "ww.", "ww2.", "ww3."):
        if domain.startswith(prefix):
            domain = domain[len(prefix):]
    return domain


def check_suspicious(domain: str) -> tuple[bool, list[str]]:
    """Check if a domain is suspicious. Returns (is_suspicious, reasons)."""
    reasons = []
    normalized = normalize_domain(domain)

    # Check TLD
    tld = normalized.rsplit(".", 1)[-1] if "." in normalized else ""
    if tld in SUSPICIOUS_TLDS:
        reasons.append(f"suspicious TLD: .{tld}")

    # Check length
    if len(normalized) > 30:
        reasons.append(f"very long domain ({len(normalized)} chars)")

    # Check suspicious keywords
    for kw in SUSPICIOUS_KEYWORDS:
        if kw in normalized:
            reasons.append(f"suspicious keyword: {kw}")
            break  # one keyword match is enough

    # Check excessive hyphens
    if normalized.count("-") >= 3:
        reasons.append(f"excessive hyphens ({normalized.count('-')})")

    # Check if looks like IP address
    import re
    if re.match(r"^\d+\.\d+\.\d+\.\d+$", normalized):
        reasons.append("IP address instead of domain")

    return bool(reasons), reasons


class ExternalDomainEntry(models.Model):
    """Tracks external domains discovered across scans for a given site."""

    class Status(models.TextChoices):
        SAFE = "safe", "Safe"
        SUSPICIOUS = "suspicious", "Suspicious"
        NEW = "new", "New"

    class ListClassification(models.TextChoices):
        WHITELIST = "whitelist", "Whitelist"
        BLACKLIST = "blacklist", "Blacklist"
        UNKNOWN = "unknown", "Unknown"

    # Which site this external domain was found on
    site_domain = models.CharField(max_length=255, db_index=True)
    domain = models.CharField(max_length=255, db_index=True)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.NEW
    )
    list_classification = models.CharField(
        max_length=10,
        choices=ListClassification.choices,
        default=ListClassification.UNKNOWN,
        db_index=True,
        help_text="Classification based on whitelist/blacklist",
    )
    is_suspicious = models.BooleanField(default=False)
    suspicious_reasons = models.JSONField(default=list, blank=True)
    first_seen_scan = models.ForeignKey(
        Scan, on_delete=models.SET_NULL, null=True, related_name="first_seen_domains"
    )
    last_seen_scan = models.ForeignKey(
        Scan, on_delete=models.SET_NULL, null=True, related_name="last_seen_domains"
    )
    first_seen = models.DateTimeField(auto_now_add=True)
    last_seen = models.DateTimeField(auto_now=True)
    times_seen = models.IntegerField(default=1)

    # Pages where this domain was found (stored as JSON list)
    found_on_pages = models.JSONField(default=list, blank=True)

    class Meta:
        ordering = ["-last_seen"]
        unique_together = ["site_domain", "domain"]
        indexes = [
            models.Index(
                fields=["site_domain", "is_suspicious"],
                name="scans_exter_site_do_susp_idx",
            ),
            models.Index(
                fields=["site_domain", "status"],
                name="scans_exter_site_do_stat_idx",
            ),
        ]

    def __str__(self):
        flag = "⚠️" if self.is_suspicious else "✅"
        return f"{flag} {self.domain} (on {self.site_domain})"


# ─── Blacklist / Whitelist System ────────────────────────────────────────────


class DomainListEntry(models.Model):
    """
    Per-site whitelist / blacklist entry.
    Blacklist has priority over whitelist if a domain appears in both.
    """

    class ListType(models.TextChoices):
        WHITELIST = "whitelist", "Whitelist"
        BLACKLIST = "blacklist", "Blacklist"

    site_domain = models.CharField(max_length=255, db_index=True)
    domain = models.CharField(
        max_length=255, db_index=True,
        help_text="External domain pattern, e.g. google.com",
    )
    list_type = models.CharField(
        max_length=10, choices=ListType.choices, db_index=True,
    )
    note = models.TextField(
        blank=True, default="",
        help_text="Optional reason / comment",
    )
    added_by = models.CharField(
        max_length=50, default="user",
        help_text="Who added: user | auto-suggest",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["domain"]
        unique_together = ["site_domain", "domain", "list_type"]
        verbose_name = "Domain List Entry"
        verbose_name_plural = "Domain List Entries"
        indexes = [
            models.Index(
                fields=["site_domain", "list_type"],
                name="scans_domlist_site_type_idx",
            ),
        ]

    def __str__(self):
        icon = "🟢" if self.list_type == "whitelist" else "🔴"
        return f"{icon} {self.domain} ({self.list_type}) on {self.site_domain}"

    @staticmethod
    def classify_domain(site_domain: str, ext_domain: str) -> str:
        """
        Classify an external domain against the lists.
        Returns: 'whitelist' | 'blacklist' | 'unknown'.
        Blacklist takes priority.
        """
        normalized = normalize_domain(ext_domain)
        # Blacklist priority
        if DomainListEntry.objects.filter(
            site_domain=site_domain,
            domain=normalized,
            list_type=DomainListEntry.ListType.BLACKLIST,
        ).exists():
            return "blacklist"
        if DomainListEntry.objects.filter(
            site_domain=site_domain,
            domain=normalized,
            list_type=DomainListEntry.ListType.WHITELIST,
        ).exists():
            return "whitelist"
        return "unknown"

    @staticmethod
    def classify_domains_bulk(site_domain: str, ext_domains: list[str]) -> dict[str, str]:
        """
        Classify many domains at once (efficient DB access).
        Returns dict: { domain: 'whitelist'|'blacklist'|'unknown' }
        """
        normalized_map = {normalize_domain(d): d for d in ext_domains}
        norm_list = list(normalized_map.keys())

        blacklisted = set(
            DomainListEntry.objects.filter(
                site_domain=site_domain,
                domain__in=norm_list,
                list_type=DomainListEntry.ListType.BLACKLIST,
            ).values_list("domain", flat=True)
        )
        whitelisted = set(
            DomainListEntry.objects.filter(
                site_domain=site_domain,
                domain__in=norm_list,
                list_type=DomainListEntry.ListType.WHITELIST,
            ).values_list("domain", flat=True)
        )

        result = {}
        for norm, orig in normalized_map.items():
            if norm in blacklisted:
                result[orig] = "blacklist"
            elif norm in whitelisted:
                result[orig] = "whitelist"
            else:
                result[orig] = "unknown"
        return result


class ExternalDomainAlert(models.Model):
    """Alert generated when new/suspicious external domains are detected."""

    class AlertType(models.TextChoices):
        NEW_DOMAIN = "new_domain", "New External Domain"
        SUSPICIOUS_DOMAIN = "suspicious_domain", "Suspicious Domain"
        REMOVED_DOMAIN = "removed_domain", "Domain Removed"
        CONTENT_CHANGE = "content_change", "Content Changed"
        DOMAIN_REMOVED = "domain_removed", "Domain No Longer Found"
        BLACKLIST_HIT = "blacklist_hit", "Blacklisted Domain Found"
        AUTH_FAILED = "auth_failed", "Authentication Failed"
        SESSION_EXPIRED = "session_expired", "Session Expired"
        NEW_PRIVATE_PAGE = "new_private_page", "New Private Page Discovered"

    class Severity(models.TextChoices):
        INFO = "info", "Info"
        WARNING = "warning", "Warning"
        CRITICAL = "critical", "Critical"

    scan = models.ForeignKey(
        Scan, on_delete=models.CASCADE, related_name="alerts",
        null=True, blank=True,
    )
    site_domain = models.CharField(max_length=255, db_index=True)
    external_domain = models.CharField(max_length=255, blank=True, default="")
    alert_type = models.CharField(
        max_length=30, choices=AlertType.choices
    )
    severity = models.CharField(
        max_length=10, choices=Severity.choices, default=Severity.INFO
    )
    message = models.TextField()
    domain_list = models.JSONField(
        default=list, blank=True,
        help_text="List of domains related to this alert",
    )
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(
                fields=["site_domain", "-created_at"],
                name="scans_alert_site_date_idx",
            ),
            models.Index(fields=["is_read"], name="scans_alert_is_read_idx"),
        ]

    def __str__(self):
        return f"[{self.severity}] {self.alert_type}: {self.external_domain}"


class DomainReputation(models.Model):
    """Cached domain reputation from Safe Browsing and VirusTotal."""

    class RiskLevel(models.TextChoices):
        LOW = "low", "Low"
        MEDIUM = "medium", "Medium"
        HIGH = "high", "High"
        UNKNOWN = "unknown", "Unknown"

    class CheckStatus(models.TextChoices):
        PENDING = "pending", "Pending"
        CHECKING = "checking", "Checking"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"

    domain = models.CharField(max_length=255, unique=True, db_index=True)
    risk_level = models.CharField(
        max_length=10, choices=RiskLevel.choices, default=RiskLevel.UNKNOWN
    )
    check_status = models.CharField(
        max_length=10, choices=CheckStatus.choices, default=CheckStatus.PENDING
    )

    safe_browsing_result = models.JSONField(
        default=dict,
        blank=True,
        help_text="Google Safe Browsing API response data",
    )
    safe_browsing_risk = models.CharField(
        max_length=10, choices=RiskLevel.choices, default=RiskLevel.UNKNOWN
    )

    virustotal_stats = models.JSONField(
        default=dict,
        blank=True,
        help_text="VirusTotal analysis statistics",
    )
    virustotal_risk = models.CharField(
        max_length=10, choices=RiskLevel.choices, default=RiskLevel.UNKNOWN
    )
    virustotal_malicious = models.IntegerField(default=0)
    virustotal_suspicious = models.IntegerField(default=0)
    virustotal_harmless = models.IntegerField(default=0)
    virustotal_undetected = models.IntegerField(default=0)

    checked_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(blank=True, default="")
    check_count = models.IntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-checked_at"]
        indexes = [
            models.Index(
                fields=["risk_level"],
                name="scans_domai_risk_le_c2b5ec_idx",
            ),
            models.Index(
                fields=["check_status"],
                name="scans_domai_check_s_e87d64_idx",
            ),
            models.Index(
                fields=["checked_at"],
                name="scans_domai_checked_d7312a_idx",
            ),
        ]

    def __str__(self):
        return f"{self.domain} [{self.risk_level}]"


# ─── Real-Time Monitoring Models ─────────────────────────────────────────────

class SiteMonitorConfig(models.Model):
    """
    Per-site configuration for the real-time monitoring system.
    Each monitored domain gets one config row controlling
    interval, enabled state, key pages to probe, and content hash.
    """

    domain = models.CharField(max_length=255, unique=True, db_index=True)
    is_enabled = models.BooleanField(default=True)
    interval_minutes = models.PositiveIntegerField(
        default=15,
        help_text="How often (minutes) to run a light scan",
    )
    key_pages = models.JSONField(
        default=list,
        blank=True,
        help_text='Relative paths to monitor, e.g. ["/","/login","/checkout"]',
    )
    last_content_hash = models.CharField(
        max_length=64, blank=True, default="",
        help_text="MD5 hash of aggregated key-page content from last scan",
    )
    last_scan_at = models.DateTimeField(null=True, blank=True)
    next_scan_at = models.DateTimeField(null=True, blank=True)
    total_light_scans = models.PositiveIntegerField(default=0)
    changes_detected_count = models.PositiveIntegerField(default=0)
    consecutive_errors = models.PositiveIntegerField(default=0)
    last_error = models.TextField(blank=True, default="")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]
        verbose_name = "Site Monitor Config"
        verbose_name_plural = "Site Monitor Configs"

    def __str__(self):
        state = "ON" if self.is_enabled else "OFF"
        return f"{self.domain} [{state}, every {self.interval_minutes}m]"

    @property
    def is_due(self):
        """True if next_scan_at is in the past or null."""
        if not self.is_enabled:
            return False
        if self.next_scan_at is None:
            return True
        from django.utils import timezone
        return timezone.now() >= self.next_scan_at

    DEFAULT_KEY_PAGES = [
        "/",
        "/index.html",
        "/login",
        "/checkout",
        "/cart",
        "/account",
        "/payment",
    ]


class LightScanResult(models.Model):
    """
    Result of a single light-scan cycle for a monitored site.
    Stores content hash, change detection, and external domain diff.
    """

    site_config = models.ForeignKey(
        SiteMonitorConfig,
        on_delete=models.CASCADE,
        related_name="light_scan_results",
    )
    content_hash = models.CharField(max_length=64, blank=True, default="")
    previous_hash = models.CharField(max_length=64, blank=True, default="")
    has_changes = models.BooleanField(default=False)
    pages_checked = models.PositiveIntegerField(default=0)
    pages_data = models.JSONField(
        default=list, blank=True,
        help_text="Per-page status: [{url, status_code, hash, has_content}]",
    )
    external_domains_snapshot = models.JSONField(
        default=list, blank=True,
        help_text="All external domains found in this scan",
    )
    new_domains = models.JSONField(
        default=list, blank=True,
        help_text="Domains found in this scan but not in previous",
    )
    removed_domains = models.JSONField(
        default=list, blank=True,
        help_text="Domains in previous scan but not in this one",
    )
    new_domains_count = models.PositiveIntegerField(default=0)
    removed_domains_count = models.PositiveIntegerField(default=0)
    reputation_enqueued = models.BooleanField(
        default=False,
        help_text="Whether new domains were sent to the reputation queue",
    )
    scan_duration = models.FloatField(
        default=0.0, help_text="Scan duration in seconds"
    )
    error = models.TextField(blank=True, default="")

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Light Scan Result"
        indexes = [
            models.Index(fields=["site_config", "-created_at"]),
            models.Index(fields=["has_changes"]),
        ]

    def __str__(self):
        status = "CHANGED" if self.has_changes else "no change"
        return (
            f"LightScan {self.site_config.domain} "
            f"[{status}, +{self.new_domains_count}/-{self.removed_domains_count}]"
        )


# ─── Authenticated Scanning ─────────────────────────────────────────────────


class SiteAuthConfig(models.Model):
    """
    Per-site authentication configuration for scanning private pages.
    Supports form-based login and direct cookie injection.
    """

    class AuthType(models.TextChoices):
        NONE = "none", "None"
        FORM = "form", "Form Login"
        COOKIE = "cookie", "Cookie"
        INTERACTIVE = "interactive", "Interactive Login"
        RECORDED = "recorded", "Recorded Flow"

    class AuthStatus(models.TextChoices):
        UNTESTED = "untested", "Not Tested"
        SUCCESS = "success", "Login Successful"
        FAILED = "failed", "Login Failed"

    class AuthStrategy(models.TextChoices):
        AUTO = "auto", "Auto (HTTP → Browser fallback)"
        HTTP_ONLY = "http_only", "HTTP Only"
        PLAYWRIGHT_ONLY = "playwright_only", "Browser Only (Playwright)"

    domain = models.CharField(max_length=255, unique=True, db_index=True)
    auth_type = models.CharField(
        max_length=20, choices=AuthType.choices, default=AuthType.NONE,
    )
    auth_strategy = models.CharField(
        max_length=20, choices=AuthStrategy.choices, default=AuthStrategy.AUTO,
        help_text="Login method strategy: auto, http_only, or playwright_only",
    )
    is_enabled = models.BooleanField(default=False)

    # Form login fields
    login_url = models.URLField(max_length=2048, blank=True, default="")
    username = models.CharField(max_length=255, blank=True, default="")
    password_encrypted = models.TextField(
        blank=True, default="",
        help_text="AES-encrypted password",
    )
    username_selector = models.CharField(
        max_length=255, blank=True, default="",
        help_text='CSS selector for username field, e.g. #email or input[name=username]',
    )
    password_selector = models.CharField(
        max_length=255, blank=True, default="",
        help_text='CSS selector for password field, e.g. #password',
    )
    submit_selector = models.CharField(
        max_length=255, blank=True, default="",
        help_text='CSS selector for submit button, e.g. button[type=submit]',
    )

    # Interactive login fields
    login_button_selector = models.CharField(
        max_length=255, blank=True, default="",
        help_text='CSS selector for the login button on homepage that opens the login form/modal',
    )
    home_url = models.URLField(
        max_length=2048, blank=True, default="",
        help_text='Homepage URL where the login button is located',
    )

    # Recorded login flow
    recorded_steps = models.JSONField(
        default=list, blank=True,
        help_text='JSON array of recorded login steps: [{action, selector, value, ...}]',
    )

    # Cookie-based auth
    cookie_value = models.TextField(
        blank=True, default="",
        help_text='Raw cookie string, e.g. sessionid=abc123; token=xyz',
    )

    # Auth status & session
    auth_status = models.CharField(
        max_length=10, choices=AuthStatus.choices, default=AuthStatus.UNTESTED,
    )
    last_test_at = models.DateTimeField(null=True, blank=True)
    last_error = models.TextField(blank=True, default="")
    session_cookies = models.JSONField(
        default=dict, blank=True,
        help_text="Cookies obtained after successful login",
    )
    session_valid_until = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]
        verbose_name = "Site Auth Config"
        verbose_name_plural = "Site Auth Configs"

    def __str__(self):
        return f"{self.domain} [{self.auth_type}] {'✅' if self.auth_status == 'success' else '❌' if self.auth_status == 'failed' else '⏳'}"

    def set_password(self, raw_password: str):
        """Encrypt and store the password."""
        self.password_encrypted = encrypt_value(raw_password)

    def get_password(self) -> str:
        """Decrypt and return the password."""
        return decrypt_value(self.password_encrypted)

    def get_cookies_dict(self) -> dict:
        """
        Parse cookie_value string into a dict.
        Supports both direct cookie string and session_cookies JSON.
        """
        if self.auth_type == self.AuthType.COOKIE and self.cookie_value:
            cookies = {}
            for part in self.cookie_value.split(";"):
                part = part.strip()
                if "=" in part:
                    key, val = part.split("=", 1)
                    cookies[key.strip()] = val.strip()
            return cookies
        if self.session_cookies:
            return dict(self.session_cookies)
        return {}
