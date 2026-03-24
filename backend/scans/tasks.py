"""Celery tasks for the scans app."""

import logging

import requests
from celery import shared_task
from django.conf import settings

from .reputation import enqueue_domains, process_reputation_queue

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, queue="default")
def run_scan_task(self, scan_id: int):
    """Dispatch a scan to the scanner service."""
    from .models import DiscoveredURL, DiffURL, Scan, ScanDiff, SiteAuthConfig

    try:
        scan = Scan.objects.get(id=scan_id)
        scan.mark_running()

        # Build scanner payload
        payload = {
            "scan_id": scan.id,
            "domain": scan.domain,
            "max_depth": scan.max_depth,
            "max_pages": scan.max_pages,
        }

        # Include auth config if available
        try:
            auth_cfg = SiteAuthConfig.objects.get(domain=scan.domain, is_enabled=True)
            if auth_cfg.auth_type != "none":
                auth_data = {
                    "auth_type": auth_cfg.auth_type,
                    "auth_strategy": auth_cfg.auth_strategy or "auto",
                    "login_url": auth_cfg.login_url,
                    "username": auth_cfg.username,
                    "password": auth_cfg.get_password() or "",
                    "username_selector": auth_cfg.username_selector,
                    "password_selector": auth_cfg.password_selector,
                    "submit_selector": auth_cfg.submit_selector,
                }
                if auth_cfg.auth_type == "cookie" and auth_cfg.cookie_value:
                    # Parse cookie string into dict
                    cookies = {}
                    for part in auth_cfg.cookie_value.split(";"):
                        part = part.strip()
                        if "=" in part:
                            k, v = part.split("=", 1)
                            cookies[k.strip()] = v.strip()
                    auth_data["cookies"] = cookies

                # Interactive login fields
                if auth_cfg.auth_type == "interactive":
                    auth_data["home_url"] = auth_cfg.home_url or ""
                    auth_data["login_button_selector"] = auth_cfg.login_button_selector or ""

                # Recorded flow steps
                if auth_cfg.auth_type == "recorded":
                    auth_data["recorded_steps"] = auth_cfg.recorded_steps or []

                # Include saved session cookies for reuse (persisted sessions)
                if auth_cfg.session_cookies and auth_cfg.auth_status == "success":
                    from django.utils import timezone
                    # Only reuse if session hasn't expired
                    if auth_cfg.session_valid_until and auth_cfg.session_valid_until > timezone.now():
                        auth_data["saved_session_cookies"] = auth_cfg.session_cookies
                        logger.info(f"Scan #{scan.id}: reusing saved session cookies for {scan.domain}")

                payload["auth_config"] = auth_data
                logger.info(f"Scan #{scan.id}: auth enabled ({auth_cfg.auth_type})")
        except SiteAuthConfig.DoesNotExist:
            pass

        # Call scanner service
        scanner_url = f"{settings.SCANNER_SERVICE_URL}/scan"
        response = requests.post(
            scanner_url,
            json=payload,
            timeout=600,
        )

        if response.status_code == 200:
            result = response.json()
            urls_data = result.get("urls", [])

            # Save discovered URLs
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

            # ── Auth-related post-processing ──────────────────────────
            auth_success = result.get("auth_success", False)
            auth_error = result.get("auth_error")
            session_cookies = result.get("session_cookies", {})
            session_relogins = result.get("session_relogins", 0)
            private_count = result.get("private_urls", 0)

            if auth_success and session_cookies:
                # Save session cookies back to SiteAuthConfig for reuse
                try:
                    auth_cfg = SiteAuthConfig.objects.get(
                        domain=scan.domain, is_enabled=True
                    )
                    from django.utils import timezone
                    from datetime import timedelta
                    auth_cfg.session_cookies = session_cookies
                    auth_cfg.session_valid_until = (
                        timezone.now() + timedelta(hours=2)
                    )
                    auth_cfg.auth_status = SiteAuthConfig.AuthStatus.SUCCESS
                    auth_cfg.last_error = ""
                    auth_cfg.save(update_fields=[
                        "session_cookies", "session_valid_until",
                        "auth_status", "last_error", "updated_at",
                    ])
                    logger.info(
                        f"Scan #{scan.id}: saved session cookies for {scan.domain}"
                    )
                except SiteAuthConfig.DoesNotExist:
                    pass

            # Create auth alerts if login failed during scan
            from .models import ExternalDomainAlert

            if auth_error:
                ExternalDomainAlert.objects.create(
                    scan=scan,
                    site_domain=scan.domain,
                    alert_type=ExternalDomainAlert.AlertType.AUTH_FAILED,
                    severity=ExternalDomainAlert.Severity.WARNING,
                    message=(
                        f"Authentication failed during scan #{scan.id}: "
                        f"{auth_error}"
                    ),
                )
                # Update auth config status
                try:
                    auth_cfg = SiteAuthConfig.objects.get(
                        domain=scan.domain, is_enabled=True
                    )
                    auth_cfg.auth_status = SiteAuthConfig.AuthStatus.FAILED
                    auth_cfg.last_error = auth_error
                    auth_cfg.save(update_fields=[
                        "auth_status", "last_error", "updated_at",
                    ])
                except SiteAuthConfig.DoesNotExist:
                    pass

            if session_relogins > 0:
                ExternalDomainAlert.objects.create(
                    scan=scan,
                    site_domain=scan.domain,
                    alert_type=ExternalDomainAlert.AlertType.SESSION_EXPIRED,
                    severity=ExternalDomainAlert.Severity.INFO,
                    message=(
                        f"Session expired {session_relogins} time(s) during "
                        f"scan #{scan.id} and was automatically renewed."
                    ),
                )

            # Alert for new private pages discovered
            if private_count > 0:
                # Get previous scan's private URLs
                previous_scan = (
                    Scan.objects.filter(
                        domain=scan.domain,
                        status=Scan.Status.COMPLETED,
                        id__lt=scan.id,
                    )
                    .order_by("-id")
                    .first()
                )
                prev_private_urls = set()
                if previous_scan:
                    prev_private_urls = set(
                        previous_scan.urls.filter(is_private=True)
                        .values_list("url", flat=True)
                    )
                new_private_urls = set(
                    u["url"] for u in urls_data if u.get("is_private")
                ) - prev_private_urls
                if new_private_urls:
                    sample = list(new_private_urls)[:10]
                    ExternalDomainAlert.objects.create(
                        scan=scan,
                        site_domain=scan.domain,
                        alert_type=ExternalDomainAlert.AlertType.NEW_PRIVATE_PAGE,
                        severity=(
                            ExternalDomainAlert.Severity.INFO
                            if len(new_private_urls) <= 5
                            else ExternalDomainAlert.Severity.WARNING
                        ),
                        message=(
                            f"{len(new_private_urls)} new private page(s) "
                            f"discovered: {', '.join(sample)}"
                            + (
                                f" (+{len(new_private_urls) - 10} more)"
                                if len(new_private_urls) > 10
                                else ""
                            )
                        ),
                        domain_list=list(new_private_urls),
                    )

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
                previous_urls = set(
                    previous_scan.urls.values_list("url", flat=True)
                )

                new_urls = current_urls - previous_urls
                removed_urls = previous_urls - current_urls
                new_urls_count = len(new_urls)

                # Mark new URLs
                scan.urls.filter(url__in=new_urls).update(is_new=True)

                # Create diff record
                diff = ScanDiff.objects.create(
                    current_scan=scan,
                    previous_scan=previous_scan,
                    new_urls_count=len(new_urls),
                    removed_urls_count=len(removed_urls),
                )

                diff_url_objects = []
                for url in new_urls:
                    diff_url_objects.append(
                        DiffURL(diff=diff, url=url, change_type="added")
                    )
                for url in removed_urls:
                    diff_url_objects.append(
                        DiffURL(diff=diff, url=url, change_type="removed")
                    )
                DiffURL.objects.bulk_create(diff_url_objects)
            else:
                # First scan - all URLs are new
                scan.urls.all().update(is_new=True)
                new_urls_count = len(urls_data)

            scan.mark_completed(
                total_urls=len(urls_data), new_urls=new_urls_count
            )
            logger.info(f"Scan #{scan.id} completed: {len(urls_data)} URLs found")

            # Process external domain monitoring
            from .views import _process_external_domains
            _process_external_domains(scan)

            # Queue reputation checks for discovered external domains
            domains = list(
                scan.urls.filter(is_internal=False)
                .exclude(external_domain="")
                .values_list("external_domain", flat=True)
                .distinct()
            )
            if domains:
                enqueue_domains(domains, priority="high")
                process_reputation_queue_task.delay()

        else:
            scan.mark_failed(f"Scanner returned status {response.status_code}")
            logger.error(f"Scan #{scan.id} failed: {response.text}")

    except requests.exceptions.ConnectionError:
        # If scanner service is not available, run inline
        logger.warning("Scanner service unavailable, running inline scan")
        _run_inline_scan(scan_id)
    except Exception as exc:
        logger.exception(f"Scan #{scan_id} failed with exception")
        try:
            scan = Scan.objects.get(id=scan_id)
            scan.mark_failed(str(exc))
        except Scan.DoesNotExist:
            pass
        raise self.retry(exc=exc, countdown=60)


def _run_inline_scan(scan_id: int):
    """Fallback: run scan inline if scanner service is unavailable."""
    import asyncio
    import sys

    from .models import DiscoveredURL, Scan

    scan = Scan.objects.get(id=scan_id)
    scan.mark_running()

    try:
        # Import scanner engine
        sys.path.insert(0, str(settings.BASE_DIR.parent / "scanner"))
        from core.engine import ScannerEngine

        engine = ScannerEngine(
            domain=scan.domain,
            max_depth=scan.max_depth,
            max_pages=scan.max_pages,
        )

        results = asyncio.run(engine.run())

        url_objects = []
        for url_info in results:
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
                )
            )

        DiscoveredURL.objects.bulk_create(url_objects, ignore_conflicts=True)
        scan.urls.all().update(is_new=True)
        scan.mark_completed(total_urls=len(results), new_urls=len(results))

        # Process external domain monitoring
        from .views import _process_external_domains
        _process_external_domains(scan)

        domains = list(
            scan.urls.filter(is_internal=False)
            .exclude(external_domain="")
            .values_list("external_domain", flat=True)
            .distinct()
        )
        if domains:
            enqueue_domains(domains, priority="high")
            process_reputation_queue_task.delay()

    except Exception as e:
        scan.mark_failed(str(e))
        logger.exception(f"Inline scan #{scan_id} failed")


@shared_task(bind=True, max_retries=3, queue="default")
def process_reputation_queue_task(self, max_items: int = 100):
    """Process queued reputation checks in background."""
    try:
        result = process_reputation_queue(max_items=max_items)
        logger.info(
            "Processed reputation queue: %s items (%s failed)",
            result.get("processed", 0),
            result.get("failed", 0),
        )
        return result
    except Exception as exc:
        logger.exception("Reputation queue processing failed")
        raise self.retry(exc=exc, countdown=30)


# ─── Real-Time Monitoring Tasks ──────────────────────────────────────────────

@shared_task(bind=True, queue="default")
def run_monitoring_cycle(self):
    """
    Periodic task (called by Celery Beat every minute).
    Finds all SiteMonitorConfig entries that are enabled and due,
    then dispatches a light_scan_task for each.
    """
    from django.conf import settings as django_settings

    from .models import SiteMonitorConfig

    # Global kill-switch
    if not getattr(django_settings, "MONITORING_ENABLED", True):
        return {"dispatched": 0, "reason": "monitoring disabled globally"}

    EXCLUDED_DOMAINS = ["example.com", "localhost", "127.0.0.1"]
    configs = SiteMonitorConfig.objects.filter(
        is_enabled=True
    ).exclude(domain__in=EXCLUDED_DOMAINS)
    dispatched = 0

    for config in configs:
        if config.is_due:
            light_scan_task.delay(config.id)
            dispatched += 1
            logger.info(f"Monitoring cycle: dispatched light scan for {config.domain}")

    if dispatched:
        logger.info(f"Monitoring cycle: dispatched {dispatched} light scan(s)")
    else:
        logger.debug(f"Monitoring cycle: no sites due ({configs.count()} active configs)")
    return {"dispatched": dispatched}


@shared_task(bind=True, max_retries=2, queue="default")
def light_scan_task(self, config_id: int):
    """
    Execute a light scan for a single monitored site.

    Steps:
      1. Fetch key pages and compute aggregated content hash
      2. Extract external domains from fetched pages
      3. Diff against previous scan's domain set
      4. If new domains found → enqueue for reputation check
      5. Save LightScanResult and update SiteMonitorConfig
    """
    import asyncio
    from datetime import timedelta

    from django.utils import timezone

    from .light_scanner import diff_domains, run_light_scan
    from .models import (
        ExternalDomainAlert,
        ExternalDomainEntry,
        LightScanResult,
        SiteAuthConfig,
        SiteMonitorConfig,
    )

    try:
        config = SiteMonitorConfig.objects.get(id=config_id)
    except SiteMonitorConfig.DoesNotExist:
        logger.warning(f"SiteMonitorConfig #{config_id} not found, skipping")
        return

    if not config.is_enabled:
        logger.info(f"Monitoring disabled for {config.domain}, skipping")
        return

    logger.info(f"Starting light scan for {config.domain}")

    try:
        # 1. Get auth cookies if available for this domain
        auth_cookies = None
        try:
            auth_cfg = SiteAuthConfig.objects.get(
                domain=config.domain, is_enabled=True,
            )
            if auth_cfg.auth_status == "success" and auth_cfg.session_cookies:
                # Check if session is still within validity window
                if auth_cfg.session_valid_until and auth_cfg.session_valid_until > timezone.now():
                    auth_cookies = auth_cfg.session_cookies
                    logger.info(
                        f"Light scan {config.domain}: using auth cookies "
                        f"(valid until {auth_cfg.session_valid_until})"
                    )
                else:
                    logger.info(
                        f"Light scan {config.domain}: auth cookies expired, "
                        f"scanning without auth"
                    )
                    # Create session expired alert
                    ExternalDomainAlert.objects.create(
                        site_domain=config.domain,
                        alert_type=ExternalDomainAlert.AlertType.SESSION_EXPIRED,
                        severity=ExternalDomainAlert.Severity.WARNING,
                        message=(
                            f"Session cookies expired for {config.domain}. "
                            f"Real-time monitoring running without authentication. "
                            f"Please re-test auth or run a new scan to refresh session."
                        ),
                    )
        except SiteAuthConfig.DoesNotExist:
            pass

        # 2. Run the light scan
        key_pages = config.key_pages or list(SiteMonitorConfig.DEFAULT_KEY_PAGES)
        scan_output = asyncio.run(
            run_light_scan(config.domain, key_pages, auth_cookies=auth_cookies)
        )

        if scan_output.error:
            config.consecutive_errors += 1
            config.last_error = scan_output.error
            config.last_scan_at = timezone.now()
            config.next_scan_at = timezone.now() + timedelta(minutes=config.interval_minutes)
            config.save(update_fields=[
                "consecutive_errors", "last_error", "last_scan_at", "next_scan_at", "updated_at",
            ])
            logger.warning(f"Light scan error for {config.domain}: {scan_output.error}")
            return {"status": "error", "domain": config.domain, "error": scan_output.error}

        # 2. Get previous scan's domain snapshot
        previous_result = (
            LightScanResult.objects.filter(site_config=config)
            .order_by("-created_at")
            .first()
        )
        previous_domains = set(previous_result.external_domains_snapshot) if previous_result else set()

        # 3. Diff domains
        current_domains = scan_output.external_domains
        new_domains, removed_domains = diff_domains(current_domains, previous_domains)

        # 4. Detect content changes
        has_changes = (
            config.last_content_hash != ""
            and scan_output.content_hash != config.last_content_hash
        )

        # 5. Save LightScanResult
        result = LightScanResult.objects.create(
            site_config=config,
            content_hash=scan_output.content_hash,
            previous_hash=config.last_content_hash,
            has_changes=has_changes,
            pages_checked=scan_output.pages_checked,
            pages_data=scan_output.pages_data,
            external_domains_snapshot=sorted(current_domains),
            new_domains=new_domains,
            removed_domains=removed_domains,
            new_domains_count=len(new_domains),
            removed_domains_count=len(removed_domains),
            scan_duration=scan_output.duration,
        )

        # 6. If new domains found → update ExternalDomainEntry + enqueue reputation
        if new_domains:
            logger.info(
                f"Light scan {config.domain}: {len(new_domains)} new domain(s): "
                f"{', '.join(new_domains[:5])}"
            )

            # Upsert ExternalDomainEntry records
            for domain in new_domains:
                from .models import check_suspicious, normalize_domain
                clean = normalize_domain(domain)
                if not clean:
                    continue

                is_susp, susp_reasons = check_suspicious(clean)
                entry, created = ExternalDomainEntry.objects.get_or_create(
                    site_domain=config.domain,
                    domain=clean,
                    defaults={
                        "status": "new",
                        "is_suspicious": is_susp,
                        "suspicious_reasons": susp_reasons,
                        "times_seen": 1,
                        "found_on_pages": key_pages[:3],
                    },
                )
                if not created:
                    entry.times_seen += 1
                    entry.save(update_fields=["times_seen", "last_seen"])

            # Create alert for new domains
            ExternalDomainAlert.objects.create(
                site_domain=config.domain,
                alert_type="new_domain",
                severity="warning" if len(new_domains) <= 3 else "critical",
                message=(
                    f"{len(new_domains)} new external domain(s) detected (auto-monitor): "
                    f"{', '.join(new_domains[:10])}"
                    + (f" (+{len(new_domains) - 10} more)" if len(new_domains) > 10 else "")
                ),
                domain_list=new_domains,
            )

            # Enqueue only the NEW domains for reputation check
            enqueue_domains(new_domains, priority="normal")
            result.reputation_enqueued = True
            result.save(update_fields=["reputation_enqueued"])

            # Trigger reputation processing
            process_reputation_queue_task.apply_async(countdown=5)

        # 7. Alert on removed domains too
        if removed_domains:
            ExternalDomainAlert.objects.create(
                site_domain=config.domain,
                alert_type="domain_removed",
                severity="info",
                message=(
                    f"{len(removed_domains)} external domain(s) removed: "
                    f"{', '.join(removed_domains[:10])}"
                    + (f" (+{len(removed_domains) - 10} more)" if len(removed_domains) > 10 else "")
                ),
                domain_list=removed_domains,
            )

        # 8. Alert on content change
        if has_changes:
            config.changes_detected_count += 1
            ExternalDomainAlert.objects.create(
                site_domain=config.domain,
                alert_type="content_change",
                severity="info",
                message=(
                    f"Content change detected on monitored pages. "
                    f"Hash changed: {config.last_content_hash[:12]}… → "
                    f"{scan_output.content_hash[:12]}…  "
                    f"({scan_output.pages_checked} pages checked)"
                ),
                domain_list=[],
            )

        # 9. Update config
        now = timezone.now()
        config.last_content_hash = scan_output.content_hash
        config.last_scan_at = now
        config.next_scan_at = now + timedelta(minutes=config.interval_minutes)
        config.total_light_scans += 1
        config.consecutive_errors = 0
        config.last_error = ""
        config.save(update_fields=[
            "last_content_hash", "last_scan_at", "next_scan_at",
            "total_light_scans", "changes_detected_count",
            "consecutive_errors", "last_error", "updated_at",
        ])

        logger.info(
            f"Light scan complete for {config.domain}: "
            f"changes={has_changes}, +{len(new_domains)}/-{len(removed_domains)} domains, "
            f"next run at {config.next_scan_at}"
        )

        return {
            "status": "ok",
            "domain": config.domain,
            "has_changes": has_changes,
            "new_domains": len(new_domains),
            "removed_domains": len(removed_domains),
            "duration": scan_output.duration,
        }

    except Exception as exc:
        logger.exception(f"Light scan task failed for config #{config_id}")
        try:
            config.consecutive_errors += 1
            config.last_error = str(exc)
            config.last_scan_at = timezone.now()
            config.next_scan_at = timezone.now() + timedelta(minutes=config.interval_minutes)
            config.save(update_fields=[
                "consecutive_errors", "last_error", "last_scan_at", "next_scan_at", "updated_at",
            ])
        except Exception:
            pass
        raise self.retry(exc=exc, countdown=120)
