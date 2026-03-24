"""Domain reputation service (Safe Browsing + VirusTotal)."""

from __future__ import annotations

import json
import logging
import time
from datetime import timedelta
from typing import Any

import redis
import requests
from django.conf import settings
from django.utils import timezone

from .models import DomainReputation, ExternalDomainAlert, ExternalDomainEntry, normalize_domain

logger = logging.getLogger(__name__)

REPUTATION_QUEUE = "reputation_queue"


class RiskLevel:
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    UNKNOWN = "unknown"


class Priority:
    HIGH = "high"
    LOW = "low"


def _redis_client() -> redis.Redis:
    redis_url = getattr(settings, "REPUTATION_REDIS_URL", None) or settings.CELERY_BROKER_URL
    return redis.Redis.from_url(redis_url, decode_responses=True)


def _request_with_retry(
    method: str,
    url: str,
    *,
    max_retries: int = 3,
    rate_delay: float = 0.25,
    **kwargs,
) -> requests.Response:
    last_error: Exception | None = None
    for attempt in range(max_retries):
        try:
            response = requests.request(method=method, url=url, timeout=20, **kwargs)
            if response.status_code >= 500:
                raise requests.HTTPError(
                    f"HTTP {response.status_code}: {response.text[:200]}", response=response
                )
            time.sleep(rate_delay)
            return response
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            if attempt < max_retries - 1:
                time.sleep(2**attempt)
                continue
            raise

    if last_error:
        raise last_error
    raise RuntimeError("Request failed")


def _safe_browsing_batch(domains: list[str]) -> dict[str, dict[str, Any]]:
    if not domains:
        return {}

    key = getattr(settings, "GOOGLE_SAFE_BROWSING_API_KEY", "")
    if not key:
        return {
            d: {
                "matched": False,
                "threats": [],
                "risk": RiskLevel.UNKNOWN,
                "error": "Google Safe Browsing API key not configured",
            }
            for d in domains
        }

    endpoint = "https://safebrowsing.googleapis.com/v4/threatMatches:find"
    payload = {
        "client": {"clientId": "wscaner", "clientVersion": "1.0.0"},
        "threatInfo": {
            "threatTypes": ["MALWARE", "SOCIAL_ENGINEERING", "UNWANTED_SOFTWARE"],
            "platformTypes": ["ANY_PLATFORM"],
            "threatEntryTypes": ["URL"],
            "threatEntries": [{"url": f"http://{d}"} for d in domains],
        },
    }

    try:
        response = _request_with_retry(
            "POST",
            endpoint,
            params={"key": key},
            json=payload,
        )
        if response.status_code >= 400:
            msg = f"Safe Browsing error {response.status_code}"
            return {
                d: {"matched": False, "threats": [], "risk": RiskLevel.UNKNOWN, "error": msg}
                for d in domains
            }

        data = response.json() if response.content else {}
        matches = data.get("matches", []) if isinstance(data, dict) else []

        threats_by_domain: dict[str, list[str]] = {d: [] for d in domains}
        for match in matches:
            threat_url = (
                match.get("threat", {}).get("url", "")
                if isinstance(match, dict)
                else ""
            )
            threat_type = match.get("threatType", "UNKNOWN") if isinstance(match, dict) else "UNKNOWN"
            for domain in domains:
                if domain in threat_url:
                    threats_by_domain[domain].append(threat_type)

        result: dict[str, dict[str, Any]] = {}
        for domain in domains:
            domain_threats = sorted(set(threats_by_domain.get(domain, [])))
            matched = len(domain_threats) > 0
            result[domain] = {
                "matched": matched,
                "threats": domain_threats,
                "risk": RiskLevel.HIGH if matched else RiskLevel.LOW,
            }
        return result
    except Exception as exc:  # noqa: BLE001
        logger.warning("Safe Browsing check failed: %s", exc)
        return {
            d: {
                "matched": False,
                "threats": [],
                "risk": RiskLevel.UNKNOWN,
                "error": str(exc),
            }
            for d in domains
        }


def _virustotal_check(domain: str) -> dict[str, Any]:
    key = getattr(settings, "VIRUSTOTAL_API_KEY", "")
    if not key:
        return {
            "risk": RiskLevel.UNKNOWN,
            "malicious": 0,
            "suspicious": 0,
            "harmless": 0,
            "undetected": 0,
            "stats": {"error": "VirusTotal API key not configured"},
        }

    endpoint = f"https://www.virustotal.com/api/v3/domains/{domain}"
    headers = {"x-apikey": key}

    try:
        response = _request_with_retry("GET", endpoint, headers=headers)
        if response.status_code >= 400:
            return {
                "risk": RiskLevel.UNKNOWN,
                "malicious": 0,
                "suspicious": 0,
                "harmless": 0,
                "undetected": 0,
                "stats": {"error": f"VirusTotal error {response.status_code}"},
            }

        data = response.json() if response.content else {}
        attributes = data.get("data", {}).get("attributes", {})
        stats = attributes.get("last_analysis_stats", {})

        malicious = int(stats.get("malicious", 0) or 0)
        suspicious = int(stats.get("suspicious", 0) or 0)
        harmless = int(stats.get("harmless", 0) or 0)
        undetected = int(stats.get("undetected", 0) or 0)

        if malicious > 5:
            risk = RiskLevel.HIGH
        elif malicious > 0:
            risk = RiskLevel.MEDIUM
        else:
            risk = RiskLevel.LOW

        return {
            "risk": risk,
            "malicious": malicious,
            "suspicious": suspicious,
            "harmless": harmless,
            "undetected": undetected,
            "stats": {
                **stats,
                "categories": attributes.get("categories", {}),
                "last_analysis_date": attributes.get("last_analysis_date"),
                "reputation": attributes.get("reputation"),
            },
        }
    except Exception as exc:  # noqa: BLE001
        logger.warning("VirusTotal check failed for %s: %s", domain, exc)
        return {
            "risk": RiskLevel.UNKNOWN,
            "malicious": 0,
            "suspicious": 0,
            "harmless": 0,
            "undetected": 0,
            "stats": {"error": str(exc)},
        }


def _aggregate_risk(safe_browsing_risk: str, virustotal_risk: str) -> str:
    if safe_browsing_risk == RiskLevel.HIGH:
        return RiskLevel.HIGH
    if virustotal_risk == RiskLevel.HIGH:
        return RiskLevel.HIGH
    if virustotal_risk == RiskLevel.MEDIUM:
        return RiskLevel.MEDIUM
    if safe_browsing_risk == RiskLevel.UNKNOWN and virustotal_risk == RiskLevel.UNKNOWN:
        return RiskLevel.UNKNOWN
    return RiskLevel.LOW


def enqueue_domain(domain: str, priority: str = Priority.HIGH) -> bool:
    normalized = normalize_domain(domain)
    if not normalized:
        return False

    payload = json.dumps({"domain": normalized, "priority": priority})
    client = _redis_client()

    if priority == Priority.HIGH:
        client.lpush(REPUTATION_QUEUE, payload)
    else:
        client.rpush(REPUTATION_QUEUE, payload)

    return True


def enqueue_domains(domains: list[str], *, priority: str = Priority.HIGH) -> int:
    queued = 0
    for domain in domains:
        if enqueue_domain(domain, priority=priority):
            queued += 1
    return queued


def _is_cache_valid(reputation: DomainReputation) -> bool:
    if not reputation.checked_at:
        return False
    ttl_hours = int(getattr(settings, "DOMAIN_REPUTATION_CACHE_HOURS", 24))
    return (
        reputation.check_status == DomainReputation.CheckStatus.COMPLETED
        and timezone.now() - reputation.checked_at < timedelta(hours=ttl_hours)
    )


def _save_reputation(
    reputation: DomainReputation,
    safe_result: dict[str, Any],
    vt_result: dict[str, Any],
) -> DomainReputation:
    final_risk = _aggregate_risk(
        safe_result.get("risk", RiskLevel.UNKNOWN),
        vt_result.get("risk", RiskLevel.UNKNOWN),
    )

    reputation.risk_level = final_risk
    reputation.safe_browsing_result = safe_result
    reputation.safe_browsing_risk = safe_result.get("risk", RiskLevel.UNKNOWN)
    reputation.virustotal_stats = vt_result.get("stats", {})
    reputation.virustotal_risk = vt_result.get("risk", RiskLevel.UNKNOWN)
    reputation.virustotal_malicious = int(vt_result.get("malicious", 0) or 0)
    reputation.virustotal_suspicious = int(vt_result.get("suspicious", 0) or 0)
    reputation.virustotal_harmless = int(vt_result.get("harmless", 0) or 0)
    reputation.virustotal_undetected = int(vt_result.get("undetected", 0) or 0)
    reputation.checked_at = timezone.now()
    reputation.check_count += 1
    reputation.check_status = DomainReputation.CheckStatus.COMPLETED
    reputation.error_message = ""
    reputation.save()

    _create_high_risk_alerts(reputation)
    return reputation


def analyze_domain(domain: str, *, force: bool = False) -> DomainReputation:
    normalized = normalize_domain(domain)

    reputation, _ = DomainReputation.objects.get_or_create(domain=normalized)
    if not force and _is_cache_valid(reputation):
        return reputation

    reputation.check_status = DomainReputation.CheckStatus.CHECKING
    reputation.error_message = ""
    reputation.save(update_fields=["check_status", "error_message", "updated_at"])

    try:
        safe_result = _safe_browsing_batch([normalized]).get(normalized, {})
        vt_result = _virustotal_check(normalized)

        return _save_reputation(reputation, safe_result, vt_result)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Reputation check failed for %s", normalized)
        reputation.check_status = DomainReputation.CheckStatus.FAILED
        reputation.error_message = str(exc)
        reputation.checked_at = timezone.now()
        reputation.check_count += 1
        reputation.save(update_fields=[
            "check_status",
            "error_message",
            "checked_at",
            "check_count",
            "updated_at",
        ])
        return reputation


def _create_high_risk_alerts(reputation: DomainReputation) -> None:
    if reputation.risk_level != DomainReputation.RiskLevel.HIGH:
        return

    source: list[str] = []
    if reputation.safe_browsing_risk == DomainReputation.RiskLevel.HIGH:
        source.append("SafeBrowsing")
    if reputation.virustotal_risk in [DomainReputation.RiskLevel.HIGH, DomainReputation.RiskLevel.MEDIUM]:
        source.append("VirusTotal")
    source_text = " / ".join(source) if source else "Reputation Engine"

    entries = ExternalDomainEntry.objects.filter(domain=reputation.domain).select_related("last_seen_scan")
    for entry in entries:
        scan = entry.last_seen_scan
        if not scan:
            continue

        exists = ExternalDomainAlert.objects.filter(
            scan=scan,
            site_domain=entry.site_domain,
            external_domain=entry.domain,
            alert_type=ExternalDomainAlert.AlertType.SUSPICIOUS_DOMAIN,
            message__icontains="Dangerous domain detected",
        ).exists()
        if exists:
            continue

        ExternalDomainAlert.objects.create(
            scan=scan,
            site_domain=entry.site_domain,
            external_domain=entry.domain,
            alert_type=ExternalDomainAlert.AlertType.SUSPICIOUS_DOMAIN,
            severity=ExternalDomainAlert.Severity.CRITICAL,
            message=(
                "🚨 Dangerous domain detected\n\n"
                f"Domain: {entry.domain}\n"
                f"Risk: HIGH\n"
                f"Source: {source_text}"
            ),
        )


def process_reputation_queue(max_items: int = 100) -> dict[str, int]:
    client = _redis_client()
    processed = 0
    failed = 0

    domains: list[tuple[str, bool]] = []
    while processed < max_items:
        result = client.brpop(REPUTATION_QUEUE, timeout=1)
        item = result[1] if result else None
        if not item:
            break
        processed += 1
        try:
            payload = json.loads(item)
            domain = normalize_domain(str(payload.get("domain", "")))
            force = bool(payload.get("force", False))
            if domain:
                domains.append((domain, force))
        except Exception:  # noqa: BLE001
            failed += 1

    if not domains:
        return {"processed": processed, "failed": failed}

    force_map: dict[str, bool] = {}
    for domain, force in domains:
        force_map[domain] = force_map.get(domain, False) or force

    unique_domains = list(force_map.keys())
    existing = {
        rep.domain: rep
        for rep in DomainReputation.objects.filter(domain__in=unique_domains)
    }

    to_check: list[str] = []
    for domain in unique_domains:
        rep = existing.get(domain)
        if rep is None:
            rep = DomainReputation.objects.create(domain=domain)
            existing[domain] = rep

        force = force_map.get(domain, False)
        if force or not _is_cache_valid(rep):
            rep.check_status = DomainReputation.CheckStatus.CHECKING
            rep.error_message = ""
            rep.save(update_fields=["check_status", "error_message", "updated_at"])
            to_check.append(domain)

    safe_results = _safe_browsing_batch(to_check)

    for domain in to_check:
        rep = existing[domain]
        try:
            safe_result = safe_results.get(domain, {"risk": RiskLevel.UNKNOWN, "matched": False, "threats": []})
            vt_result = _virustotal_check(domain)
            _save_reputation(rep, safe_result, vt_result)
        except Exception as exc:  # noqa: BLE001
            rep.check_status = DomainReputation.CheckStatus.FAILED
            rep.error_message = str(exc)
            rep.checked_at = timezone.now()
            rep.check_count += 1
            rep.save(update_fields=[
                "check_status",
                "error_message",
                "checked_at",
                "check_count",
                "updated_at",
            ])
            failed += 1

    return {"processed": processed, "failed": failed}
