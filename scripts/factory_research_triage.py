#!/usr/bin/env python3
"""Evidence-based research defect triage, never false scientific approval.

Plans are derived from original research QA ledger blockers; the machine cannot
fabricate peer reviews, citations, internal tests, ownership or market evidence.
Idempotent; previous ledgers and work orders stay untouched. Python >=3.8.
"""
import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile

SCHEMA = "saeit.factory.research-triage.v1"
ID = re.compile(r"^product-([0-9]+)$")
PLANS = {
    "FIVE_DISTINCT_PUBLIC_SOURCES_WITH_LINKED_EVIDENCE_REQUIRED":
        ("independent_public_citations",
         "Obtain at least five genuinely independent, topic-relevant publications with URLs and direct supporting excerpts."),
    "ONE_HUNDRED_DISTINCT_STRONG_EVIDENCE_PASSAGES_REQUIRED":
        ("substantive_evidence",
         "Verify each distinct passage against an original source; reach the documented minimum without duplicates."),
    "ONE_STRUCTURED_INTERNAL_RESEARCH_ACTION_REQUIRED":
        ("reproducible_experiment",
         "Execute a measurable internal experiment, record its raw outputs, protocol and failures."),
    "TEN_FACTOR_VALIDATION_PASS_REQUIRED":
        ("ten_dimension_assessment",
         "Evaluate all ten mandatory business and technical validation factors against real evidence."),
    "FACTORY_OWNER_OR_ACTIVE_PRODUCT_STATE_INVALID":
        ("ownership_confirmation",
         "Resolve the real owner and authorized active state through signed documentary evidence."),
    "PUBLISHED_KNOWLEDGE_PROVENANCE_REQUIRED":
        ("editorial_source_trace",
         "Document exact scientific factual claims, matching citations and independent editorial review."),
    "FAIR_PRICE_AND_COST_REVIEW_REQUIRED":
        ("actual_cost_measurement",
         "Measure real production inputs and sensitivity; never invent revenue or market value."),
    "HUMAN_COMMERCIAL_LICENSE_AND_FACTUAL_REVIEW_REQUIRED":
        ("independent_human_review",
         "Obtain genuinely independent scientific, rights and commercial attestation with provenance."),
}


def sha(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                    separators=(",", ":")).encode("utf8")).hexdigest()


def atomic(path, value):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, stage = tempfile.mkstemp(prefix=".research-triage-", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf8") as file:
            json.dump(value, file, indent=2, ensure_ascii=False, sort_keys=True)
            file.write("\n")
            file.flush()
            os.fsync(file.fileno())
        os.chmod(stage, 0o600)
        os.replace(stage, str(path))
    finally:
        if os.path.exists(stage):
            os.unlink(stage)


def snapshot(root):
    root = Path(root)
    ledger_dir = root / "research-rework"
    if ledger_dir.is_symlink() or not ledger_dir.is_dir():
        raise RuntimeError("RESEARCH_LEDGER_DIRECTORY_MISSING")
    inbox = root / "research-triage"
    inbox.mkdir(parents=True, exist_ok=True, mode=0o700)
    if inbox.is_symlink():
        raise RuntimeError("RESEARCH_TRIAGE_SYMLINK")
    count = Counter()
    actions = Counter()
    updated = 0
    for directory in sorted(ledger_dir.iterdir()):
        if not ID.fullmatch(directory.name):
            continue
        if directory.is_symlink() or not directory.is_dir():
            raise RuntimeError("RESEARCH_UNSAFE_LEDGER")
        original = directory / "ledger.json"
        if original.is_symlink() or not original.is_file() or original.stat().st_size > 1_000_000:
            raise RuntimeError("RESEARCH_LEDGER_NOT_RELIABLE:" + directory.name)
        record = json.loads(original.read_text(encoding="utf8"))
        if record.get("schema") != "saeit.factory.research-rework.v1":
            raise RuntimeError("RESEARCH_LEDGER_SCHEMA_MISMATCH:" + directory.name)
        product_id = int(ID.fullmatch(directory.name).group(1))
        if record.get("product_id") != product_id:
            raise RuntimeError("RESEARCH_LEDGER_ID_MISMATCH")
        history = record.get("history")
        if not isinstance(history, list) or not history:
            raise RuntimeError("RESEARCH_LEDGER_NO_EVIDENCE")
        most_recent = history[-1]
        reasons = most_recent.get("blocking_reasons", [])
        if not isinstance(reasons, list) or any(x not in PLANS for x in reasons):
            raise RuntimeError("RESEARCH_UNRECOGNIZED_REASON")
        previous_status = record.get("current_status")
        count[previous_status] += 1
        for reason in reasons:
            actions[reason] += 1
        fingerprint = sha({"product_id": product_id,
                           "research_ledger_fingerprint": most_recent.get("fingerprint"),
                           "status": previous_status, "reasons": sorted(reasons)})
        plan = {
            "schema": SCHEMA,
            "product_id": product_id,
            "research_ledger_fingerprint": fingerprint,
            "research_evidence_confirmed_complete": False,
            "commercial_approval_claimed": False,
            "source_ledger": str(original.relative_to(root)),
            "status": "requires_real_evidence" if reasons else "pending_independent_review",
            "required_fixes": [
                {"blocker": reason, "deliverable": PLANS[reason][0],
                 "task": PLANS[reason][1], "actual_new_evidence_attached": False}
                for reason in sorted(reasons)
            ],
        }
        dest = inbox / ("product-%d.json" % product_id)
        if dest.exists() and not dest.is_symlink():
            previous = json.loads(dest.read_text(encoding="utf8"))
            if previous.get("research_ledger_fingerprint") == fingerprint:
                continue
        atomic(dest, plan)
        updated += 1
    status = {"schema": SCHEMA, "research_ledgers_found": sum(count.values()),
              "ledger_status_counts": dict(count),
              "defect_type_counts": dict(actions),
              "workplans_created_or_updated": updated,
              "genuine_research_repairs_verified_this_run": 0,
              "independent_human_review_automatically_completed": False,
              "source_evidence_fabricated": False}
    atomic(inbox / "triage-status.json", status)
    return status


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--out", required=True)
    arg = p.parse_args()
    print("FACTORY_RESEARCH_TRIAGE=" + json.dumps(snapshot(arg.out), sort_keys=True))


if __name__ == "__main__":
    main()
