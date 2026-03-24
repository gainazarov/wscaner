"""URL patterns for the scans app."""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register(r"scans", views.ScanViewSet, basename="scan")

urlpatterns = [
    path("", include(router.urls)),
    path("domains/", views.domain_stats, name="domain-stats"),
    path("dashboard/", views.dashboard_stats, name="dashboard-stats"),
    path("scans/<int:scan_id>/stream/", views.scan_stream, name="scan-stream"),
    # External Monitoring endpoints
    path("monitoring/", views.external_monitoring, name="external-monitoring"),
    path("monitoring/timeline/", views.external_domain_timeline, name="external-timeline"),
    path("monitoring/domain/<str:domain>/", views.external_domain_detail, name="external-domain-detail"),
    path("monitoring/alerts/read/", views.mark_alerts_read, name="mark-alerts-read"),
    path("monitoring/domain/safe/", views.mark_domain_safe, name="mark-domain-safe"),
    path("monitoring/reputation/", views.reputation_list, name="reputation-list"),
    path("monitoring/reputation/check/", views.check_reputation, name="reputation-check"),
    path("monitoring/reputation/check-all/", views.check_all_reputations, name="reputation-check-all"),
    # Blacklist / Whitelist endpoints
    path("monitoring/lists/", views.domain_lists, name="domain-lists"),
    path("monitoring/lists/add/", views.domain_lists_add, name="domain-lists-add"),
    path("monitoring/lists/<int:entry_id>/remove/", views.domain_lists_remove, name="domain-lists-remove"),
    path("monitoring/lists/quick-action/", views.domain_lists_quick_action, name="domain-lists-quick-action"),
    path("monitoring/lists/clear/", views.domain_lists_bulk_clear, name="domain-lists-clear"),
    path("monitoring/lists/suggestions/", views.domain_lists_suggestions, name="domain-lists-suggestions"),
    # Real-Time Monitoring endpoints
    path("monitoring/realtime/", views.realtime_monitoring_status, name="realtime-status"),
    path("monitoring/realtime/create/", views.realtime_monitoring_create, name="realtime-create"),
    path("monitoring/realtime/<int:config_id>/", views.realtime_monitoring_detail, name="realtime-detail"),
    path("monitoring/realtime/<int:config_id>/toggle/", views.realtime_monitoring_toggle, name="realtime-toggle"),
    path("monitoring/realtime/<int:config_id>/scan-now/", views.realtime_monitoring_scan_now, name="realtime-scan-now"),
    path("monitoring/realtime/<int:config_id>/history/", views.realtime_monitoring_history, name="realtime-history"),
    path("monitoring/realtime/latest/", views.realtime_monitoring_latest, name="realtime-latest"),
    # Authenticated Scanning endpoints
    path("auth/config/", views.auth_config_get, name="auth-config-get"),
    path("auth/config/save/", views.auth_config_save, name="auth-config-save"),
    path("auth/config/test/", views.auth_config_test, name="auth-config-test"),
    path("auth/config/delete/", views.auth_config_delete, name="auth-config-delete"),
    path("auth/detect-fields/", views.auth_detect_fields, name="auth-detect-fields"),
    path("auth/debug/", views.auth_debug_login, name="auth-debug-login"),
    path("auth/stability/", views.auth_stability_score, name="auth-stability-score"),
    # Recorder endpoints
    path("auth/record/start/", views.auth_record_start, name="auth-record-start"),
    path("auth/record/stop/", views.auth_record_stop, name="auth-record-stop"),
    path("auth/record/status/", views.auth_record_status, name="auth-record-status"),
    path("auth/record/reset/", views.auth_record_reset, name="auth-record-reset"),
    # Scanner logs
    path("logs/", views.scanner_logs, name="scanner-logs"),
    path("logs/files/", views.scanner_logs_files, name="scanner-logs-files"),
    path("logs/clear/", views.scanner_logs_clear, name="scanner-logs-clear"),
]
