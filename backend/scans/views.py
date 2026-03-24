"""Views for the scans app."""

import json
import logging

import requests
from django.conf import settings
from django.db.models import Count, Max
from django.http import StreamingHttpResponse
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action, api_view
from rest_framework.response import Response

from .models import (
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
from .reputation import analyze_domain, enqueue_domain, enqueue_domains, normalize_domain as rep_normalize
from .serializers import (
    CreateScanSerializer,
    DomainListClassificationSerializer,
    DomainListEntryCreateSerializer,
    DomainListEntrySerializer,
    DomainReputationSerializer,
    DiscoveredURLSerializer,
    DomainStatsSerializer,
    ExternalDomainAlertSerializer,
    ExternalDomainEntrySerializer,
    LightScanResultSerializer,
    MonitoringSummarySerializer,
    ReputationSummarySerializer,
    ScanDetailSerializer,
    ScanDiffSerializer,
    ScanListSerializer,
    SiteAuthConfigSerializer,
    SiteAuthConfigWriteSerializer,
    SiteMonitorConfigCreateSerializer,
    SiteMonitorConfigSerializer,
)
from .tasks import process_reputation_queue_task, run_scan_task

logger = logging.getLogger(__name__)


class ScanViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for listing and retrieving scans."""

    queryset = Scan.objects.all()

    def get_serializer_class(self):
        if self.action == "retrieve":
            return ScanDetailSerializer
        return ScanListSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        domain = self.request.query_params.get("domain")
        status_filter = self.request.query_params.get("status")
        if domain:
            qs = qs.filter(domain__icontains=domain)
        if status_filter:
            qs = qs.filter(status=status_filter)
        return qs

    def create(self, request):
        """Create a new scan and dispatch it."""
        serializer = CreateScanSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        domain = serializer.validated_data["domain"]
        # Normalize domain
        domain = domain.strip().lower()
        if domain.startswith("http://") or domain.startswith("https://"):
            from urllib.parse import urlparse

            domain = urlparse(domain).netloc or domain

        scan = Scan.objects.create(
            domain=domain,
            max_depth=serializer.validated_data.get("max_depth", 3),
            max_pages=serializer.validated_data.get("max_pages", 500),
        )

        return Response(
            ScanListSerializer(scan).data, status=status.HTTP_201_CREATED
        )

    @action(detail=True, methods=["get"])
    def urls(self, request, pk=None):
        """Get URLs for a specific scan with advanced filtering."""
        scan = self.get_object()
        urls = scan.urls.all()

        # Filters
        source = request.query_params.get("source")
        is_new = request.query_params.get("is_new")
        is_internal = request.query_params.get("is_internal")
        search = request.query_params.get("search")
        status_code = request.query_params.get("status_code")
        tab = request.query_params.get("tab")  # all, new, hidden, external, errors, private
        external_domain = request.query_params.get("external_domain")
        ordering = request.query_params.get("ordering", "-first_seen")
        visibility = request.query_params.get("visibility")  # public, private
        list_status = request.query_params.get("list_status")  # whitelist, blacklist, unknown

        # Tab-based filtering
        if tab == "new":
            urls = urls.filter(is_new=True)
        elif tab == "hidden":
            urls = urls.filter(status_code=403)
        elif tab == "external":
            urls = urls.filter(is_internal=False)
        elif tab == "errors":
            urls = urls.filter(status_code__gte=400)
        elif tab == "private":
            urls = urls.filter(is_private=True)

        # Visibility filter (public / private)
        if visibility == "public":
            urls = urls.filter(is_private=False)
        elif visibility == "private":
            urls = urls.filter(is_private=True)

        # Whitelist / Blacklist / Unknown filter for external URLs
        if list_status in ("whitelist", "blacklist", "unknown"):
            ext_domains = list(
                scan.urls.filter(is_internal=False)
                .exclude(external_domain="")
                .values_list("external_domain", flat=True)
                .distinct()
            )
            if ext_domains:
                classifications = DomainListEntry.classify_domains_bulk(
                    scan.domain, ext_domains
                )
                matching_domains = [
                    d for d, c in classifications.items() if c == list_status
                ]
                if list_status == "unknown":
                    # Unknown = external domains not in any list + internal URLs are NOT unknown
                    urls = urls.filter(
                        is_internal=False,
                        external_domain__in=matching_domains,
                    )
                else:
                    urls = urls.filter(
                        is_internal=False,
                        external_domain__in=matching_domains,
                    )
            else:
                if list_status != "unknown":
                    urls = urls.none()

        if source:
            urls = urls.filter(source=source)
        if is_new is not None and tab != "new":
            urls = urls.filter(is_new=is_new.lower() in ("true", "1"))
        if is_internal is not None and tab != "external":
            urls = urls.filter(is_internal=is_internal.lower() in ("true", "1"))
        if search:
            urls = urls.filter(url__icontains=search)
        if status_code:
            urls = urls.filter(status_code=int(status_code))
        if external_domain:
            urls = urls.filter(external_domain=external_domain)

        # Ordering
        valid_orderings = ["url", "-url", "status_code", "-status_code",
                          "depth", "-depth", "first_seen", "-first_seen",
                          "source", "-source"]
        if ordering in valid_orderings:
            urls = urls.order_by(ordering)

        page = self.paginate_queryset(urls)
        if page is not None:
            serializer = DiscoveredURLSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = DiscoveredURLSerializer(urls, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["get"], url_path="url_summary")
    def url_summary(self, request, pk=None):
        """Get URL summary with public/private/whitelist/blacklist breakdown."""
        scan = self.get_object()
        all_urls = scan.urls.all()

        total = all_urls.count()
        public_count = all_urls.filter(is_private=False).count()
        private_count = all_urls.filter(is_private=True).count()
        internal_count = all_urls.filter(is_internal=True).count()
        external_count = all_urls.filter(is_internal=False).count()

        # Classify external domains
        ext_domains = list(
            all_urls.filter(is_internal=False)
            .exclude(external_domain="")
            .values_list("external_domain", flat=True)
            .distinct()
        )

        whitelist_count = 0
        blacklist_count = 0
        unknown_count = 0
        whitelist_domains = []
        blacklist_domains = []
        unknown_domains = []

        if ext_domains:
            classifications = DomainListEntry.classify_domains_bulk(
                scan.domain, ext_domains
            )
            for domain, cls in classifications.items():
                domain_url_count = all_urls.filter(
                    is_internal=False, external_domain=domain
                ).count()
                entry = {"domain": domain, "count": domain_url_count}
                if cls == "whitelist":
                    whitelist_count += domain_url_count
                    whitelist_domains.append(entry)
                elif cls == "blacklist":
                    blacklist_count += domain_url_count
                    blacklist_domains.append(entry)
                else:
                    unknown_count += domain_url_count
                    unknown_domains.append(entry)

        return Response({
            "total": total,
            "public": public_count,
            "private": private_count,
            "internal": internal_count,
            "external": external_count,
            "whitelist": whitelist_count,
            "blacklist": blacklist_count,
            "unknown": unknown_count,
            "whitelist_domains": sorted(whitelist_domains, key=lambda x: -x["count"]),
            "blacklist_domains": sorted(blacklist_domains, key=lambda x: -x["count"]),
            "unknown_domains": sorted(unknown_domains, key=lambda x: -x["count"]),
        })

    @action(detail=True, methods=["get"])
    def external_domains(self, request, pk=None):
        """Get external domains grouped with counts for a scan."""
        scan = self.get_object()
        domains = (
            scan.urls.filter(is_internal=False)
            .exclude(external_domain="")
            .values("external_domain")
            .annotate(count=Count("id"))
            .order_by("-count")
        )

        # Optionally expand to show URLs per domain
        expand = request.query_params.get("expand", "false").lower() in ("true", "1")
        results = []
        for d in domains:
            item = {
                "external_domain": d["external_domain"],
                "count": d["count"],
            }
            if expand:
                domain_urls = scan.urls.filter(
                    is_internal=False, external_domain=d["external_domain"]
                ).values("url", "source", "status_code", "source_url")[:50]
                item["urls"] = list(domain_urls)
                item["sources"] = list(
                    scan.urls.filter(
                        is_internal=False, external_domain=d["external_domain"]
                    ).values_list("source", flat=True).distinct()
                )
            results.append(item)

        return Response(results)

    @action(detail=True, methods=["get"])
    def summary(self, request, pk=None):
        """Get detailed summary statistics for a scan."""
        scan = self.get_object()
        serializer = ScanDetailSerializer(scan)
        return Response(serializer.data)

    @action(detail=True, methods=["get"])
    def diff(self, request, pk=None):
        """Get diff between this scan and the previous one."""
        scan = self.get_object()
        diffs = ScanDiff.objects.filter(current_scan=scan)
        serializer = ScanDiffSerializer(diffs, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["post"])
    def rescan(self, request, pk=None):
        """Re-run a scan for the same domain."""
        original_scan = self.get_object()
        new_scan = Scan.objects.create(
            domain=original_scan.domain,
            max_depth=original_scan.max_depth,
            max_pages=original_scan.max_pages,
        )
        run_scan_task.delay(new_scan.id)
        return Response(
            ScanListSerializer(new_scan).data, status=status.HTTP_201_CREATED
        )


@api_view(["GET"])
def domain_stats(request):
    """Get stats grouped by domain."""
    domains = (
        Scan.objects.values("domain")
        .annotate(
            total_scans=Count("id"),
            last_scan_date=Max("created_at"),
        )
        .order_by("-last_scan_date")
    )

    results = []
    for d in domains:
        last_scan = (
            Scan.objects.filter(domain=d["domain"]).order_by("-created_at").first()
        )
        unique_urls = (
            DiscoveredURL.objects.filter(scan__domain=d["domain"])
            .values("url")
            .distinct()
            .count()
        )
        external_domains = (
            DiscoveredURL.objects.filter(scan__domain=d["domain"], is_internal=False)
            .values("external_domain")
            .distinct()
            .count()
        )
        results.append(
            {
                "domain": d["domain"],
                "total_scans": d["total_scans"],
                "last_scan_date": d["last_scan_date"],
                "last_scan_status": last_scan.status if last_scan else None,
                "last_scan_id": last_scan.id if last_scan else None,
                "total_unique_urls": unique_urls,
                "external_domains_count": external_domains,
            }
        )

    return Response(results)


@api_view(["GET"])
def dashboard_stats(request):
    """Get overall dashboard statistics."""
    # Domains to exclude from stats (test/default entries)
    EXCLUDED_DOMAINS = ["example.com", "localhost", "127.0.0.1"]

    total_scans = Scan.objects.count()
    active_scans = Scan.objects.filter(
        status__in=[Scan.Status.PENDING, Scan.Status.RUNNING]
    ).count()
    completed_scans = Scan.objects.filter(status=Scan.Status.COMPLETED).count()
    total_urls = DiscoveredURL.objects.count()
    unique_domains = Scan.objects.values("domain").distinct().count()
    external_urls = DiscoveredURL.objects.filter(is_internal=False).count()
    hidden_urls = DiscoveredURL.objects.filter(status_code=403).count()

    # Recent scans for dashboard (exclude test domains)
    recent_scans = Scan.objects.exclude(domain__in=EXCLUDED_DOMAINS)[:10]
    recent_data = ScanListSerializer(recent_scans, many=True).data

    # Last completed scan info (exclude test domains)
    last_completed_scan = (
        Scan.objects.filter(status=Scan.Status.COMPLETED)
        .exclude(domain__in=EXCLUDED_DOMAINS)
        .order_by("-completed_at")
        .first()
    )

    last_scan_info = None
    if last_completed_scan:
        last_scan_info = {
            "id": last_completed_scan.id,
            "domain": last_completed_scan.domain,
            "completed_at": (
                last_completed_scan.completed_at.isoformat()
                if last_completed_scan.completed_at else None
            ),
            "started_at": (
                last_completed_scan.started_at.isoformat()
                if last_completed_scan.started_at else None
            ),
            "total_urls": last_completed_scan.total_urls,
            "duration": last_completed_scan.duration_seconds,
            "status": last_completed_scan.status,
        }

    # If no completed scans, fall back to latest scan of any status
    if not last_scan_info:
        last_any_scan = (
            Scan.objects.exclude(domain__in=EXCLUDED_DOMAINS)
            .order_by("-created_at")
            .first()
        )
        if last_any_scan:
            last_scan_info = {
                "id": last_any_scan.id,
                "domain": last_any_scan.domain,
                "completed_at": (
                    last_any_scan.completed_at.isoformat()
                    if last_any_scan.completed_at else None
                ),
                "started_at": (
                    last_any_scan.started_at.isoformat()
                    if last_any_scan.started_at else None
                ),
                "total_urls": last_any_scan.total_urls,
                "duration": last_any_scan.duration_seconds,
                "status": last_any_scan.status,
            }

    # Next scheduled monitoring scan (exclude test domains)
    next_monitoring_scan = (
        SiteMonitorConfig.objects.filter(is_enabled=True, next_scan_at__isnull=False)
        .exclude(domain__in=EXCLUDED_DOMAINS)
        .order_by("next_scan_at")
        .first()
    )
    next_scan_info = None
    if next_monitoring_scan:
        next_scan_info = {
            "domain": next_monitoring_scan.domain,
            "next_scan_at": (
                next_monitoring_scan.next_scan_at.isoformat()
                if next_monitoring_scan.next_scan_at else None
            ),
            "interval_minutes": next_monitoring_scan.interval_minutes,
        }

    # Last light scan (monitoring) info
    from .models import LightScanResult
    last_light_scan = (
        LightScanResult.objects
        .select_related("site_config")
        .exclude(site_config__domain__in=EXCLUDED_DOMAINS)
        .order_by("-created_at")
        .first()
    )
    last_monitoring_info = None
    if last_light_scan:
        last_monitoring_info = {
            "domain": last_light_scan.site_config.domain,
            "scanned_at": last_light_scan.created_at.isoformat(),
            "has_changes": last_light_scan.has_changes,
            "pages_checked": last_light_scan.pages_checked,
            "new_domains": last_light_scan.new_domains_count,
            "duration": last_light_scan.scan_duration,
        }

    # Active scan (currently running)
    active_scan = Scan.objects.filter(
        status__in=[Scan.Status.PENDING, Scan.Status.RUNNING]
    ).exclude(domain__in=EXCLUDED_DOMAINS).order_by("-created_at").first()
    active_scan_info = None
    if active_scan:
        active_scan_info = {
            "id": active_scan.id,
            "domain": active_scan.domain,
            "status": active_scan.status,
            "started_at": (
                active_scan.started_at.isoformat()
                if active_scan.started_at else None
            ),
        }

    return Response(
        {
            "total_scans": total_scans,
            "active_scans": active_scans,
            "completed_scans": completed_scans,
            "total_urls_discovered": total_urls,
            "unique_domains": unique_domains,
            "external_urls": external_urls,
            "hidden_urls": hidden_urls,
            "recent_scans": recent_data,
            "last_scan": last_scan_info,
            "next_scheduled_scan": next_scan_info,
            "last_monitoring_scan": last_monitoring_info,
            "active_scan": active_scan_info,
        }
    )


@api_view(["GET"])
def scan_stream(request, scan_id):
    """
    SSE proxy: streams real-time scan events from the scanner service.
    The frontend connects via EventSource to GET /api/scans/<id>/stream/.
    This view POSTs to the scanner's /scan/stream endpoint and forwards events.
    """
    try:
        scan = Scan.objects.get(id=scan_id)
    except Scan.DoesNotExist:
        return Response({"error": "Scan not found"}, status=404)

    # If scan is already completed or failed, send a single event
    if scan.status in (Scan.Status.COMPLETED, Scan.Status.FAILED):
        def completed_stream():
            event = {
                "type": "scan_already_done",
                "status": scan.status,
                "total_urls": scan.total_urls,
            }
            yield f"data: {json.dumps(event)}\n\n"

        return StreamingHttpResponse(
            completed_stream(),
            content_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
            },
        )

    # Mark scan as running
    if scan.status == Scan.Status.PENDING:
        scan.mark_running()

    scanner_url = f"{settings.SCANNER_SERVICE_URL}/scan/stream"

    # ── Load auth config for authenticated scanning ──────────────────
    auth_payload = None
    try:
        # Try exact domain match first, then case-insensitive
        scan_domain = scan.domain.strip().lower()
        try:
            auth_cfg = SiteAuthConfig.objects.get(domain=scan_domain, is_enabled=True)
        except SiteAuthConfig.DoesNotExist:
            # Fallback: case-insensitive lookup
            auth_cfg = SiteAuthConfig.objects.filter(
                domain__iexact=scan_domain, is_enabled=True
            ).first()
            if auth_cfg is None:
                # Log all available configs for debugging
                all_configs = list(SiteAuthConfig.objects.values_list('domain', 'is_enabled', 'auth_type'))
                logger.warning(
                    f"Scan #{scan.id}: NO auth config for '{scan_domain}'. "
                    f"DB configs: {all_configs}"
                )
                raise SiteAuthConfig.DoesNotExist()
            else:
                logger.warning(f"Scan #{scan.id}: auth config found via iexact fallback: '{auth_cfg.domain}'")

        if auth_cfg.auth_type != "none":
            password = ""
            try:
                password = auth_cfg.get_password() or ""
            except Exception as pw_err:
                logger.warning(f"Scan #{scan.id}: get_password() failed: {pw_err}")
            auth_payload = {
                "auth_type": auth_cfg.auth_type,
                "auth_strategy": auth_cfg.auth_strategy or "auto",
                "login_url": auth_cfg.login_url,
                "username": auth_cfg.username,
                "password": password,
                "username_selector": auth_cfg.username_selector,
                "password_selector": auth_cfg.password_selector,
                "submit_selector": auth_cfg.submit_selector,
            }
            if auth_cfg.auth_type == "cookie" and auth_cfg.cookie_value:
                cookies = {}
                for part in auth_cfg.cookie_value.split(";"):
                    part = part.strip()
                    if "=" in part:
                        k, v = part.split("=", 1)
                        cookies[k.strip()] = v.strip()
                auth_payload["cookies"] = cookies
            if auth_cfg.auth_type == "interactive":
                auth_payload["home_url"] = auth_cfg.home_url or ""
                auth_payload["login_button_selector"] = auth_cfg.login_button_selector or ""
            if auth_cfg.auth_type == "recorded":
                auth_payload["recorded_steps"] = auth_cfg.recorded_steps or []
            # Include saved session cookies for reuse
            if auth_cfg.session_cookies and auth_cfg.auth_status == "success":
                from django.utils import timezone as tz
                if auth_cfg.session_valid_until and auth_cfg.session_valid_until > tz.now():
                    auth_payload["saved_session_cookies"] = auth_cfg.session_cookies
            logger.warning(
                f"Scan #{scan.id}: AUTH ENABLED type={auth_cfg.auth_type} domain='{auth_cfg.domain}' "
                f"has_steps={bool(auth_cfg.recorded_steps)} has_password={bool(password)}"
            )
        else:
            logger.warning(f"Scan #{scan.id}: auth config found but type='none', skipping auth")
    except SiteAuthConfig.DoesNotExist:
        logger.warning(f"Scan #{scan.id}: no auth config for domain '{scan.domain}' — scanning without auth")
    except Exception as e:
        logger.warning(f"Scan #{scan.id}: auth config ERROR: {type(e).__name__}: {e}")
        import traceback
        logger.warning(traceback.format_exc())
        auth_payload = None

    def stream_proxy():
        """POST to scanner service and relay the SSE chunks."""
        try:
            payload = {
                "scan_id": scan.id,
                "domain": scan.domain,
                "max_depth": scan.max_depth,
                "max_pages": scan.max_pages,
            }
            if auth_payload:
                payload["auth_config"] = auth_payload

            resp = requests.post(
                scanner_url,
                json=payload,
                stream=True,
                timeout=(30, 900),
            )

            results_data = None
            auth_result = {}

            for line in resp.iter_lines(decode_unicode=True):
                if not line:
                    continue
                # Forward SSE comments (keepalive heartbeats)
                if line.startswith(":"):
                    yield f"{line}\n\n"
                    continue
                if line.startswith("data: "):
                    data_str = line[6:]
                    yield f"data: {data_str}\n\n"

                    # Check for results and auth events to save to DB
                    try:
                        event = json.loads(data_str)
                        if event.get("type") == "results":
                            results_data = event
                        elif event.get("type") == "auth_success":
                            auth_result = {"success": True, "method": event.get("method", ""), "error": ""}
                        elif event.get("type") == "auth_error":
                            auth_result = {"success": False, "method": event.get("method", ""), "error": event.get("error", "")}
                    except json.JSONDecodeError:
                        pass

            # Save auth result to scan
            if auth_result:
                scan.auth_success = auth_result.get("success")
                scan.auth_method = auth_result.get("method", "")
                scan.auth_error = auth_result.get("error", "")
                scan.save(update_fields=["auth_success", "auth_method", "auth_error", "updated_at"])

                # Update SiteAuthConfig status
                try:
                    auth_cfg = (
                        SiteAuthConfig.objects.filter(domain__iexact=scan.domain.strip().lower(), is_enabled=True).first()
                        or SiteAuthConfig.objects.get(domain=scan.domain, is_enabled=True)
                    )
                    from django.utils import timezone as tz
                    if auth_result.get("success"):
                        auth_cfg.auth_status = SiteAuthConfig.AuthStatus.SUCCESS
                        auth_cfg.last_error = ""
                        cookies = (results_data or {}).get("session_cookies", {})
                        if cookies:
                            auth_cfg.session_cookies = cookies
                            auth_cfg.session_valid_until = tz.now() + tz.timedelta(hours=2)
                    else:
                        auth_cfg.auth_status = SiteAuthConfig.AuthStatus.FAILED
                        auth_cfg.last_error = auth_result.get("error", "")
                    auth_cfg.last_test_at = tz.now()
                    auth_cfg.save()
                except SiteAuthConfig.DoesNotExist:
                    pass

            # Save results to DB after stream ends
            if results_data:
                _save_scan_results(scan, results_data.get("urls", []))

                # ─── Phase 5: Domain Reputation Check (SSE) ──────────────
                yield from _reputation_phase_sse(scan)

                # Signal to frontend that everything is truly done
                yield f"data: {json.dumps({'type': 'scan_fully_complete'})}\n\n"

        except requests.exceptions.ConnectionError as e:
            logger.error(f"Scanner service connection error: {e}")
            error_event = {"type": "scan_error", "error": "Scanner service unavailable"}
            yield f"data: {json.dumps(error_event)}\n\n"
            scan.mark_failed("Scanner service unavailable")
        except Exception as e:
            logger.exception(f"Stream proxy error for scan #{scan_id}")
            error_event = {"type": "scan_error", "error": str(e)}
            yield f"data: {json.dumps(error_event)}\n\n"
            scan.mark_failed(str(e))

    return StreamingHttpResponse(
        stream_proxy(),
        content_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


def _save_scan_results(scan, urls_data):
    """Save scan results to the database (called after SSE stream finishes)."""
    from .models import DiscoveredURL, DiffURL, ScanDiff

    url_objects = []
    for url_info in urls_data:
        url_objects.append(
            DiscoveredURL(
                scan=scan,
                url=url_info["url"],
                source=url_info.get("source", "html"),
                status_code=url_info.get("status_code"),
                content_type=url_info.get("content_type", ""),
                depth=url_info.get("depth", 0),
                is_internal=url_info.get("is_internal", True),
                external_domain=url_info.get("external_domain", ""),
                source_url=url_info.get("source_url", ""),
                is_private=url_info.get("is_private", False),
                is_sensitive=url_info.get("is_sensitive", False),
            )
        )
    DiscoveredURL.objects.bulk_create(url_objects, ignore_conflicts=True)

    # Run diff against previous scan
    previous_scan = (
        Scan.objects.filter(
            domain=scan.domain,
            status=Scan.Status.COMPLETED,
            id__lt=scan.id,
        )
        .order_by("-id")
        .first()
    )

    new_urls_count = 0
    if previous_scan:
        current_urls = set(scan.urls.values_list("url", flat=True))
        previous_urls = set(previous_scan.urls.values_list("url", flat=True))
        new_urls = current_urls - previous_urls
        removed_urls = previous_urls - current_urls
        new_urls_count = len(new_urls)

        scan.urls.filter(url__in=new_urls).update(is_new=True)

        diff = ScanDiff.objects.create(
            current_scan=scan,
            previous_scan=previous_scan,
            new_urls_count=len(new_urls),
            removed_urls_count=len(removed_urls),
        )

        diff_url_objects = []
        for url in new_urls:
            diff_url_objects.append(DiffURL(diff=diff, url=url, change_type="added"))
        for url in removed_urls:
            diff_url_objects.append(DiffURL(diff=diff, url=url, change_type="removed"))
        DiffURL.objects.bulk_create(diff_url_objects)
    else:
        scan.urls.all().update(is_new=True)
        new_urls_count = len(urls_data)

    scan.mark_completed(total_urls=len(urls_data), new_urls=new_urls_count)
    logger.info(f"Scan #{scan.id} completed via stream: {len(urls_data)} URLs")

    # ─── External Domain Monitoring ──────────────────────────────────────
    # skip_reputation=True because reputation is handled inline in SSE stream
    _process_external_domains(scan, skip_reputation=True)


def _reputation_phase_sse(scan):
    """
    Generator that runs reputation checks on discovered external domains
    and yields SSE events for real-time progress in the live scan view.
    """
    from .reputation import (
        analyze_domain as _rep_analyze,
        _safe_browsing_batch,
        _virustotal_check,
        _aggregate_risk,
        _save_reputation,
        _is_cache_valid,
        RiskLevel,
    )

    # Collect unique external domains from this scan
    external_domains = list(
        scan.urls.filter(is_internal=False)
        .exclude(external_domain="")
        .values_list("external_domain", flat=True)
        .distinct()
    )

    if not external_domains:
        return

    # Normalize
    normalized = []
    for d in external_domains:
        norm = rep_normalize(d)
        if norm and norm not in normalized:
            normalized.append(norm)

    total = len(normalized)
    if total == 0:
        return

    # Emit phase_start
    yield f"data: {json.dumps({'type': 'phase_start', 'phase': 'reputation', 'module': 'Domain Reputation', 'total_domains': total})}\n\n"

    checked = 0
    high_risk = 0
    medium_risk = 0
    low_risk = 0
    failed = 0

    try:
        # Batch Safe Browsing check for all domains at once
        yield f"data: {json.dumps({'type': 'reputation_progress', 'step': 'safe_browsing', 'message': f'Checking {total} domains via Google Safe Browsing...', 'checked': 0, 'total': total})}\n\n"

        safe_results = _safe_browsing_batch(normalized)

        yield f"data: {json.dumps({'type': 'reputation_progress', 'step': 'safe_browsing_done', 'message': 'Safe Browsing check complete', 'checked': 0, 'total': total})}\n\n"

        # Check each domain via VirusTotal + save results
        for domain in normalized:
            checked += 1

            yield f"data: {json.dumps({'type': 'reputation_progress', 'step': 'virustotal', 'domain': domain, 'message': f'Checking {domain}...', 'checked': checked, 'total': total})}\n\n"

            try:
                rep, _ = DomainReputation.objects.get_or_create(domain=domain)

                if _is_cache_valid(rep):
                    risk = rep.risk_level
                else:
                    rep.check_status = DomainReputation.CheckStatus.CHECKING
                    rep.save(update_fields=["check_status", "updated_at"])

                    safe_result = safe_results.get(domain, {
                        "matched": False, "threats": [], "risk": RiskLevel.UNKNOWN
                    })
                    vt_result = _virustotal_check(domain)
                    _save_reputation(rep, safe_result, vt_result)
                    risk = rep.risk_level

                if risk == "high":
                    high_risk += 1
                elif risk == "medium":
                    medium_risk += 1
                elif risk == "low":
                    low_risk += 1

                yield f"data: {json.dumps({'type': 'reputation_domain_checked', 'domain': domain, 'risk_level': risk, 'check_status': rep.check_status, 'checked': checked, 'total': total, 'virustotal_malicious': rep.virustotal_malicious, 'virustotal_suspicious': rep.virustotal_suspicious})}\n\n"

            except Exception as exc:
                failed += 1
                logger.warning(f"Reputation check failed for {domain}: {exc}")

                yield f"data: {json.dumps({'type': 'reputation_domain_checked', 'domain': domain, 'risk_level': 'unknown', 'check_status': 'failed', 'checked': checked, 'total': total, 'error': str(exc)})}\n\n"

        # Emit phase_complete
        yield f"data: {json.dumps({'type': 'phase_complete', 'phase': 'reputation', 'module': 'Domain Reputation', 'urls_found': total, 'high_risk': high_risk, 'medium_risk': medium_risk, 'low_risk': low_risk, 'failed': failed})}\n\n"

    except Exception as exc:
        logger.exception(f"Reputation phase failed for scan #{scan.id}")
        yield f"data: {json.dumps({'type': 'phase_error', 'phase': 'reputation', 'module': 'Domain Reputation', 'error': str(exc)})}\n\n"


def _process_external_domains(scan, skip_reputation=False):
    """
    After a scan completes, process external domains:
    - Normalize and deduplicate
    - Check for suspicious domains
    - Create/update ExternalDomainEntry records
    - Classify against whitelist/blacklist
    - Compare with previous scan to detect new/removed domains
    - Generate alerts for new, suspicious, and blacklisted domains
    """
    from .models import (
        ExternalDomainEntry, ExternalDomainAlert, DomainListEntry,
        normalize_domain, check_suspicious,
    )

    site_domain = scan.domain

    # Collect all external domains from this scan with their source pages
    external_urls = scan.urls.filter(is_internal=False).exclude(external_domain="")
    domain_pages_map = {}  # normalized_domain -> set of source_urls

    for eu in external_urls:
        norm_domain = normalize_domain(eu.external_domain)
        if not norm_domain:
            continue
        if norm_domain not in domain_pages_map:
            domain_pages_map[norm_domain] = set()
        if eu.source_url:
            domain_pages_map[norm_domain].add(eu.source_url)

    current_domains = set(domain_pages_map.keys())

    # Bulk-classify all domains against whitelist/blacklist
    classification = DomainListEntry.classify_domains_bulk(
        site_domain, list(current_domains)
    )

    # Get previous external domains for this site
    previous_entries = ExternalDomainEntry.objects.filter(site_domain=site_domain)
    previous_domains = set(previous_entries.values_list("domain", flat=True))

    new_domains = current_domains - previous_domains
    removed_domains = previous_domains - current_domains
    existing_domains = current_domains & previous_domains

    # Update existing domain entries
    for domain in existing_domains:
        pages = list(domain_pages_map.get(domain, set()))[:20]
        entry = previous_entries.filter(domain=domain).first()
        if entry:
            entry.last_seen_scan = scan
            entry.times_seen += 1
            entry.found_on_pages = pages
            # Re-classify
            entry.list_classification = classification.get(domain, "unknown")
            is_susp, reasons = check_suspicious(domain)
            if is_susp and not entry.is_suspicious:
                entry.is_suspicious = True
                entry.suspicious_reasons = reasons
                entry.status = ExternalDomainEntry.Status.SUSPICIOUS
            elif not is_susp and entry.status == ExternalDomainEntry.Status.NEW:
                if entry.list_classification == "whitelist":
                    entry.status = ExternalDomainEntry.Status.SAFE
                else:
                    entry.status = ExternalDomainEntry.Status.SAFE
            entry.save()

    # Create entries for new domains
    blacklist_hits = []
    for domain in new_domains:
        pages = list(domain_pages_map.get(domain, set()))[:20]
        is_susp, reasons = check_suspicious(domain)
        domain_class = classification.get(domain, "unknown")

        entry_status = ExternalDomainEntry.Status.NEW
        if is_susp:
            entry_status = ExternalDomainEntry.Status.SUSPICIOUS
        elif domain_class == "whitelist":
            entry_status = ExternalDomainEntry.Status.SAFE

        ExternalDomainEntry.objects.create(
            site_domain=site_domain,
            domain=domain,
            status=entry_status,
            list_classification=domain_class,
            is_suspicious=is_susp,
            suspicious_reasons=reasons,
            first_seen_scan=scan,
            last_seen_scan=scan,
            times_seen=1,
            found_on_pages=pages,
        )

        # Track blacklist hits
        if domain_class == "blacklist":
            blacklist_hits.append(domain)

        # Generate alert for new domain
        severity = ExternalDomainAlert.Severity.INFO
        alert_type = ExternalDomainAlert.AlertType.NEW_DOMAIN
        message = f"New external domain discovered: {domain}"

        if domain_class == "blacklist":
            severity = ExternalDomainAlert.Severity.CRITICAL
            alert_type = ExternalDomainAlert.AlertType.BLACKLIST_HIT
            message = (
                f"🚨 Blacklisted domain detected: {domain}\n"
                f"This domain is on your blacklist."
            )
            if pages:
                message += f"\nFound on: {', '.join(list(pages)[:5])}"
        elif is_susp:
            severity = ExternalDomainAlert.Severity.CRITICAL
            alert_type = ExternalDomainAlert.AlertType.SUSPICIOUS_DOMAIN
            message = (
                f"🚨 Suspicious external domain detected: {domain}\n"
                f"Reasons: {', '.join(reasons)}"
            )
            if pages:
                message += f"\nFound on: {', '.join(list(pages)[:5])}"
        elif domain_class == "whitelist":
            # Whitelisted: log only, no alert
            continue

        ExternalDomainAlert.objects.create(
            scan=scan,
            site_domain=site_domain,
            external_domain=domain,
            alert_type=alert_type,
            severity=severity,
            message=message,
        )

    # Check existing domains that are now blacklisted (re-classification)
    for domain in existing_domains:
        domain_class = classification.get(domain, "unknown")
        if domain_class == "blacklist":
            # Check if we already have a recent blacklist alert for this domain
            recent_bl_alert = ExternalDomainAlert.objects.filter(
                site_domain=site_domain,
                external_domain=domain,
                alert_type=ExternalDomainAlert.AlertType.BLACKLIST_HIT,
                scan=scan,
            ).exists()
            if not recent_bl_alert:
                blacklist_hits.append(domain)
                ExternalDomainAlert.objects.create(
                    scan=scan,
                    site_domain=site_domain,
                    external_domain=domain,
                    alert_type=ExternalDomainAlert.AlertType.BLACKLIST_HIT,
                    severity=ExternalDomainAlert.Severity.CRITICAL,
                    message=f"🚨 Blacklisted domain still present: {domain}",
                )

    # Generate alerts for removed domains
    for domain in removed_domains:
        ExternalDomainAlert.objects.create(
            scan=scan,
            site_domain=site_domain,
            external_domain=domain,
            alert_type=ExternalDomainAlert.AlertType.REMOVED_DOMAIN,
            severity=ExternalDomainAlert.Severity.WARNING,
            message=f"External domain no longer found: {domain}",
        )

    logger.info(
        f"External monitoring for {site_domain}: "
        f"{len(new_domains)} new, {len(removed_domains)} removed, "
        f"{len(existing_domains)} existing, {len(blacklist_hits)} blacklist hits"
    )

    # Queue reputation checks (high priority for newly discovered domains)
    if not skip_reputation:
        if new_domains:
            enqueue_domains(list(new_domains), priority="high")
        if existing_domains:
            enqueue_domains(list(existing_domains), priority="low")
        if new_domains or existing_domains:
            process_reputation_queue_task.delay()


# ─── External Monitoring API Endpoints ───────────────────────────────────────


@api_view(["GET"])
def external_monitoring(request):
    """
    Get external monitoring data for a domain.
    Query params: domain (optional - if not provided, returns global stats)
    Returns: summary, domains list, recent alerts
    """
    site_domain = request.query_params.get("domain")
    if site_domain:
        all_entries = ExternalDomainEntry.objects.filter(site_domain=site_domain)
        all_alerts = ExternalDomainAlert.objects.filter(site_domain=site_domain)
    else:
        all_entries = ExternalDomainEntry.objects.all()
        all_alerts = ExternalDomainAlert.objects.all()

    summary = {
        "total_external_domains": all_entries.count(),
        "new_domains": all_entries.filter(status="new").count(),
        "suspicious_domains": all_entries.filter(is_suspicious=True).count(),
        "safe_domains": all_entries.filter(status="safe").count(),
        "unread_alerts": all_alerts.filter(is_read=False).count(),
        "total_alerts": all_alerts.count(),
        "whitelist_domains": all_entries.filter(list_classification="whitelist").count(),
        "blacklist_domains": all_entries.filter(list_classification="blacklist").count(),
        "unknown_domains": all_entries.filter(list_classification="unknown").count(),
    }

    entries = list(all_entries[:100])
    domains = ExternalDomainEntrySerializer(entries, many=True).data

    rep_map = {
        r.domain: r
        for r in DomainReputation.objects.filter(
            domain__in=[entry.domain for entry in entries]
        )
    }

    for item in domains:
        rep = rep_map.get(item["domain"])
        item["reputation"] = DomainReputationSerializer(rep).data if rep else None

    rep_qs = DomainReputation.objects.filter(domain__in=[entry.domain for entry in entries])
    reputation_summary = {
        "total": rep_qs.count(),
        "high_risk": rep_qs.filter(risk_level=DomainReputation.RiskLevel.HIGH).count(),
        "medium_risk": rep_qs.filter(risk_level=DomainReputation.RiskLevel.MEDIUM).count(),
        "low_risk": rep_qs.filter(risk_level=DomainReputation.RiskLevel.LOW).count(),
        "unknown_risk": rep_qs.filter(risk_level=DomainReputation.RiskLevel.UNKNOWN).count(),
        "pending": rep_qs.filter(check_status=DomainReputation.CheckStatus.PENDING).count(),
        "checking": rep_qs.filter(check_status=DomainReputation.CheckStatus.CHECKING).count(),
        "completed": rep_qs.filter(check_status=DomainReputation.CheckStatus.COMPLETED).count(),
        "failed": rep_qs.filter(check_status=DomainReputation.CheckStatus.FAILED).count(),
    }

    alerts = ExternalDomainAlertSerializer(all_alerts[:50], many=True).data

    return Response({
        "summary": summary,
        "reputation_summary": reputation_summary,
        "domains": domains,
        "alerts": alerts,
    })


@api_view(["GET"])
def external_domain_timeline(request):
    """
    Get timeline of external domain discoveries for a site.
    Query params: domain (required)
    """
    site_domain = request.query_params.get("domain")
    if not site_domain:
        return Response({"error": "domain parameter required"}, status=400)

    entries = (
        ExternalDomainEntry.objects.filter(site_domain=site_domain)
        .order_by("first_seen")
    )

    timeline = []
    for entry in entries:
        timeline.append({
            "domain": entry.domain,
            "first_seen": entry.first_seen,
            "last_seen": entry.last_seen,
            "status": entry.status,
            "is_suspicious": entry.is_suspicious,
            "suspicious_reasons": entry.suspicious_reasons,
            "times_seen": entry.times_seen,
            "scan_id": entry.first_seen_scan_id,
        })

    return Response(timeline)


@api_view(["GET"])
def external_domain_detail(request, domain):
    """
    Get details for a specific external domain.
    Query params: site_domain (required)
    """
    site_domain = request.query_params.get("site_domain")
    if not site_domain:
        return Response({"error": "site_domain parameter required"}, status=400)

    try:
        entry = ExternalDomainEntry.objects.get(
            site_domain=site_domain, domain=domain
        )
    except ExternalDomainEntry.DoesNotExist:
        return Response({"error": "Domain not found"}, status=404)

    # Get all URLs pointing to this domain
    related_urls = (
        DiscoveredURL.objects.filter(
            scan__domain=site_domain,
            external_domain__icontains=domain,
            is_internal=False,
        )
        .values("url", "source", "status_code", "source_url", "scan_id")
        .order_by("-scan_id")[:100]
    )

    alerts = ExternalDomainAlertSerializer(
        ExternalDomainAlert.objects.filter(
            site_domain=site_domain, external_domain=domain
        )[:20],
        many=True,
    ).data

    return Response({
        "entry": ExternalDomainEntrySerializer(entry).data,
        "urls": list(related_urls),
        "alerts": alerts,
    })


@api_view(["POST"])
def mark_alerts_read(request):
    """Mark alerts as read."""
    alert_ids = request.data.get("alert_ids", [])
    site_domain = request.data.get("site_domain")

    if alert_ids:
        ExternalDomainAlert.objects.filter(id__in=alert_ids).update(is_read=True)
    elif site_domain:
        ExternalDomainAlert.objects.filter(
            site_domain=site_domain
        ).update(is_read=True)

    return Response({"status": "ok"})


@api_view(["POST"])
def mark_domain_safe(request):
    """Manually mark a domain as safe."""
    site_domain = request.data.get("site_domain")
    domain = request.data.get("domain")

    if not site_domain or not domain:
        return Response(
            {"error": "site_domain and domain required"}, status=400
        )

    try:
        entry = ExternalDomainEntry.objects.get(
            site_domain=site_domain, domain=domain
        )
        entry.status = ExternalDomainEntry.Status.SAFE
        entry.is_suspicious = False
        entry.suspicious_reasons = []
        entry.save()
        return Response(ExternalDomainEntrySerializer(entry).data)
    except ExternalDomainEntry.DoesNotExist:
        return Response({"error": "Domain not found"}, status=404)


@api_view(["GET"])
def reputation_list(request):
    """Get cached reputation checks with optional site filter."""
    site_domain = request.query_params.get("site_domain", "")

    qs = DomainReputation.objects.all()
    if site_domain:
        domains = ExternalDomainEntry.objects.filter(site_domain=site_domain).values_list(
            "domain", flat=True
        )
        qs = qs.filter(domain__in=domains)

    results = DomainReputationSerializer(qs[:200], many=True).data
    summary_data = {
        "total": qs.count(),
        "high_risk": qs.filter(risk_level=DomainReputation.RiskLevel.HIGH).count(),
        "medium_risk": qs.filter(risk_level=DomainReputation.RiskLevel.MEDIUM).count(),
        "low_risk": qs.filter(risk_level=DomainReputation.RiskLevel.LOW).count(),
        "unknown_risk": qs.filter(risk_level=DomainReputation.RiskLevel.UNKNOWN).count(),
        "pending": qs.filter(check_status=DomainReputation.CheckStatus.PENDING).count(),
        "checking": qs.filter(check_status=DomainReputation.CheckStatus.CHECKING).count(),
        "completed": qs.filter(check_status=DomainReputation.CheckStatus.COMPLETED).count(),
        "failed": qs.filter(check_status=DomainReputation.CheckStatus.FAILED).count(),
    }

    return Response(
        {
            "summary": ReputationSummarySerializer(summary_data).data,
            "results": results,
        }
    )


@api_view(["POST"])
def check_reputation(request):
    """Queue or force-check a single domain reputation."""
    domain = request.data.get("domain", "")
    force = bool(request.data.get("force", False))

    if not domain:
        return Response({"error": "domain required"}, status=400)

    if force:
        reputation = analyze_domain(domain, force=True)
        return Response(DomainReputationSerializer(reputation).data)

    queued = enqueue_domain(domain, priority="high")
    if not queued:
        return Response({"error": "invalid domain"}, status=400)

    process_reputation_queue_task.delay()

    return Response({"status": "queued", "domain": domain})


@api_view(["POST"])
def check_all_reputations(request):
    """Queue checks for all tracked external domains."""
    site_domain = request.data.get("site_domain", "")

    entries = ExternalDomainEntry.objects.all()
    if site_domain:
        entries = entries.filter(site_domain=site_domain)

    domains = list(entries.values_list("domain", flat=True).distinct())
    queued = enqueue_domains(domains, priority="high")
    if queued:
        process_reputation_queue_task.delay()
    return Response({"status": "queued", "queued": queued})


# ─── Blacklist / Whitelist Endpoints ─────────────────────────────────────────


@api_view(["GET"])
def domain_lists(request):
    """
    GET whitelist/blacklist for a site.
    Query params: site_domain (required), list_type (optional: whitelist/blacklist)
    """
    site_domain = request.query_params.get("site_domain")
    if not site_domain:
        return Response({"error": "site_domain parameter required"}, status=400)

    qs = DomainListEntry.objects.filter(site_domain=site_domain)
    list_type = request.query_params.get("list_type")
    if list_type in ("whitelist", "blacklist"):
        qs = qs.filter(list_type=list_type)

    whitelist = DomainListEntrySerializer(
        qs.filter(list_type="whitelist"), many=True
    ).data
    blacklist = DomainListEntrySerializer(
        qs.filter(list_type="blacklist"), many=True
    ).data

    # Classification summary from ExternalDomainEntry
    entries = ExternalDomainEntry.objects.filter(site_domain=site_domain)
    classification = {
        "total": entries.count(),
        "whitelist": entries.filter(list_classification="whitelist").count(),
        "blacklist": entries.filter(list_classification="blacklist").count(),
        "unknown": entries.filter(list_classification="unknown").count(),
    }

    return Response({
        "site_domain": site_domain,
        "whitelist": whitelist,
        "blacklist": blacklist,
        "classification": classification,
    })


@api_view(["POST"])
def domain_lists_add(request):
    """
    POST add domains to whitelist or blacklist (supports bulk).
    Body: { site_domain, domains: [...], list_type: "whitelist"|"blacklist", note? }
    """
    from .models import normalize_domain

    serializer = DomainListEntryCreateSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    site_domain = serializer.validated_data["site_domain"]
    domains = serializer.validated_data["domains"]
    list_type = serializer.validated_data["list_type"]
    note = serializer.validated_data.get("note", "")

    created = []
    skipped = []
    moved = []

    opposite_type = "blacklist" if list_type == "whitelist" else "whitelist"

    for domain in domains:
        # If domain is in opposite list, remove it (conflict resolution)
        opposite = DomainListEntry.objects.filter(
            site_domain=site_domain,
            domain=domain,
            list_type=opposite_type,
        )
        if opposite.exists():
            opposite.delete()
            moved.append(domain)

        entry, was_created = DomainListEntry.objects.get_or_create(
            site_domain=site_domain,
            domain=domain,
            list_type=list_type,
            defaults={"note": note, "added_by": "user"},
        )
        if was_created:
            created.append(domain)
        else:
            skipped.append(domain)

    # Re-classify existing ExternalDomainEntry records
    _reclassify_domains(site_domain, domains)

    return Response({
        "status": "ok",
        "created": created,
        "skipped": skipped,
        "moved_from_opposite": moved,
        "total_created": len(created),
    }, status=status.HTTP_201_CREATED)


@api_view(["DELETE"])
def domain_lists_remove(request, entry_id):
    """DELETE a single domain list entry."""
    try:
        entry = DomainListEntry.objects.get(id=entry_id)
    except DomainListEntry.DoesNotExist:
        return Response({"error": "Entry not found"}, status=404)

    site_domain = entry.site_domain
    domain = entry.domain
    entry.delete()

    # Re-classify this domain
    _reclassify_domains(site_domain, [domain])

    return Response(status=status.HTTP_204_NO_CONTENT)


@api_view(["POST"])
def domain_lists_quick_action(request):
    """
    Quick action: add a domain to whitelist or blacklist from scan results.
    Body: { site_domain, domain, list_type: "whitelist"|"blacklist" }
    """
    from .models import normalize_domain

    site_domain = request.data.get("site_domain")
    domain = request.data.get("domain")
    list_type = request.data.get("list_type")

    if not all([site_domain, domain, list_type]):
        return Response(
            {"error": "site_domain, domain, and list_type required"}, status=400
        )
    if list_type not in ("whitelist", "blacklist"):
        return Response({"error": "list_type must be whitelist or blacklist"}, status=400)

    normalized = normalize_domain(domain.strip().lower())
    if not normalized:
        return Response({"error": "Invalid domain"}, status=400)

    opposite_type = "blacklist" if list_type == "whitelist" else "whitelist"

    # Remove from opposite list if present
    DomainListEntry.objects.filter(
        site_domain=site_domain, domain=normalized, list_type=opposite_type,
    ).delete()

    entry, created = DomainListEntry.objects.get_or_create(
        site_domain=site_domain,
        domain=normalized,
        list_type=list_type,
        defaults={"note": "Added via quick action", "added_by": "user"},
    )

    # Re-classify
    _reclassify_domains(site_domain, [normalized])

    return Response({
        "status": "ok",
        "entry": DomainListEntrySerializer(entry).data,
        "created": created,
    })


@api_view(["POST"])
def domain_lists_bulk_clear(request):
    """
    Clear all entries from a list.
    Body: { site_domain, list_type: "whitelist"|"blacklist" }
    """
    site_domain = request.data.get("site_domain")
    list_type = request.data.get("list_type")

    if not site_domain or list_type not in ("whitelist", "blacklist"):
        return Response({"error": "site_domain and valid list_type required"}, status=400)

    affected_domains = list(
        DomainListEntry.objects.filter(
            site_domain=site_domain, list_type=list_type,
        ).values_list("domain", flat=True)
    )

    count, _ = DomainListEntry.objects.filter(
        site_domain=site_domain, list_type=list_type,
    ).delete()

    # Re-classify all affected domains
    if affected_domains:
        _reclassify_domains(site_domain, affected_domains)

    return Response({"status": "ok", "deleted": count})


@api_view(["GET"])
def domain_lists_suggestions(request):
    """
    Get auto-suggestions for domains that should be whitelisted.
    Suggests domains seen many times that aren't in any list.
    Query params: site_domain (required)
    """
    site_domain = request.query_params.get("site_domain")
    if not site_domain:
        return Response({"error": "site_domain parameter required"}, status=400)

    suggestions = (
        ExternalDomainEntry.objects.filter(
            site_domain=site_domain,
            list_classification="unknown",
            is_suspicious=False,
            times_seen__gte=5,
        )
        .order_by("-times_seen")[:20]
    )

    return Response({
        "suggestions": [
            {
                "domain": s.domain,
                "times_seen": s.times_seen,
                "first_seen": s.first_seen,
                "status": s.status,
            }
            for s in suggestions
        ]
    })


def _reclassify_domains(site_domain: str, domains: list[str]):
    """Re-classify ExternalDomainEntry records after a list change."""
    from .models import normalize_domain as _norm

    normalized = [_norm(d) for d in domains if _norm(d)]
    if not normalized:
        return

    classification = DomainListEntry.classify_domains_bulk(site_domain, normalized)

    for norm_domain, cls in classification.items():
        ExternalDomainEntry.objects.filter(
            site_domain=site_domain, domain=norm_domain,
        ).update(list_classification=cls)


# ─── Real-Time Monitoring Endpoints ─────────────────────────────────────────


@api_view(["GET"])
def realtime_monitoring_status(request):
    """
    GET overall real-time monitoring status.
    Returns all configs + aggregated stats.
    """
    from django.db.models import Sum

    configs = SiteMonitorConfig.objects.all()
    total_scans = configs.aggregate(s=Sum("total_light_scans"))["s"] or 0
    total_changes = configs.aggregate(s=Sum("changes_detected_count"))["s"] or 0

    # Total new domains found across all light scans
    total_new = LightScanResult.objects.filter(
        new_domains_count__gt=0
    ).aggregate(s=Sum("new_domains_count"))["s"] or 0

    data = {
        "total_configs": configs.count(),
        "active_configs": configs.filter(is_enabled=True).count(),
        "total_light_scans": total_scans,
        "total_changes_detected": total_changes,
        "total_new_domains_found": total_new,
        "configs": SiteMonitorConfigSerializer(configs, many=True).data,
    }
    return Response(data)


@api_view(["POST"])
def realtime_monitoring_create(request):
    """
    POST create a new monitoring config.
    Body: { domain, is_enabled?, interval_minutes?, key_pages? }
    """
    serializer = SiteMonitorConfigCreateSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    domain = serializer.validated_data["domain"]

    # Check if already exists
    existing = SiteMonitorConfig.objects.filter(domain=domain).first()
    if existing:
        return Response(
            {"error": f"Monitoring config for {domain} already exists", "config_id": existing.id},
            status=status.HTTP_409_CONFLICT,
        )

    config = serializer.save()
    logger.info(f"Created monitoring config for {domain}")
    return Response(
        SiteMonitorConfigSerializer(config).data,
        status=status.HTTP_201_CREATED,
    )


@api_view(["GET", "PATCH", "DELETE"])
def realtime_monitoring_detail(request, config_id):
    """
    GET / PATCH / DELETE a single monitoring config.
    """
    try:
        config = SiteMonitorConfig.objects.get(id=config_id)
    except SiteMonitorConfig.DoesNotExist:
        return Response({"error": "Config not found"}, status=404)

    if request.method == "GET":
        return Response(SiteMonitorConfigSerializer(config).data)

    if request.method == "DELETE":
        domain = config.domain
        config.delete()
        logger.info(f"Deleted monitoring config for {domain}")
        return Response(status=status.HTTP_204_NO_CONTENT)

    # PATCH
    allowed_fields = {"is_enabled", "interval_minutes", "key_pages"}
    for field, value in request.data.items():
        if field in allowed_fields:
            if field == "interval_minutes":
                value = max(5, min(1440, int(value)))
            setattr(config, field, value)

    config.save()
    logger.info(f"Updated monitoring config for {config.domain}")
    return Response(SiteMonitorConfigSerializer(config).data)


@api_view(["POST"])
def realtime_monitoring_toggle(request, config_id):
    """Toggle monitoring ON/OFF for a config."""
    try:
        config = SiteMonitorConfig.objects.get(id=config_id)
    except SiteMonitorConfig.DoesNotExist:
        return Response({"error": "Config not found"}, status=404)

    config.is_enabled = not config.is_enabled

    # If re-enabling, schedule next scan
    if config.is_enabled:
        from datetime import timedelta
        from django.utils import timezone
        config.next_scan_at = timezone.now() + timedelta(minutes=1)

    config.save(update_fields=["is_enabled", "next_scan_at", "updated_at"])
    state = "enabled" if config.is_enabled else "disabled"
    logger.info(f"Monitoring {state} for {config.domain}")
    return Response(SiteMonitorConfigSerializer(config).data)


@api_view(["POST"])
def realtime_monitoring_scan_now(request, config_id):
    """Trigger an immediate light scan for a config."""
    from .tasks import light_scan_task

    try:
        config = SiteMonitorConfig.objects.get(id=config_id)
    except SiteMonitorConfig.DoesNotExist:
        return Response({"error": "Config not found"}, status=404)

    light_scan_task.delay(config.id)
    return Response({"status": "queued", "domain": config.domain})


@api_view(["GET"])
def realtime_monitoring_history(request, config_id):
    """Get light scan history for a specific monitoring config."""
    try:
        config = SiteMonitorConfig.objects.get(id=config_id)
    except SiteMonitorConfig.DoesNotExist:
        return Response({"error": "Config not found"}, status=404)

    limit = int(request.query_params.get("limit", 50))
    results = config.light_scan_results.all()[:limit]
    return Response({
        "domain": config.domain,
        "total": config.light_scan_results.count(),
        "results": LightScanResultSerializer(results, many=True).data,
    })


@api_view(["GET"])
def realtime_monitoring_latest(request):
    """
    GET latest light scan results across all monitored sites.
    Useful for the dashboard view.
    """
    limit = int(request.query_params.get("limit", 20))
    results = LightScanResult.objects.select_related("site_config").all()[:limit]
    return Response({
        "results": LightScanResultSerializer(results, many=True).data,
    })


# ─── Authenticated Scanning ─────────────────────────────────────────────────


@api_view(["GET"])
def auth_config_get(request):
    """
    GET auth config for a site domain.
    ?domain=example.com
    """
    domain = request.query_params.get("domain", "").strip().lower()
    if not domain:
        return Response({"error": "domain param required"}, status=400)

    try:
        config = SiteAuthConfig.objects.get(domain=domain)
        return Response(SiteAuthConfigSerializer(config).data)
    except SiteAuthConfig.DoesNotExist:
        # Fallback: case-insensitive lookup for legacy entries
        config = SiteAuthConfig.objects.filter(domain__iexact=domain).first()
        if config:
            return Response(SiteAuthConfigSerializer(config).data)
        return Response({
            "domain": domain,
            "auth_type": "none",
            "auth_strategy": "auto",
            "is_enabled": False,
            "login_url": "",
            "username": "",
            "has_password": False,
            "username_selector": "",
            "password_selector": "",
            "submit_selector": "",
            "login_button_selector": "",
            "home_url": "",
            "recorded_steps": [],
            "cookie_value": "",
            "auth_status": "untested",
            "last_test_at": None,
            "last_error": "",
            "session_valid_until": None,
            "created_at": None,
            "updated_at": None,
        })


@api_view(["POST"])
def auth_config_save(request):
    """
    POST — create or update auth config for a domain.
    """
    serializer = SiteAuthConfigWriteSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data

    domain = data["domain"].strip().lower()
    if domain.startswith("http://") or domain.startswith("https://"):
        from urllib.parse import urlparse
        domain = urlparse(domain).netloc or domain
    config, created = SiteAuthConfig.objects.get_or_create(domain=domain)

    config.auth_type = data["auth_type"]
    config.auth_strategy = data.get("auth_strategy", "auto")
    config.is_enabled = data.get("is_enabled", False)
    config.login_url = data.get("login_url", "")
    config.username = data.get("username", "")
    config.username_selector = data.get("username_selector", "")
    config.password_selector = data.get("password_selector", "")
    config.submit_selector = data.get("submit_selector", "")
    config.cookie_value = data.get("cookie_value", "")
    config.login_button_selector = data.get("login_button_selector", "")
    config.home_url = data.get("home_url", "")
    config.recorded_steps = data.get("recorded_steps", [])

    # Only update password if provided (non-empty)
    password = data.get("password", "")
    if password:
        config.set_password(password)

    # If switching to 'none', disable and reset
    if config.auth_type == "none":
        config.is_enabled = False
        config.auth_status = SiteAuthConfig.AuthStatus.UNTESTED

    config.save()

    return Response(SiteAuthConfigSerializer(config).data, status=200 if not created else 201)


@api_view(["POST"])
def auth_config_test(request):
    """
    POST — test login with the saved auth config.
    Attempts to authenticate and reports success/failure.
    """
    domain = request.data.get("domain", "").strip().lower()
    if not domain:
        return Response({"error": "domain is required"}, status=400)

    try:
        config = SiteAuthConfig.objects.get(domain=domain)
    except SiteAuthConfig.DoesNotExist:
        return Response({"error": "No auth config found for this domain"}, status=404)

    if config.auth_type == "none":
        return Response({"error": "Auth type is set to None"}, status=400)

    # Call the scanner service to test the login
    try:
        scanner_url = f"{settings.SCANNER_SERVICE_URL}/auth/test"
        payload = {
            "domain": config.domain,
            "auth_type": config.auth_type,
            "auth_strategy": config.auth_strategy or "auto",
        }
        if config.auth_type == "form":
            payload.update({
                "login_url": config.login_url,
                "username": config.username,
                "password": config.get_password(),
                "username_selector": config.username_selector or "",
                "password_selector": config.password_selector or "",
                "submit_selector": config.submit_selector or "",
            })
        elif config.auth_type == "cookie":
            payload["cookies"] = config.get_cookies_dict()
        elif config.auth_type == "interactive":
            payload.update({
                "home_url": config.home_url or "",
                "login_url": config.login_url or "",
                "username": config.username,
                "password": config.get_password(),
                "login_button_selector": config.login_button_selector or "",
                "username_selector": config.username_selector or "",
                "password_selector": config.password_selector or "",
                "submit_selector": config.submit_selector or "",
            })
        elif config.auth_type == "recorded":
            payload.update({
                "recorded_steps": config.recorded_steps or [],
                "username": config.username or "",
                "password": config.get_password() or "",
                "login_url": config.login_url or "",
            })

        # Interactive/recorded flows use Playwright — need more time
        request_timeout = 180 if config.auth_type in ("interactive", "recorded") else 30
        response = requests.post(scanner_url, json=payload, timeout=request_timeout)
        result = response.json()

        from django.utils import timezone

        if result.get("success"):
            config.auth_status = SiteAuthConfig.AuthStatus.SUCCESS
            config.last_error = ""
            config.session_cookies = result.get("cookies", {})
            config.last_test_at = timezone.now()
            config.session_valid_until = timezone.now() + timezone.timedelta(hours=2)
            config.save()
            return Response({
                "status": "success",
                "message": "Login successful",
                "method": result.get("method", "unknown"),
                "pages_accessible": result.get("pages_accessible", 0),
                "accessible_paths": result.get("accessible_paths", []),
                "login_redirects": result.get("login_redirects", []),
                "cookies_count": len(result.get("cookies", {})),
                "storage_tokens_count": result.get("storage_tokens_count", len(result.get("storage_tokens", {}))),
                "note": result.get("note", ""),
                "warning": result.get("warning", ""),
            })
        else:
            config.auth_status = SiteAuthConfig.AuthStatus.FAILED
            config.last_error = result.get("error", "Unknown login failure")
            config.last_test_at = timezone.now()
            config.save()

            # Create auth_failed alert
            ExternalDomainAlert.objects.create(
                site_domain=config.domain,
                alert_type=ExternalDomainAlert.AlertType.AUTH_FAILED,
                severity=ExternalDomainAlert.Severity.WARNING,
                message=(
                    f"Authentication test failed for {config.domain}: "
                    f"{result.get('error', 'Unknown error')}"
                ),
            )

            return Response({
                "status": "failed",
                "message": result.get("error", "Login failed"),
                "method": result.get("method", "unknown"),
                "playwright_available": result.get("playwright_available", True),
                "needs_selectors": result.get("needs_selectors", False),
            }, status=400)

    except requests.exceptions.ConnectionError:
        # Scanner unavailable — try inline test
        from django.utils import timezone
        config.auth_status = SiteAuthConfig.AuthStatus.FAILED
        config.last_error = "Scanner service unavailable"
        config.last_test_at = timezone.now()
        config.save()
        return Response({
            "status": "failed",
            "message": "Scanner service unavailable. Please try again.",
        }, status=503)
    except Exception as e:
        from django.utils import timezone
        config.auth_status = SiteAuthConfig.AuthStatus.FAILED
        config.last_error = str(e)
        config.last_test_at = timezone.now()
        config.save()
        return Response({
            "status": "failed",
            "message": f"Test failed: {str(e)}",
        }, status=500)


@api_view(["DELETE"])
def auth_config_delete(request):
    """
    DELETE auth config for a domain.
    """
    domain = request.data.get("domain", "").strip().lower()
    if not domain:
        return Response({"error": "domain is required"}, status=400)

    deleted, _ = SiteAuthConfig.objects.filter(domain=domain).delete()
    if deleted:
        return Response({"status": "deleted"})
    return Response({"status": "not_found"}, status=404)


@api_view(["POST"])
def auth_detect_fields(request):
    """
    Proxy: detect form fields on a login page.
    Calls the scanner service /auth/detect-fields endpoint.
    """
    login_url = request.data.get("login_url", "").strip()
    if not login_url:
        return Response({"error": "login_url is required"}, status=400)

    try:
        scanner_url = f"{settings.SCANNER_SERVICE_URL}/auth/detect-fields"
        response = requests.post(scanner_url, json={"login_url": login_url}, timeout=20)
        return Response(response.json(), status=response.status_code)
    except requests.exceptions.ConnectionError:
        return Response({"error": "Scanner service unavailable"}, status=503)
    except Exception as e:
        return Response({"error": str(e)}, status=500)


@api_view(["POST"])
def auth_debug_login(request):
    """
    Proxy: run a debug login attempt with step-by-step results.
    """
    domain = request.data.get("domain", "").strip().lower()
    if not domain:
        return Response({"error": "domain is required"}, status=400)

    try:
        config = SiteAuthConfig.objects.get(domain=domain)
    except SiteAuthConfig.DoesNotExist:
        return Response({"error": "No auth config found for this domain"}, status=404)

    if config.auth_type == "none":
        return Response({"error": "Auth type is None"}, status=400)

    try:
        scanner_url = f"{settings.SCANNER_SERVICE_URL}/auth/debug"
        payload = {
            "domain": config.domain,
            "auth_type": config.auth_type,
            "auth_strategy": config.auth_strategy or "auto",
        }
        if config.auth_type == "form":
            payload.update({
                "login_url": config.login_url,
                "username": config.username,
                "password": config.get_password(),
                "username_selector": config.username_selector or "",
                "password_selector": config.password_selector or "",
                "submit_selector": config.submit_selector or "",
            })
        elif config.auth_type == "cookie":
            payload["cookies"] = config.get_cookies_dict()
        elif config.auth_type == "interactive":
            payload.update({
                "home_url": config.home_url or "",
                "login_url": config.login_url or "",
                "username": config.username,
                "password": config.get_password(),
                "login_button_selector": config.login_button_selector or "",
                "username_selector": config.username_selector or "",
                "password_selector": config.password_selector or "",
                "submit_selector": config.submit_selector or "",
            })
        elif config.auth_type == "recorded":
            payload.update({
                "recorded_steps": config.recorded_steps or [],
                "username": config.username or "",
                "password": config.get_password() or "",
                "login_url": config.login_url or "",
            })

        response = requests.post(scanner_url, json=payload, timeout=180)
        return Response(response.json(), status=200)
    except requests.exceptions.ConnectionError:
        return Response({"error": "Scanner service unavailable"}, status=503)
    except Exception as e:
        return Response({"error": str(e)}, status=500)


@api_view(["GET"])
def auth_stability_score(request):
    """
    Calculate auth stability score for a domain based on alert history.
    Score 0-100 based on: success rate, re-login frequency, error count.
    """
    from .models import ExternalDomainAlert
    domain = request.query_params.get("domain", "").strip().lower()
    if not domain:
        return Response({"error": "domain is required"}, status=400)

    try:
        config = SiteAuthConfig.objects.get(domain=domain)
    except SiteAuthConfig.DoesNotExist:
        return Response({"score": None, "reason": "No auth config"})

    if config.auth_type == "none":
        return Response({"score": None, "reason": "Auth disabled"})

    # Count auth-related alerts in last 30 days
    from django.utils import timezone
    from datetime import timedelta
    since = timezone.now() - timedelta(days=30)

    auth_failed_count = ExternalDomainAlert.objects.filter(
        site_domain=domain,
        alert_type="auth_failed",
        created_at__gte=since,
    ).count()

    session_expired_count = ExternalDomainAlert.objects.filter(
        site_domain=domain,
        alert_type="session_expired",
        created_at__gte=since,
    ).count()

    total_scans = ExternalDomainAlert.objects.filter(
        site_domain=domain,
        created_at__gte=since,
    ).values("scan_id").distinct().count() or 1

    # Score calculation
    # Start at 100, deduct for failures
    score = 100
    score -= auth_failed_count * 15   # -15 per auth failure
    score -= session_expired_count * 5  # -5 per session expiry
    score = max(0, min(100, score))

    # Label
    if score >= 90:
        label = "Excellent"
    elif score >= 70:
        label = "Good"
    elif score >= 50:
        label = "Fair"
    elif score >= 30:
        label = "Poor"
    else:
        label = "Critical"

    return Response({
        "score": score,
        "label": label,
        "auth_status": config.auth_status,
        "auth_failed_count": auth_failed_count,
        "session_expired_count": session_expired_count,
        "total_scans_period": total_scans,
        "period_days": 30,
    })


# ──────────────────────────────────────────────────────────────────────────────
# Recorder — Start / Stop / Status (proxy to scanner service)
# ──────────────────────────────────────────────────────────────────────────────

@api_view(["POST"])
def auth_record_start(request):
    """Start a login recording session. Proxies to scanner."""
    domain = request.data.get("domain", "").strip().lower()
    if not domain:
        return Response({"error": "domain is required"}, status=400)

    start_url = request.data.get("start_url", "") or request.data.get("home_url", "")

    try:
        scanner_url = f"{settings.SCANNER_SERVICE_URL}/auth/record/start"
        response = requests.post(
            scanner_url,
            json={"domain": domain, "start_url": start_url},
            timeout=30,
        )
        return Response(response.json(), status=response.status_code)
    except requests.exceptions.ConnectionError:
        return Response({"error": "Scanner service unavailable"}, status=503)
    except Exception as e:
        return Response({"error": str(e)}, status=500)


@api_view(["POST"])
def auth_record_stop(request):
    """Stop a login recording session and return recorded steps. Proxies to scanner."""
    session_id = request.data.get("session_id", "")
    if not session_id:
        return Response({"error": "session_id is required"}, status=400)

    try:
        scanner_url = f"{settings.SCANNER_SERVICE_URL}/auth/record/stop"
        response = requests.post(
            scanner_url,
            json={"session_id": session_id},
            timeout=30,
        )
        return Response(response.json(), status=response.status_code)
    except requests.exceptions.ConnectionError:
        return Response({"error": "Scanner service unavailable"}, status=503)
    except Exception as e:
        return Response({"error": str(e)}, status=500)


@api_view(["GET"])
def auth_record_status(request):
    """Get the status of the current recording session. Proxies to scanner."""
    session_id = request.query_params.get("session_id", "")
    try:
        scanner_url = f"{settings.SCANNER_SERVICE_URL}/auth/record/status"
        params = {}
        if session_id:
            params["session_id"] = session_id
        response = requests.get(scanner_url, params=params, timeout=10)
        return Response(response.json(), status=response.status_code)
    except requests.exceptions.ConnectionError:
        return Response({"error": "Scanner service unavailable"}, status=503)
    except Exception as e:
        return Response({"error": str(e)}, status=500)


@api_view(["POST"])
def auth_record_reset(request):
    """Force-reset any active recording session. Proxies to scanner."""
    try:
        scanner_url = f"{settings.SCANNER_SERVICE_URL}/auth/record/reset"
        response = requests.post(scanner_url, json={}, timeout=30)
        return Response(response.json(), status=response.status_code)
    except requests.exceptions.ConnectionError:
        return Response({"error": "Scanner service unavailable"}, status=503)
    except Exception as e:
        return Response({"error": str(e)}, status=500)


# ──────────────────────────────────────────────────────────────────────────────
# Scanner Logs
# ──────────────────────────────────────────────────────────────────────────────

@api_view(["GET"])
def scanner_logs(request):
    """Proxy GET /logs to scanner service."""
    try:
        params = {
            "file": request.query_params.get("file", "scanner"),
            "lines": request.query_params.get("lines", "500"),
        }
        level = request.query_params.get("level")
        if level:
            params["level"] = level
        scanner_url = f"{settings.SCANNER_SERVICE_URL}/logs"
        response = requests.get(scanner_url, params=params, timeout=15)
        return Response(response.json(), status=response.status_code)
    except requests.exceptions.ConnectionError:
        return Response({"error": "Scanner service unavailable"}, status=503)
    except Exception as e:
        return Response({"error": str(e)}, status=500)


@api_view(["GET"])
def scanner_logs_files(request):
    """Proxy GET /logs/files to scanner service."""
    try:
        scanner_url = f"{settings.SCANNER_SERVICE_URL}/logs/files"
        response = requests.get(scanner_url, timeout=10)
        return Response(response.json(), status=response.status_code)
    except requests.exceptions.ConnectionError:
        return Response({"error": "Scanner service unavailable"}, status=503)
    except Exception as e:
        return Response({"error": str(e)}, status=500)


@api_view(["POST"])
def scanner_logs_clear(request):
    """Proxy POST /logs/clear to scanner service."""
    try:
        scanner_url = f"{settings.SCANNER_SERVICE_URL}/logs/clear"
        response = requests.post(scanner_url, json=request.data, timeout=10)
        return Response(response.json(), status=response.status_code)
    except requests.exceptions.ConnectionError:
        return Response({"error": "Scanner service unavailable"}, status=503)
    except Exception as e:
        return Response({"error": str(e)}, status=500)

