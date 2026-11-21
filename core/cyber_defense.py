"""Side-effect-free incident triage for the Saeit/Mojtaba master agent.

The functions here NEVER probe, contact, modify or delete remote systems. A
caller must persist sealed records in access-controlled append-only storage;
an in-memory hash chain alone does not prove independent custody.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha256
import ipaddress
import json
import re


EVENT_TYPES = frozenset({
    "authentication_failed", "authentication_succeeded", "mfa_failed",
    "privileged_action_denied", "credential_exposure_suspected",
    "unexpected_data_transfer", "integrity_change", "malware_indicator",
    "prompt_injection_attempt", "backup_restore_failed",
})
INDICATOR_TYPES = frozenset({
    "attempt_count", "bytes_out", "baseline_bytes_out", "mfa_passed",
    "known_device", "integrity_verified", "backup_verified",
})
MAX_IDENTIFIER_LENGTH = 128
GENESIS_HASH = "0" * 64
_HASH = re.compile(r"^[0-9a-f]{64}$")


def _utc_time(value):
    if value is None:
        value = datetime.now(timezone.utc)
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise ValueError("observed_at must be a timezone-aware datetime")
    return value.astimezone(timezone.utc).isoformat(timespec="microseconds")


def _identifier(value, field):
    value = str(value or "")
    if len(value) > MAX_IDENTIFIER_LENGTH or any(ord(ch) < 32 for ch in value):
        raise ValueError(f"invalid {field}")
    return value


def make_security_event(kind, asset, *, actor_id="", source_ip="",
                        indicators=None, observed_at=None):
    """Return a minimal allowlisted event, without payloads or credentials."""
    if kind not in EVENT_TYPES:
        raise ValueError("unsupported security event type")
    asset = _identifier(asset, "asset")
    if not asset:
        raise ValueError("asset is required")
    source_ip = _identifier(source_ip, "source_ip")
    if source_ip:
        try:
            source_ip = str(ipaddress.ip_address(source_ip))
        except ValueError as exc:
            raise ValueError("invalid source_ip") from exc
    values = dict(indicators or {})
    if not set(values).issubset(INDICATOR_TYPES):
        raise ValueError("unapproved indicator; never log payloads or secrets")
    for key, value in values.items():
        if key in {"mfa_passed", "known_device", "integrity_verified", "backup_verified"}:
            if type(value) is not bool:
                raise ValueError(f"{key} must be bool")
        elif type(value) is not int or value < 0:
            raise ValueError(f"{key} must be a nonnegative integer")
    return {
        "kind": kind,
        "asset": asset,
        "actor_id": _identifier(actor_id, "actor_id"),
        "source_ip": source_ip,
        "indicators": values,
        "observed_at": _utc_time(observed_at),
    }


def seal_evidence(event, *, previous_hash=GENESIS_HASH):
    """Produce a deterministic SHA-256 chained evidence envelope."""
    if not isinstance(previous_hash, str) or not _HASH.fullmatch(previous_hash):
        raise ValueError("invalid previous_hash")
    if not isinstance(event, dict) or set(event) != {
        "kind", "asset", "actor_id", "source_ip", "indicators", "observed_at"
    }:
        raise ValueError("event must be created by make_security_event")
    try:
        validated = make_security_event(
            event["kind"], event["asset"], actor_id=event["actor_id"],
            source_ip=event["source_ip"], indicators=event["indicators"],
            observed_at=datetime.fromisoformat(event["observed_at"]),
        )
    except (TypeError, AttributeError, KeyError) as exc:
        raise ValueError("invalid security event") from exc
    if validated != event:
        raise ValueError("noncanonical security event")
    payload = {"event": event, "previous_hash": previous_hash}
    serialized = json.dumps(payload, sort_keys=True, ensure_ascii=False,
                            separators=(",", ":"), allow_nan=False)
    return {**payload, "record_hash": sha256(serialized.encode("utf-8")).hexdigest()}


def verify_evidence_chain(records):
    """Check chain integrity; authenticity requires trusted external custody."""
    previous_hash = GENESIS_HASH
    try:
        for record in records:
            if set(record) != {"event", "previous_hash", "record_hash"}:
                return False
            if record["previous_hash"] != previous_hash:
                return False
            expected = seal_evidence(record["event"], previous_hash=previous_hash)
            if record["record_hash"] != expected["record_hash"]:
                return False
            previous_hash = expected["record_hash"]
    except (TypeError, ValueError, KeyError, OverflowError, AttributeError):
        return False
    return True


def triage_security_events(events, *, now=None, window_minutes=15):
    """Correlate safe telemetry into an advisory severity, not an accusation."""
    if type(window_minutes) is not int or not 1 <= window_minutes <= 1440:
        raise ValueError("invalid window_minutes")
    current = now or datetime.now(timezone.utc)
    if not isinstance(current, datetime) or current.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    current = current.astimezone(timezone.utc)
    cutoff = current - timedelta(minutes=window_minutes)
    active = []
    for event in events:
        # Fail closed on malformed telemetry instead of trusting caller input.
        seal_evidence(event)
        timestamp = datetime.fromisoformat(event["observed_at"])
        if cutoff <= timestamp <= current:
            active.append(event)
    findings = []
    failures = {}
    for event in active:
        kind = event["kind"]
        source = (event["asset"], event["source_ip"] or event["actor_id"] or "unknown")
        if kind in {"authentication_failed", "mfa_failed"}:
            failures[source] = failures.get(source, 0) + max(1, event["indicators"].get("attempt_count", 1))
        if kind in {"credential_exposure_suspected", "malware_indicator"}:
            findings.append("suspected_compromise")
        elif kind == "unexpected_data_transfer":
            volume = event["indicators"].get("bytes_out")
            baseline = event["indicators"].get("baseline_bytes_out")
            if volume is not None and baseline is not None and volume > max(1000000, baseline * 3):
                findings.append("possible_exfiltration")
            else:
                findings.append("unexpected_transfer_needs_review")
        elif kind in {"privileged_action_denied", "integrity_change"}:
            findings.append("privilege_or_integrity_anomaly")
        elif kind == "prompt_injection_attempt":
            findings.append("untrusted_instruction_attempt")
        elif kind == "backup_restore_failed":
            findings.append("recovery_gap")
    if any(count >= 5 for count in failures.values()):
        findings.append("authentication_burst")
    severity = "critical" if "possible_exfiltration" in findings else (
        "high" if "suspected_compromise" in findings or "authentication_burst" in findings
        else "medium" if findings else "informational"
    )
    return {
        "severity": severity,
        "findings": sorted(set(findings)),
        "events_examined": len(active),
        "identity_status": "unverified",
        "automated_external_action": False,
    }


def identity_assessment(*, account_match=False, device_match=False,
                        independently_verified=False):
    """Never infer a natural person's identity from an IP or account alone."""
    if any(type(v) is not bool for v in (account_match, device_match, independently_verified)):
        raise ValueError("evidence flags must be boolean")
    if independently_verified and account_match and device_match:
        return "corroborated_for_authorized_review"
    if account_match or device_match:
        return "technical_lead_unverified"
    return "unknown"


def defensive_response_plan(assessment):
    """Offer actions on owned assets only; never authorize hack-back."""
    severity = assessment.get("severity")
    if severity not in {"critical", "high", "medium", "informational"}:
        raise ValueError("invalid assessment")
    steps = ["preserve_logs_and_hashes", "validate_scope_and_owner_authority"]
    if severity in {"high", "critical"}:
        steps += ["review_session_revocation", "rotate_exposed_credentials",
                  "isolate_affected_owned_assets", "verify_clean_offline_backups"]
    if severity == "critical":
        steps += ["prepare_provider_preservation_and_takedown_request",
                  "assess_notification_obligations", "restore_verified_backup_to_owned_assets"]
    return {
        "steps_for_authorized_review": steps,
        "requires_owner_approval": True,
        "external_system_access": "prohibited_without_separate_lawful_authority",
        "remote_deletion_guarantee": False,
        "data_return_guarantee": False,
        "automatic_actions_taken": [],
    }
