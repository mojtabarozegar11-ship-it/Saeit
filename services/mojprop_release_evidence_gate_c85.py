"""Fail-closed, read-only Moj Prop release evidence validator.

This module never authorizes a deployment or executes external commands.
It rejects missing, expired, mismatched or unverified evidence. A successful
result is an audit input, NOT owner approval or a production release permit.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import unicodedata
from pathlib import Path

SHA = re.compile(r"^[0-9a-f]{40}$")
REQUIRED = (
    "full_ci", "django_ci", "source_ci", "app_backup", "media_backup",
    "database_backup", "independent_database_restore", "app_restore",
    "media_restore", "rollback_rehearsal", "passenger_wsgi",
    "tenant_isolation", "live_database_compatibility", "csp_live",
    "email_ownership", "owner_merge_approval", "owner_deploy_approval",
)
NO_DEPLOY = "NO_DEPLOY"


def _unsafe_evidence_text(value: str) -> bool:
    """Reject invisible format/control characters that can spoof audit references."""
    return any(unicodedata.category(char) in {"Cc", "Cf", "Cs"} for char in value)


def validate_evidence(document: object, expected_sha: str, now: dt.datetime | None = None) -> list[str]:
    errors: list[str] = []
    if not isinstance(document, dict):
        return ["evidence must be an object"]
    if not SHA.fullmatch(expected_sha):
        return ["expected SHA must be a full lowercase 40-character commit"]
    if document.get("commit_sha") != expected_sha:
        errors.append("commit SHA mismatch")
    if document.get("environment") != "production":
        errors.append("production environment not attested")
    if document.get("status") != NO_DEPLOY:
        errors.append("status must remain NO_DEPLOY")
    now = now or dt.datetime.now(dt.timezone.utc)
    artifact_refs: set[str] = set()
    for key in REQUIRED:
        item = document.get(key)
        if not isinstance(item, dict):
            errors.append(f"{key}: missing evidence object")
            continue
        if item.get("verified") is not True:
            errors.append(f"{key}: not independently verified")
        if item.get("commit_sha") != expected_sha:
            errors.append(f"{key}: commit mismatch")
        uri = item.get("artifact_uri")
        if not isinstance(uri, str) or not uri.strip():
            errors.append(f"{key}: missing artifact reference")
        elif (uri.strip().lower() in {"none", "n/a", "unknown", "pending", "todo"}
              or _unsafe_evidence_text(uri)
              or uri != uri.strip()):
            errors.append(f"{key}: invalid artifact reference")
        elif uri in artifact_refs:
            errors.append(f"{key}: duplicate artifact reference")
        else:
            artifact_refs.add(uri)
        reviewer = item.get("reviewer")
        if (not isinstance(reviewer, str) or not reviewer.strip()
            or reviewer != reviewer.strip()
            or reviewer.casefold() in {"none", "n/a", "unknown", "pending", "todo", "tbd", "test"}
            or _unsafe_evidence_text(reviewer)):
            errors.append(f"{key}: missing or invalid reviewer")
        try:
            stamp = dt.datetime.fromisoformat(item["verified_at"].replace("Z", "+00:00"))
            if stamp.tzinfo is None or stamp > now or now - stamp > dt.timedelta(hours=24):
                errors.append(f"{key}: stale, future or timezone-naive timestamp")
        except (KeyError, AttributeError, TypeError, ValueError):
            errors.append(f"{key}: invalid timestamp")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Read-only evidence audit; never deploys")
    parser.add_argument("evidence", type=Path)
    parser.add_argument("--sha", required=True)
    args = parser.parse_args()
    try:
        document = json.loads(args.evidence.read_text(encoding="utf-8"))
        failures = validate_evidence(document, args.sha)
    except (OSError, ValueError) as exc:
        failures = [f"cannot read evidence: {type(exc).__name__}"]
    print(json.dumps({"decision": NO_DEPLOY, "evidence_complete": not failures, "errors": failures}, ensure_ascii=False))
    return 0 if not failures else 2


if __name__ == "__main__":
    raise SystemExit(main())
