"""Source-side mitigation planning within the canonical Mojtaba.bot.ai.

Read-only, offline, tenant-isolated analysis of pre-collected traffic counters.
Not an active firewall, scanner, exploit tool, counterattack or attribution engine.
"""
from __future__ import annotations

import hashlib
import hmac
import ipaddress
import json
from datetime import datetime, timedelta, timezone

from .cyber_security import (
    BOT_ID, MODULE_ID, CyberModuleError, _host, _timestamp, verify_authorization,
)

SCHEMA = "mojtaba.bot.ai.cyber.origin-defense.v1"
COLLECTORS = frozenset(("verified_edge_export", "origin_socket_log", "unverified_forwarded_header"))
RISK_ORDER = {"informational": 0, "review": 1, "urgent_review": 2}


def _count(value: object, *, ceiling: int = 10_000_000) -> int:
    if type(value) is not int or not 0 <= value <= ceiling:
        raise CyberModuleError("ORIGIN_METRIC_INVALID")
    return value


def _identity(source_ip: str, *, key: bytes, tenant_id: str,
              engagement_id: str) -> tuple[str, bool]:
    if not isinstance(source_ip, str):
        raise CyberModuleError("SOURCE_IP_INVALID")
    try:
        ip = ipaddress.ip_address(source_ip)
    except ValueError as exc:
        raise CyberModuleError("SOURCE_IP_INVALID") from exc
    if str(ip) != source_ip:
        raise CyberModuleError("SOURCE_IP_NOT_CANONICAL")
    # Include BOTH tenant and engagement to prevent cross-customer linkability.
    context = json.dumps([tenant_id, engagement_id, str(ip)],
                         ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    opaque = hmac.new(key, context, hashlib.sha256).hexdigest()[:24]
    return opaque, ip.is_global


def plan_origin_defense(*, engagement: dict, traffic: dict,
                        verify_key: bytes, now: datetime | None = None) -> dict:
    """Suggest mitigations for REVIEW, never execute blocks or any network action.

    Source addresses are indicators, NOT proof of attacker identity. Any "trusted"
    collector label is only a claim made by the supplied export; the canonical
    control plane must attest collector provenance before using the output.
    """
    scope = verify_authorization(engagement, verify_key, now=now)
    reference = now or datetime.now(timezone.utc)
    if reference.tzinfo is None:
        raise CyberModuleError("TIMEZONE_REQUIRED")
    reference = reference.astimezone(timezone.utc)

    if not isinstance(traffic, dict) or traffic.get("schema") != SCHEMA:
        raise CyberModuleError("ORIGIN_EVIDENCE_INVALID")
    if (traffic.get("tenant_id") != scope["tenant_id"] or
            traffic.get("engagement_id") != scope["engagement_id"]):
        raise CyberModuleError("CROSS_TENANT_EVIDENCE_FORBIDDEN")
    records = traffic.get("observations")
    if not isinstance(records, list) or not 0 <= len(records) <= 500:
        raise CyberModuleError("ORIGIN_OBSERVATIONS_INVALID")

    decisions = []
    for item in records:
        if not isinstance(item, dict):
            raise CyberModuleError("ORIGIN_OBSERVATION_INVALID")
        hostname = _host(item.get("asset_hostname"))
        if hostname not in scope["allowed_assets"]:
            raise CyberModuleError("ASSET_OUT_OF_SCOPE")
        collector = item.get("collector")
        if not isinstance(collector, str) or collector not in COLLECTORS:
            raise CyberModuleError("COLLECTOR_INVALID")
        observed_at = _timestamp(item.get("observed_at"))
        if not (reference - timedelta(hours=1) <= observed_at <= reference and
                _timestamp(scope["issued_at"]) <= observed_at):
            raise CyberModuleError("OBSERVATION_OUTSIDE_TIME_WINDOW")

        opaque_source, public = _identity(
            item.get("source_ip"), key=verify_key, tenant_id=scope["tenant_id"],
            engagement_id=scope["engagement_id"]
        )
        total = _count(item.get("requests_5m"))
        errors_4xx = _count(item.get("errors_4xx_5m"))
        errors_5xx = _count(item.get("errors_5xx_5m"))
        paths = _count(item.get("distinct_paths_5m"))
        if errors_4xx + errors_5xx > total or paths > total:
            raise CyberModuleError("ORIGIN_COUNTERS_INCONSISTENT")

        # All active changes require independent approval and external validation.
        # IP indications from origin sockets may represent a reverse proxy.
        eligible_edge_signal = collector == "verified_edge_export" and public
        high_pressure = total >= 600 and errors_4xx >= 300 and 2 * errors_4xx >= total
        severe_pressure = total >= 3000 and errors_5xx >= 100
        action = "observe_and_validate_origin_access"
        risk = "informational"
        if eligible_edge_signal and high_pressure:
            action = "review_edge_challenge_or_rate_limit"
            risk = "review"
        if eligible_edge_signal and severe_pressure:
            action = "request_upstream_mitigation_review"
            risk = "urgent_review"
        if not eligible_edge_signal:
            action = "validate_proxy_chain_and_source_evidence"
            risk = "review" if total >= 600 else "informational"

        decisions.append({
            "asset_hostname": hostname, "source_tag": opaque_source,
            "collector": collector, "public_ip_indicator": public,
            "risk": risk, "proposed_action": action,
            "observed_requests_5m": total,
            "approval_required": True, "executed": False,
            "identity_attribution": "not_established",
            "collector_provenance": "must_be_verified_outside_this_module",
        })

    risk = max((r["risk"] for r in decisions), key=RISK_ORDER.get,
               default="informational")
    return {
        "bot_id": BOT_ID, "module_id": MODULE_ID,
        "submodule_id": "origin_defense",
        "schema": SCHEMA, "tenant_id": scope["tenant_id"],
        "engagement_id": scope["engagement_id"],
        "mode": "offline_recommendations_only",
        "risk": risk, "recommendations": decisions,
        "defense_layers": [
            "edge_waf_rate_limits_and_challenges",
            "origin_ip_exposure_review",
            "trusted_reverse_proxy_chain_review",
            "origin_tls_authentication_or_tunnel_review",
            "hosting_provider_or_isp_ddos_mitigation_review",
        ],
        "no_hack_back": True, "network_actions_executed": 0,
        "approval_required_for_any_change": True,
        "note": "No source actor attribution, no traffic filtering, no live host access.",
    }
