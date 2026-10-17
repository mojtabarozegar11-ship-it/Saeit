#!/usr/bin/env python3
"""Read-only all-or-nothing quality acceptance for the MojPlayWin main site.

A declared 100/100 grade is NOT enough: every gate needs independently
reviewable evidence, plus a manually authorized live-release record.
This checker does not execute production changes or validate a claimed external
URL. Operations must verify the underlying evidence before changing a status.
"""
from __future__ import annotations

import argparse
from datetime import datetime
import json
from pathlib import Path
from urllib.parse import urlsplit

MANDATORY = frozenset({
    "approved_orbital_design",
    "responsive_interactions",
    "content_and_pages",
    "visual_media",
    "performance_mobile",
    "performance_desktop",
    "accessibility",
    "technical_best_practices",
    "seo_and_indexing",
    "products_inventory",
    "crypto_payment_integrity",
    "django_admin",
    "agents_runtime",
    "security_privacy",
    "protected_subsites",
    "backup_and_rollback",
    "support_forms",
    "legal_footer",
    "approved_release",
})

OWNER_APPROVAL = {"approved_orbital_design", "approved_release"}
AUTOMATED_REQUIREMENTS = MANDATORY - OWNER_APPROVAL
APPROVED_PROOF_KINDS = {"automated", "manual_owner", "operational_verification"}


def valid_evidence(entry, *, manual=False):
    if not isinstance(entry, dict):
        return False
    kind = entry.get("kind")
    uri = entry.get("url")
    if kind not in APPROVED_PROOF_KINDS or not isinstance(uri, str):
        return False
    parsed = urlsplit(uri)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        return False
    if not isinstance(entry.get("summary"), str) or len(entry["summary"].strip()) < 15:
        return False
    if entry.get("result") != "pass":
        return False
    if manual and kind != "manual_owner":
        return False
    if not manual and kind == "manual_owner":
        return False
    return True


def valid_timestamp(value):
    if not isinstance(value, str):
        return False
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return result.tzinfo is not None and result.utcoffset() is not None
    except ValueError:
        return False


def validate(manifest: dict) -> dict:
    problems = []
    if manifest.get("candidate_pr") != 390:
        problems.append("unexpected_main_site_candidate_pr")
    if manifest.get("site") != "MojPlayWin MAIN ONLY":
        problems.append("wrong_site_scope")
    gates = manifest.get("gates", [])
    if not isinstance(gates, list):
        gates = []
        problems.append("invalid_gate_list")
    ids = [g.get("id") for g in gates if isinstance(g, dict)]
    missing = sorted(MANDATORY - set(ids))
    unexpected = sorted(set(ids) - MANDATORY)
    if missing or unexpected or len(ids) != len(gates) or len(set(ids)) != len(ids):
        problems.append("invalid_required_gate_inventory")
    evaluations = {}
    for gate in gates:
        if not isinstance(gate, dict):
            problems.append("non_object_gate")
            continue
        key = gate.get("id")
        if key not in MANDATORY:
            continue
        reasons = []
        if gate.get("status") != "passed":
            reasons.append("not_passed")
        proof = gate.get("evidence", [])
        if not isinstance(proof, list) or not proof:
            reasons.append("no_evidence")
        else:
            manual = key in OWNER_APPROVAL
            if not any(valid_evidence(x, manual=manual) for x in proof):
                reasons.append("no_acceptable_independently_reviewable_proof")
        if not valid_timestamp(gate.get("verified_at_utc")):
            reasons.append("no_utc_verification_time")
        evaluations[key] = {
            "accepted": not reasons,
            "issues": reasons,
        }
    for gate_id in missing:
        evaluations[gate_id] = {"accepted": False, "issues": ["missing_gate"]}
    accepted_count = sum(1 for value in evaluations.values() if value["accepted"])
    allowed = not problems and len(evaluations) == len(MANDATORY) and accepted_count == len(MANDATORY)
    return {
        "release_authorized_by_checklist": allowed,
        "accepted_gates": accepted_count,
        "required_gates": len(MANDATORY),
        "incomplete_gates": [k for k, v in sorted(evaluations.items()) if not v["accepted"]],
        "schema_issues": problems,
        "gate_results": evaluations,
        "limitation": ("This validator checks declarations and evidence format; "
                       "independent investigation, actual service tests and protected deployment approval remain required."),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=Path("quality/mojplaywin-acceptance-100.json"))
    parser.add_argument("--output", type=Path, default=Path("mojplaywin-release-100-result.json"))
    parser.add_argument("--require-ready", action="store_true")
    options = parser.parse_args()

    data = json.loads(options.manifest.read_text(encoding="utf-8"))
    decision = validate(data)
    options.output.write_text(json.dumps(decision, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"MOJPLAYWIN_RELEASE_100={decision['accepted_gates']}/{decision['required_gates']}")
    print("MOJPLAYWIN_DEPLOY_ALLOWED="+str(decision["release_authorized_by_checklist"]).upper())
    print("INCOMPLETE="+",".join(decision["incomplete_gates"]))
    if options.require_ready and not decision["release_authorized_by_checklist"]:
        raise SystemExit("RELEASE BLOCKED: not all required quality dimensions carry reviewed evidence.")


if __name__ == "__main__":
    main()
