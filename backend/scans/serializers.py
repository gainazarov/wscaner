"""Serializers for the scans app."""

from rest_framework import serializers

from .models import (
    DiffURL,
    DiscoveredURL,
    DomainListEntry,
    DomainReputation,
    ExternalDomainAlert,
    ExternalDomainEntry,
    LightScanResult,
    Scan,
    ScanDiff,
    SiteAuthConfig,
    SiteMonitorConfig,
)

class DiscoveredURLSerializer(serializers.ModelSerializer):
    source_display = serializers.CharField(source="get_source_display", read_only=True)
    status_category = serializers.CharField(read_only=True)

    class Meta:
        model = DiscoveredURL
        fields = [
            "id",
            "url",
            "source",
            "source_display",
            "status_code",
            "status_category",
            "content_type",
            "depth",
            "is_internal",
            "is_new",
            "is_private",
            "is_sensitive",
            "external_domain",
            "source_url",
            "first_seen",
            "last_seen",
        ]


class ScanListSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    duration = serializers.SerializerMethodField()

    class Meta:
        model = Scan
        fields = [
            "id",
            "domain",
            "status",
            "status_display",
            "total_urls",
            "new_urls",
            "internal_urls",
            "external_urls",
            "hidden_urls",
            "error_urls",
            "private_urls",
            "max_depth",
            "max_pages",
            "started_at",
            "completed_at",
            "duration",
            "auth_success",
            "auth_method",
            "auth_error",
            "created_at",
        ]

    def get_duration(self, obj):
        return obj.duration_seconds


class ScanDetailSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    duration = serializers.SerializerMethodField()
    source_breakdown = serializers.SerializerMethodField()
    status_breakdown = serializers.SerializerMethodField()
    external_domains = serializers.SerializerMethodField()

    class Meta:
        model = Scan
        fields = [
            "id",
            "domain",
            "status",
            "status_display",
            "total_urls",
            "new_urls",
            "internal_urls",
            "external_urls",
            "hidden_urls",
            "error_urls",
            "private_urls",
            "max_depth",
            "max_pages",
            "started_at",
            "completed_at",
            "duration",
            "error_message",
            "auth_success",
            "auth_method",
            "auth_error",
            "created_at",
            "updated_at",
            "source_breakdown",
            "status_breakdown",
            "external_domains",
        ]

    def get_duration(self, obj):
        return obj.duration_seconds

    def get_source_breakdown(self, obj):
        """URL counts by source type."""
        from django.db.models import Count
        return dict(
            obj.urls.values_list("source")
            .annotate(count=Count("id"))
            .values_list("source", "count")
        )

    def get_status_breakdown(self, obj):
        """URL counts by status code ranges."""
        urls = obj.urls.all()
        return {
            "success": urls.filter(status_code__gte=200, status_code__lt=300).count(),
            "redirect": urls.filter(status_code__gte=300, status_code__lt=400).count(),
            "hidden": urls.filter(status_code=403).count(),
            "client_error": urls.filter(status_code__gte=400, status_code__lt=500).exclude(status_code=403).count(),
            "server_error": urls.filter(status_code__gte=500).count(),
            "unknown": urls.filter(status_code__isnull=True).count(),
        }

    def get_external_domains(self, obj):
        """Top external domains with counts."""
        from django.db.models import Count
        return list(
            obj.urls.filter(is_internal=False)
            .exclude(external_domain="")
            .values("external_domain")
            .annotate(count=Count("id"))
            .order_by("-count")[:20]
        )


class CreateScanSerializer(serializers.Serializer):
    domain = serializers.CharField(max_length=255)
    max_depth = serializers.IntegerField(default=3, min_value=1, max_value=10)
    max_pages = serializers.IntegerField(default=500, min_value=1, max_value=10000)


class DiffURLSerializer(serializers.ModelSerializer):
    class Meta:
        model = DiffURL
        fields = ["id", "url", "change_type"]


class ScanDiffSerializer(serializers.ModelSerializer):
    diff_urls = DiffURLSerializer(many=True, read_only=True)

    class Meta:
        model = ScanDiff
        fields = [
            "id",
            "current_scan",
            "previous_scan",
            "new_urls_count",
            "removed_urls_count",
            "diff_urls",
            "created_at",
        ]


class DomainStatsSerializer(serializers.Serializer):
    domain = serializers.CharField()
    total_scans = serializers.IntegerField()
    last_scan_date = serializers.DateTimeField()
    last_scan_status = serializers.CharField()
    total_unique_urls = serializers.IntegerField()
    last_scan_id = serializers.IntegerField()
    external_domains_count = serializers.IntegerField()


class ExternalDomainSerializer(serializers.Serializer):
    """Serializer for external domain grouping."""
    external_domain = serializers.CharField()
    count = serializers.IntegerField()
    sources = serializers.ListField(child=serializers.CharField(), required=False)
    urls = serializers.ListField(child=serializers.DictField(), required=False)


class ExternalDomainEntrySerializer(serializers.ModelSerializer):
    """Serializer for ExternalDomainEntry model."""
    first_seen_scan_id = serializers.IntegerField(source="first_seen_scan.id", read_only=True, default=None)
    last_seen_scan_id = serializers.IntegerField(source="last_seen_scan.id", read_only=True, default=None)
    days_since_first_seen = serializers.SerializerMethodField()

    class Meta:
        model = ExternalDomainEntry
        fields = [
            "id",
            "site_domain",
            "domain",
            "status",
            "list_classification",
            "is_suspicious",
            "suspicious_reasons",
            "first_seen",
            "last_seen",
            "times_seen",
            "found_on_pages",
            "first_seen_scan_id",
            "last_seen_scan_id",
            "days_since_first_seen",
        ]

    def get_days_since_first_seen(self, obj):
        from django.utils import timezone
        delta = timezone.now() - obj.first_seen
        return delta.days


class ExternalDomainAlertSerializer(serializers.ModelSerializer):
    """Serializer for ExternalDomainAlert model."""
    alert_type_display = serializers.CharField(source="get_alert_type_display", read_only=True)
    severity_display = serializers.CharField(source="get_severity_display", read_only=True)
    scan_id = serializers.SerializerMethodField()

    class Meta:
        model = ExternalDomainAlert
        fields = [
            "id",
            "scan_id",
            "site_domain",
            "external_domain",
            "alert_type",
            "alert_type_display",
            "severity",
            "severity_display",
            "message",
            "domain_list",
            "is_read",
            "created_at",
        ]

    def get_scan_id(self, obj):
        return obj.scan_id if obj.scan_id else None


class MonitoringSummarySerializer(serializers.Serializer):
    """Serializer for External Monitoring summary."""
    total_external_domains = serializers.IntegerField()
    new_domains = serializers.IntegerField()
    suspicious_domains = serializers.IntegerField()
    safe_domains = serializers.IntegerField()
    unread_alerts = serializers.IntegerField()
    total_alerts = serializers.IntegerField()
    whitelist_domains = serializers.IntegerField(default=0)
    blacklist_domains = serializers.IntegerField(default=0)
    unknown_domains = serializers.IntegerField(default=0)


class DomainReputationSerializer(serializers.ModelSerializer):
    """Serializer for domain reputation results."""

    is_cache_valid = serializers.SerializerMethodField()

    class Meta:
        model = DomainReputation
        fields = [
            "id",
            "domain",
            "risk_level",
            "check_status",
            "safe_browsing_result",
            "safe_browsing_risk",
            "virustotal_stats",
            "virustotal_risk",
            "virustotal_malicious",
            "virustotal_suspicious",
            "virustotal_harmless",
            "virustotal_undetected",
            "checked_at",
            "error_message",
            "check_count",
            "is_cache_valid",
            "created_at",
            "updated_at",
        ]

    def get_is_cache_valid(self, obj):
        from datetime import timedelta
        from django.conf import settings
        from django.utils import timezone

        if not obj.checked_at:
            return False

        ttl_hours = int(getattr(settings, "DOMAIN_REPUTATION_CACHE_HOURS", 24))
        return timezone.now() - obj.checked_at < timedelta(hours=ttl_hours)


class ReputationSummarySerializer(serializers.Serializer):
    """Summary stats for reputation list endpoint."""

    total = serializers.IntegerField()
    high_risk = serializers.IntegerField()
    medium_risk = serializers.IntegerField()
    low_risk = serializers.IntegerField()
    unknown_risk = serializers.IntegerField()
    pending = serializers.IntegerField()
    checking = serializers.IntegerField()
    completed = serializers.IntegerField()
    failed = serializers.IntegerField()


# ─── Blacklist / Whitelist Serializers ───────────────────────────────────────


class DomainListEntrySerializer(serializers.ModelSerializer):
    """Full serializer for DomainListEntry."""

    class Meta:
        model = DomainListEntry
        fields = [
            "id",
            "site_domain",
            "domain",
            "list_type",
            "note",
            "added_by",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]


class DomainListEntryCreateSerializer(serializers.Serializer):
    """Serializer for creating / bulk-creating list entries."""

    site_domain = serializers.CharField(max_length=255)
    domains = serializers.ListField(
        child=serializers.CharField(max_length=255),
        min_length=1,
        max_length=500,
    )
    list_type = serializers.ChoiceField(choices=DomainListEntry.ListType.choices)
    note = serializers.CharField(required=False, default="", allow_blank=True)

    def validate_domains(self, value):
        from .models import normalize_domain
        cleaned = []
        for d in value:
            norm = normalize_domain(d.strip().lower())
            if norm and norm not in cleaned:
                cleaned.append(norm)
        if not cleaned:
            raise serializers.ValidationError("No valid domains provided")
        return cleaned


class DomainListClassificationSerializer(serializers.Serializer):
    """Summary of domain classification for a site scan."""

    total = serializers.IntegerField()
    whitelist = serializers.IntegerField()
    blacklist = serializers.IntegerField()
    unknown = serializers.IntegerField()


# ─── Real-Time Monitoring Serializers ────────────────────────────────────────


class SiteMonitorConfigSerializer(serializers.ModelSerializer):
    """Full serializer for SiteMonitorConfig CRUD."""

    is_due = serializers.BooleanField(read_only=True)
    light_scans_count = serializers.SerializerMethodField()
    last_result = serializers.SerializerMethodField()

    class Meta:
        model = SiteMonitorConfig
        fields = [
            "id",
            "domain",
            "is_enabled",
            "interval_minutes",
            "key_pages",
            "last_content_hash",
            "last_scan_at",
            "next_scan_at",
            "total_light_scans",
            "changes_detected_count",
            "consecutive_errors",
            "last_error",
            "is_due",
            "light_scans_count",
            "last_result",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "last_content_hash",
            "last_scan_at",
            "next_scan_at",
            "total_light_scans",
            "changes_detected_count",
            "consecutive_errors",
            "last_error",
            "created_at",
            "updated_at",
        ]

    def get_light_scans_count(self, obj):
        return obj.light_scan_results.count()

    def get_last_result(self, obj):
        last = obj.light_scan_results.first()
        if last:
            return LightScanResultCompactSerializer(last).data
        return None


class SiteMonitorConfigCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating/updating monitor config."""

    class Meta:
        model = SiteMonitorConfig
        fields = ["domain", "is_enabled", "interval_minutes", "key_pages"]

    def validate_interval_minutes(self, value):
        if value < 5:
            raise serializers.ValidationError("Minimum interval is 5 minutes")
        if value > 1440:
            raise serializers.ValidationError("Maximum interval is 1440 minutes (24h)")
        return value

    def validate_domain(self, value):
        import re
        domain = value.strip().lower()
        if not re.match(r'^[a-z0-9]([a-z0-9\-]*[a-z0-9])?(\.[a-z0-9]([a-z0-9\-]*[a-z0-9])?)*\.[a-z]{2,}$', domain):
            raise serializers.ValidationError("Invalid domain format")
        return domain


class LightScanResultSerializer(serializers.ModelSerializer):
    """Full serializer for LightScanResult."""

    domain = serializers.CharField(source="site_config.domain", read_only=True)

    class Meta:
        model = LightScanResult
        fields = [
            "id",
            "domain",
            "content_hash",
            "previous_hash",
            "has_changes",
            "pages_checked",
            "pages_data",
            "external_domains_snapshot",
            "new_domains",
            "removed_domains",
            "new_domains_count",
            "removed_domains_count",
            "reputation_enqueued",
            "scan_duration",
            "error",
            "created_at",
        ]


class LightScanResultCompactSerializer(serializers.ModelSerializer):
    """Compact serializer for embedding in config response."""

    class Meta:
        model = LightScanResult
        fields = [
            "id",
            "has_changes",
            "new_domains_count",
            "removed_domains_count",
            "pages_checked",
            "scan_duration",
            "created_at",
        ]


class MonitoringStatusSerializer(serializers.Serializer):
    """Aggregated monitoring dashboard status."""

    total_configs = serializers.IntegerField()
    active_configs = serializers.IntegerField()
    total_light_scans = serializers.IntegerField()
    total_changes_detected = serializers.IntegerField()
    total_new_domains_found = serializers.IntegerField()
    configs = SiteMonitorConfigSerializer(many=True)


# ─── Authenticated Scanning Serializers ──────────────────────────────────────


class SiteAuthConfigSerializer(serializers.ModelSerializer):
    """Read serializer for SiteAuthConfig (never exposes raw password)."""

    has_password = serializers.SerializerMethodField()

    class Meta:
        model = SiteAuthConfig
        fields = [
            "id",
            "domain",
            "auth_type",
            "auth_strategy",
            "is_enabled",
            "login_url",
            "username",
            "has_password",
            "username_selector",
            "password_selector",
            "submit_selector",
            "login_button_selector",
            "home_url",
            "recorded_steps",
            "cookie_value",
            "auth_status",
            "last_test_at",
            "last_error",
            "session_valid_until",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id", "auth_status", "last_test_at", "last_error",
            "session_valid_until", "created_at", "updated_at",
        ]

    def get_has_password(self, obj):
        return bool(obj.password_encrypted)


class SiteAuthConfigWriteSerializer(serializers.Serializer):
    """Write serializer for creating/updating auth config."""

    domain = serializers.CharField(max_length=255)
    auth_type = serializers.ChoiceField(choices=SiteAuthConfig.AuthType.choices)
    auth_strategy = serializers.ChoiceField(
        choices=SiteAuthConfig.AuthStrategy.choices,
        required=False, default="auto",
    )
    is_enabled = serializers.BooleanField(default=False)

    # Form login
    login_url = serializers.CharField(max_length=2048, required=False, allow_blank=True, default="")
    username = serializers.CharField(max_length=255, required=False, allow_blank=True, default="")
    password = serializers.CharField(max_length=500, required=False, allow_blank=True, default="")
    username_selector = serializers.CharField(max_length=255, required=False, allow_blank=True, default="")
    password_selector = serializers.CharField(max_length=255, required=False, allow_blank=True, default="")
    submit_selector = serializers.CharField(max_length=255, required=False, allow_blank=True, default="")

    # Interactive login
    login_button_selector = serializers.CharField(max_length=255, required=False, allow_blank=True, default="")
    home_url = serializers.CharField(max_length=2048, required=False, allow_blank=True, default="")

    # Recorded flow
    recorded_steps = serializers.ListField(
        child=serializers.DictField(), required=False, default=list,
    )

    # Cookie
    cookie_value = serializers.CharField(required=False, allow_blank=True, default="")

    def validate_domain(self, value):
        import re
        domain = value.strip().lower()
        if not re.match(r'^[a-z0-9]([a-z0-9\-]*[a-z0-9])?(\.[a-z0-9]([a-z0-9\-]*[a-z0-9])?)*\.[a-z]{2,}$', domain):
            raise serializers.ValidationError("Invalid domain format")
        return domain

    def validate(self, data):
        auth_type = data.get("auth_type", "none")
        if auth_type == "form":
            if not data.get("login_url"):
                raise serializers.ValidationError({"login_url": "Login URL is required for form login"})
            if not data.get("username"):
                raise serializers.ValidationError({"username": "Username is required for form login"})
        elif auth_type == "interactive":
            if not data.get("home_url") and not data.get("login_url"):
                raise serializers.ValidationError({"home_url": "Home URL or Login URL is required for interactive login"})
            if not data.get("username"):
                raise serializers.ValidationError({"username": "Username is required for interactive login"})
        elif auth_type == "recorded":
            if not data.get("recorded_steps"):
                raise serializers.ValidationError({"recorded_steps": "Recorded steps are required for recorded flow"})
        return data

