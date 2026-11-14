"""Cybersecurity capability inside the ONE canonical Mojtaba.bot.ai.

No independent agent identity, scheduler, Django app, network I/O or deployments.
Only offline assessment of pre-collected evidence with signed authorization.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import re
from datetime import datetime, timedelta, timezone

BOT_ID = "mojtaba.bot.ai"
MODULE_ID = "cyber_security"
MANIFEST_SCHEMA = "mojtaba.bot.ai.cyber.engagement.v1"
EVIDENCE_SCHEMA = "mojtaba.bot.ai.cyber.evidence.v1"
HOST_RE = re.compile(r"(?=.{1,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$")
FINDING_ID_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,99}\Z")
REDACTIONS = (
    re.compile(r"(?i)(authorization\s*:\s*bearer\s+)\S+"),
    re.compile(r"(?i)((?:password|secret|api[_-]?key|token)\s*[=:]\s*)\S+"),
    re.compile(r"\bsk-[A-Za-z0-9_-]{12,}\b"),
)
SEVERITIES = frozenset(("informational", "low", "medium", "high", "critical"))


class CyberModuleError(ValueError):
    """Reject unauthorized or malformed offline evidence, fail closed."""


def _periodic_key(key: bytes) -> bool:
    """Reject short-period repeated HMAC keys without pretending to estimate entropy."""
    return any(
        len(key) % period == 0 and key == key[:period] * (len(key) // period)
        for period in range(1, min(8, len(key) - 1) + 1)
    )


def descriptor() -> dict:
    """Metadata for canonical bot's internal capability registry."""
    return {
        "bot_id": BOT_ID, "module_id": MODULE_ID,
        "name": "Cyber Security", "version": "1.0.0",
        "activation": "explicit_canonical_invocation_only",
        "network_access": False, "independent_agent": False,
        "independent_scheduler": False, "side_effects": False,
        "capabilities": ["offline_evidence_review", "scope_validation", "risk_triage"],
        "unimplemented": ["live_scanning", "active_pentest", "continuous_monitoring",
                          "customer_payments", "automatic_remediation"],
    }


def _canonical(document: dict) -> bytes:
    if not isinstance(document, dict):
        raise CyberModuleError("AUTHORIZATION_INVALID")
    payload = {key: value for key, value in document.items() if key != "signature"}
    try:
        return json.dumps(payload, sort_keys=True, ensure_ascii=False,
                          separators=(",", ":"), allow_nan=False).encode("utf-8")
    except (TypeError, ValueError, OverflowError) as exc:
        raise CyberModuleError("AUTHORIZATION_INVALID") from exc


def _timestamp(value: str) -> datetime:
    if not isinstance(value, str) or len(value) > 40:
        raise CyberModuleError("TIME_INVALID")
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise CyberModuleError("TIME_INVALID") from exc
    if result.tzinfo is None:
        raise CyberModuleError("TIMEZONE_REQUIRED")
    return result.astimezone(timezone.utc)


def _host(value: str) -> str:
    if not isinstance(value, str) or value != value.strip():
        raise CyberModuleError("ASSET_INVALID")
    normalized = value.lower().removesuffix(".")
    if not HOST_RE.fullmatch(normalized):
        raise CyberModuleError("ASSET_INVALID")
    return normalized


def _redact(value: str, limit: int = 3000) -> str:
    if not isinstance(value, str) or len(value) > limit:
        raise CyberModuleError("TEXT_INVALID")
    for pattern in REDACTIONS:
        value = pattern.sub(lambda m: (m.group(1) if m.lastindex else "") + "[REDACTED]", value)
    return value


def verify_authorization(engagement: dict, verify_key: bytes, *,
                         now: datetime | None = None) -> dict:
    """Key must come from the canonical bot's trusted secret store."""
    if (not isinstance(verify_key, bytes) or len(verify_key) < 32
            or _periodic_key(verify_key)):
        raise CyberModuleError("VERIFIER_KEY_INVALID")
    if not isinstance(engagement, dict) or engagement.get("schema") != MANIFEST_SCHEMA:
        raise CyberModuleError("AUTHORIZATION_INVALID")
    if engagement.get("bot_id") != BOT_ID or engagement.get("module_id") != MODULE_ID:
        raise CyberModuleError("CANONICAL_IDENTITY_REQUIRED")
    signature = engagement.get("signature")
    if not isinstance(signature, str) or not re.fullmatch(r"[0-9a-f]{64}", signature):
        raise CyberModuleError("SIGNATURE_INVALID")
    expected = hmac.new(verify_key, _canonical(engagement), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(signature, expected):
        raise CyberModuleError("SIGNATURE_INVALID")
    if not isinstance(engagement.get("tenant_id"), str) or not engagement["tenant_id"].strip():
        raise CyberModuleError("TENANT_INVALID")
    if not isinstance(engagement.get("engagement_id"), str) or not engagement["engagement_id"].strip():
        raise CyberModuleError("ENGAGEMENT_INVALID")
    targets = engagement.get("allowed_assets")
    if not isinstance(targets, list) or not 1 <= len(targets) <= 200:
        raise CyberModuleError("SCOPE_INVALID")
    hosts = [_host(host) for host in targets]
    if len(set(hosts)) != len(hosts):
        raise CyberModuleError("SCOPE_DUPLICATED")
    if engagement.get("mode") != "offline_evidence":
        raise CyberModuleError("LIVE_ACTIONS_FORBIDDEN")
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise CyberModuleError("TIMEZONE_REQUIRED")
    issued = _timestamp(engagement.get("issued_at"))
    expires = _timestamp(engagement.get("expires_at"))
    now = now.astimezone(timezone.utc)
    if expires <= issued or expires - issued > timedelta(hours=24):
        raise CyberModuleError("AUTHORIZATION_WINDOW_INVALID")
    if not issued <= now < expires:
        raise CyberModuleError("AUTHORIZATION_EXPIRED_OR_FUTURE")
    return {**engagement, "allowed_assets": hosts}


def review_offline_evidence(*, engagement: dict, evidence: dict, verify_key: bytes,
                            now: datetime | None = None) -> dict:
    """No remote requests, command execution, scanning or mutation."""
    scope = verify_authorization(engagement, verify_key, now=now)
    if not isinstance(evidence, dict) or evidence.get("schema") != EVIDENCE_SCHEMA:
        raise CyberModuleError("EVIDENCE_INVALID")
    if evidence.get("tenant_id") != scope["tenant_id"] or evidence.get("engagement_id") != scope["engagement_id"]:
        raise CyberModuleError("CROSS_TENANT_EVIDENCE_FORBIDDEN")
    submitted = evidence.get("findings")
    if not isinstance(submitted, list) or len(submitted) > 1000:
        raise CyberModuleError("FINDINGS_INVALID")
    findings = []
    ids = set()
    for finding in submitted:
        if not isinstance(finding, dict):
            raise CyberModuleError("FINDING_INVALID")
        host = _host(finding.get("asset_hostname"))
        if host not in scope["allowed_assets"]:
            raise CyberModuleError("ASSET_OUT_OF_SCOPE")
        identifier = finding.get("finding_id")
        severity = finding.get("severity")
        # Identifiers are echoed verbatim in reports: reject embedded
        # addresses, credentials, control characters and markup.
        if not isinstance(identifier, str) or not FINDING_ID_RE.fullmatch(identifier) or identifier in ids:
            raise CyberModuleError("FINDING_ID_INVALID")
        ids.add(identifier)
        if not isinstance(severity, str) or severity not in SEVERITIES:
            raise CyberModuleError("SEVERITY_INVALID")
        findings.append({
            "finding_id": identifier, "asset_hostname": host,
            "severity": severity,
            "title": _redact(finding.get("title"), 200),
            "evidence_summary": _redact(finding.get("evidence_summary"), 3000),
            "remediation": _redact(finding.get("remediation"), 3000),
        })
    levels = {severity: sum(item["severity"] == severity for item in findings)
              for severity in ("critical", "high", "medium", "low", "informational")}
    return {
        "bot_id": BOT_ID, "module_id": MODULE_ID,
        "mode": "offline_evidence", "engagement_id": scope["engagement_id"],
        "tenant_id": scope["tenant_id"], "findings": findings, "counts": levels,
        "audit_sha256": hashlib.sha256(_canonical({"engagement_id": scope["engagement_id"],
                                                    "findings": findings})).hexdigest(),
        "disclaimer": "User-supplied offline findings only; no live test was performed.",
    }
