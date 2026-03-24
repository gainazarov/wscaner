"""Admin configuration for the scans app."""

from django.contrib import admin

from .models import DiffURL, DiscoveredURL, Scan, ScanDiff


@admin.register(Scan)
class ScanAdmin(admin.ModelAdmin):
    list_display = ["id", "domain", "status", "total_urls", "new_urls", "created_at"]
    list_filter = ["status", "domain"]
    search_fields = ["domain"]
    readonly_fields = ["created_at", "updated_at"]


@admin.register(DiscoveredURL)
class DiscoveredURLAdmin(admin.ModelAdmin):
    list_display = ["url", "scan", "source", "status_code", "is_new", "first_seen"]
    list_filter = ["source", "is_new", "is_internal"]
    search_fields = ["url"]
    raw_id_fields = ["scan"]


@admin.register(ScanDiff)
class ScanDiffAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "current_scan",
        "previous_scan",
        "new_urls_count",
        "removed_urls_count",
    ]
    raw_id_fields = ["current_scan", "previous_scan"]


@admin.register(DiffURL)
class DiffURLAdmin(admin.ModelAdmin):
    list_display = ["url", "change_type", "diff"]
    list_filter = ["change_type"]
    raw_id_fields = ["diff"]
