"""Incident containment and recovery planning for the sole Mojtaba.bot.ai bot.

Analyze pre-collected incident indicators and backup attestations only.
Never connect to a host, modify files, execute commands, exfiltrate data,
erase evidence, or authorize counterattacks. A plan is not an executed action.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import re
from datetime import datetime, timedelta, timezone

from .cyber_security import (
    BOT_ID, MODULE_ID, CyberModuleError, _host, _timestamp,
    verify_authorization,
)

SCHEMA = "mojtaba.bot.ai.cyber.incident-response.v1"
ID_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,99}\Z")
DIGEST_RE = re.compile(r"[0-9a-f]{64}\Z")
INDICATORS = frozenset((
    "suspected_data_exposure", "suspected_destructive_activity",
    "suspected_ransomware", "account_compromise",
    "service_disruption", "integrity_anomaly", "other_anomaly",
))
CONFIDENCE = frozenset(("low", "medium", "high"))
INTEGRITY = frozenset(("verified_claim", "mismatch", "unknown"))
LEVEL = {"informational": 0, "review": 1, "urgent": 2, "critical": 3}
PLAYBOOKS = {
    "suspected_data_exposure": (
        "preserve_evidence_and_access_logs",
        "request_privacy_and_legal_notification_assessment",
        "review_credential_rotation_and_egress_controls",
    ),
    "suspected_destructive_activity": (
        "preserve_evidence_and_access_logs",
        "review_isolation_of_affected_authorized_assets",
        "verify_immutable_backup_restore_plan",
    ),
    "suspected_ransomware": (
        "preserve_evidence_and_access_logs",
        "review_isolation_of_affected_authorized_assets",
        "verify_immutable_backup_restore_plan",
    ),
    "account_compromise": (
        "preserve_evidence_and_access_logs",
        "review_session_revocation_and_credential_rotation",
        "review_authentication_and_authorization_controls",
    ),
    "service_disruption": (
        "preserve_evidence_and_access_logs",
        "review_upstream_mitigation_and_service_continuity",
    ),
    "integrity_anomaly": (
        "preserve_evidence_and_access_logs",
        "verify_immutable_backup_restore_plan",
        "review_change_and_release_history",
    ),
    "other_anomaly": ("preserve_evidence_and_access_logs", "request_analyst_triage"),
}


def _identifier(value: object, code: str) -> str:
    if not isinstance(value, str) or not ID_RE.fullmatch(value):
        raise CyberModuleError(code)
    return value


def _utc_now(now: datetime | None) -> datetime:
    result = now if now is not None else datetime.now(timezone.utc)
    if not isinstance(result, datetime) or result.tzinfo is None:
        raise CyberModuleError("TIMEZONE_REQUIRED")
    return result.astimezone(timezone.utc)


def _event_level(event_type: str, confidence: str) -> str:
    if confidence == "high" and event_type in {
        "suspected_data_exposure", "suspected_destructive_activity", "suspected_ransomware",
    }:
        return "critical"
    if confidence == "high":
        return "urgent"
    if confidence == "medium":
        return "review"
    return "informational"


def plan_incident_response(*, engagement: dict, incident: dict,
                           verify_key: bytes, now: datetime | None = None) -> dict:
    """Return a non-executing, evidence-minimized recovery/containment plan."""
    clock = _utc_now(now)
    scope = verify_authorization(engagement, verify_key, now=clock)
    if not isinstance(incident, dict) or incident.get("schema") != SCHEMA:
        raise CyberModuleError("INCIDENT_EVIDENCE_INVALID")
    if incident.get("tenant_id") != scope["tenant_id"] or (
        incident.get("engagement_id") != scope["engagement_id"]
    ):
        raise CyberModuleError("CROSS_TENANT_EVIDENCE_FORBIDDEN")
    incident_id = _identifier(incident.get("incident_id"), "INCIDENT_ID_INVALID")
    asset = _host(incident.get("asset_hostname"))
    if asset not in scope["allowed_assets"]:
        raise CyberModuleError("ASSET_OUT_OF_SCOPE")

    incoming = incident.get("indicators")
    if not isinstance(incoming, list) or len(incoming) > 200:
        raise CyberModuleError("INDICATORS_INVALID")
    evidence = []
    actions = set()
    seen = set()
    for row in incoming:
        if not isinstance(row, dict):
            raise CyberModuleError("INDICATOR_INVALID")
        identifier = _identifier(row.get("id"), "INDICATOR_ID_INVALID")
        if identifier in seen:
            raise CyberModuleError("INDICATOR_ID_DUPLICATED")
        seen.add(identifier)
        kind, confidence = row.get("kind"), row.get("confidence")
        if (not isinstance(kind, str) or not isinstance(confidence, str) or
                kind not in INDICATORS or confidence not in CONFIDENCE):
            raise CyberModuleError("INDICATOR_CLASS_INVALID")
        observed = _timestamp(row.get("observed_at"))
        if not (max(clock - timedelta(days=7), _timestamp(scope["issued_at"])) <= observed <= clock):
            raise CyberModuleError("INDICATOR_OUTSIDE_WINDOW")
        risk = _event_level(kind, confidence)
        evidence.append({"id": identifier, "kind": kind, "confidence": confidence,
                         "risk": risk, "observed_at": observed.isoformat()})
        actions.update(PLAYBOOKS[kind])

    backups = incident.get("backups")
    if not isinstance(backups, list) or len(backups) > 30:
        raise CyberModuleError("BACKUPS_INVALID")
    recovery = []
    backup_ids = set()
    for row in backups:
        if not isinstance(row, dict):
            raise CyberModuleError("BACKUP_INVALID")
        backup_id = _identifier(row.get("backup_id"), "BACKUP_ID_INVALID")
        if backup_id in backup_ids:
            raise CyberModuleError("BACKUP_ID_DUPLICATED")
        backup_ids.add(backup_id)
        integrity = row.get("integrity_status")
        immutable = row.get("immutable")
        sha256 = row.get("sha256")
        if not isinstance(integrity, str) or integrity not in INTEGRITY or type(immutable) is not bool or (
            not isinstance(sha256, str) or not DIGEST_RE.fullmatch(sha256)
        ):
            raise CyberModuleError("BACKUP_ATTESTATION_INVALID")
        captured = _timestamp(row.get("captured_at"))
        if captured > clock or captured > _timestamp(scope["expires_at"]):
            raise CyberModuleError("BACKUP_TIMESTAMP_INVALID")
        # Incoming backup attestations are never independent proof of restore health.
        # A plain SHA256 of a low-entropy backup id permits dictionary
        # recovery and cross-tenant linkage. The HMAC scope is unambiguous,
        # customer-isolated and uses the trusted verifier key, never user input.
        private_context = json.dumps(
            [scope["tenant_id"], scope["engagement_id"], backup_id],
            ensure_ascii=False, separators=(",", ":"),
        ).encode("utf-8")
        recovery.append({"backup_tag": hmac.new(
            verify_key, private_context, hashlib.sha256,
        ).hexdigest()[:16], "integrity_claim": integrity,
            "immutable_claim": immutable, "captured_at": captured.isoformat(),
            "digest_present": True, "restore_test_verified": False})

    if evidence and not recovery:
        actions.add("verify_immutable_backup_restore_plan")
    level = max((entry["risk"] for entry in evidence), key=LEVEL.get,
                default="informational")
    actions.update(("confirm_authorized_scope_and_affected_asset",
                    "request_human_validation_and_containment_approval",
                    "record_human_review_and_recovery_receipts"))
    if any(row["integrity_claim"] != "verified_claim" or not row["immutable_claim"]
           for row in recovery):
        actions.add("investigate_unverified_or_mutable_backup")

    # Bind digest to the tenant and engagement; no raw evidence or file paths emitted.
    fingerprint = hashlib.sha256(json.dumps({
        "tenant_id": scope["tenant_id"], "engagement_id": scope["engagement_id"],
        "incident_id": incident_id, "indicators": evidence, "backups": recovery,
    }, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")).hexdigest()
    return {
        "bot_id": BOT_ID, "module_id": MODULE_ID,
        "submodule_id": "incident_response",
        "schema": SCHEMA, "tenant_id": scope["tenant_id"],
        "engagement_id": scope["engagement_id"], "incident_id": incident_id,
        "asset_hostname": asset, "risk": level,
        "indicators": evidence, "backup_assessments": recovery,
        "proposed_steps": sorted(actions),
        "audit_sha256": fingerprint,
        "mode": "offline_plan_only",
        "executed_actions": 0,
        "requires_human_authorization": True,
        "evidence_preservation_required": True,
        "backup_restore_proven": False,
        "counterattack_prohibited": True,
        "data_export_executed": False,
        "disclaimer": (
            "Supplied evidence is unverified without collector provenance; "
            "recommendations are not an active incident response."
        ),
    }
