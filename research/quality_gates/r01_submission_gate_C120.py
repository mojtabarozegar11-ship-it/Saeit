#!/usr/bin/env python3
"""Offline, fail-closed research submission gate; no network or publication side effects."""
import argparse
import csv
import hashlib
import io
import json
import re
from pathlib import Path

REQUIRED_SECTIONS = ["## Abstract", "## 1. Introduction", "## 2. Methods", "## 6. Limitations", "## References"]
LEDGER_FIELDS = {"id", "source_url", "locator", "printed_evidence", "admissible_claim", "status"}


def assess(manuscript: Path, ledger: Path, approval: Path | None = None):
    text = manuscript.read_text(encoding="utf-8")
    digest = hashlib.sha256(manuscript.read_bytes()).hexdigest()
    rows = list(csv.DictReader(io.StringIO(ledger.read_text(encoding="utf-8")), delimiter="\t"))
    headers = set(rows[0]) if rows else set()
    checks = {
        "full_manuscript_sections": text.lstrip().startswith("# ") and all(s in text for s in REQUIRED_SECTIONS),
        "reference_dois_present": bool(re.search(r"10\.\d{4,9}/", text)),
        "ledger_columns": LEDGER_FIELDS <= headers,
        "ledger_rows": len(rows) >= 3,
        "ledger_source_urls": bool(rows) and all((r.get("source_url") or "").startswith("https://") for r in rows),
        "ledger_unique_ids": len({r.get("id") for r in rows}) == len(rows),
        "no_editorial_release_tail": "### Editorial release gate" not in text,
        "no_versioned_editorial_banners": not bool(re.search(r"\*\*C\d{2,3} (?:editorial|release note|original-source|source correction)", text)),
        "source_conflicts_declared": any("BLOCKED" in (r.get("status") or "") for r in rows),
    }
    blockers = ["CHECK_FAILED:" + k for k, passed in checks.items() if not passed]
    source_blockers = [r["id"] for r in rows if "BLOCKED" in (r.get("status") or "")]
    if source_blockers:
        blockers.append("UNRESOLVED_SOURCE_CLAIMS:" + ",".join(source_blockers))
    manifest = json.loads(approval.read_text(encoding="utf-8")) if approval else {}
    for field in ("author_approved", "independent_source_review_complete", "journal_requirements_checked", "ethics_rights_checked"):
        if manifest.get(field) is not True:
            blockers.append("MISSING_APPROVAL:" + field)
    if manifest.get("manuscript_sha256") != digest:
        blockers.append("MANUSCRIPT_HASH_NOT_APPROVED")
    if not manifest.get("target_journal"):
        blockers.append("TARGET_JOURNAL_NOT_CONFIRMED")
    return {
        "manuscript": str(manuscript), "sha256": digest, "ledger_rows": len(rows), "checks": checks,
        "unresolved_source_ids": source_blockers,
        "decision": "BLOCK_SUBMISSION" if blockers else "ELIGIBLE_FOR_HUMAN_SUBMISSION",
        "blockers": blockers,
        "note": "Eligibility is not proof of submission, acceptance or publication."
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--manuscript", required=True, type=Path)
    p.add_argument("--ledger", required=True, type=Path)
    p.add_argument("--approval", type=Path, help="Author-supplied approval manifest; never synthesized")
    p.add_argument("--output", type=Path)
    a = p.parse_args()
    result = assess(a.manuscript, a.ledger, a.approval)
    rendered = json.dumps(result, indent=2, ensure_ascii=False) + "\n"
    if a.output:
        a.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    raise SystemExit(0 if result["decision"] == "ELIGIBLE_FOR_HUMAN_SUBMISSION" else 2)


if __name__ == "__main__":
    main()
