#!/usr/bin/env python3
"""Fail-closed, offline manuscript/ledger release gate. Never submits or publishes."""
import argparse
import csv
import hashlib
import json
import re
from pathlib import Path

REQUIRED_SECTIONS = (
    "## Abstract", "## 1. Introduction", "## 2. Methods",
    "## 6. Limitations", "## 7. Conclusion", "## References",
)
LEDGER_FIELDS = (
    "claim_id", "source_url", "source_locator", "source_printed_evidence",
    "admissible_claim", "prohibited_inference", "evidence_status",
    "editorial_resolution", "human_reviewer_gate",
)
APPROVAL_FIELDS = (
    "author_approved", "independent_source_review_complete",
    "journal_requirements_checked", "ethics_rights_checked",
    "source_limitations_approved", "no_unsupported_inferences",
)


def assess(manuscript: Path, ledger: Path, approval: Path | None = None) -> dict:
    raw = manuscript.read_bytes()
    text = raw.decode("utf-8")
    digest = hashlib.sha256(raw).hexdigest()
    with ledger.open(encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream, delimiter="\t")
        columns = reader.fieldnames or []
        rows = list(reader)
    missing_columns = sorted(set(LEDGER_FIELDS) - set(columns))
    ids = [(r.get("claim_id") or "").strip() for r in rows]
    source_blockers = [
        r.get("claim_id", "<missing id>")
        for r in rows
        if "BLOCKED" in (r.get("evidence_status") or "").upper()
    ]
    references = text.split("## References", 1)[-1] if "## References" in text else ""
    reference_numbers = [int(n) for n in re.findall(r"(?m)^(\d+)\.\s", references)]
    checks = {
        "full_manuscript_sections": text.lstrip().startswith("# ") and all(
            heading in text for heading in REQUIRED_SECTIONS
        ),
        "narrative_review_type_declared": "critical narrative review" in text.lower()
        and "not a systematic review" in text.lower(),
        "reference_numbering": len(reference_numbers) >= 8
        and reference_numbers == list(range(1, len(reference_numbers) + 1)),
        "doi_syntax_present": bool(re.search(r"10\.\d{4,9}/\S+", references)),
        "ledger_exact_schema": not missing_columns,
        "ledger_nonempty": len(rows) >= 3,
        "ledger_ids_unique": len(ids) == len(set(ids)) and all(ids),
        "ledger_rows_complete": not missing_columns and all(
            all((r.get(field) or "").strip() for field in LEDGER_FIELDS)
            for r in rows
        ),
        "ledger_https_sources": bool(rows) and all(
            (r.get("source_url") or "").startswith("https://") for r in rows
        ),
        "no_editorial_banner": "### Editorial release gate" not in text
        and not bool(re.search(r"\*\*C\d{2,3} (?:editorial|release note)", text)),
        "no_placeholders": not bool(re.search(r"\b(?:TODO|TBD|LOREM IPSUM)\b", text, re.I)),
    }
    blockers = [f"STRUCTURE:{k}" for k, ok in checks.items() if not ok]
    manifest = json.loads(approval.read_text(encoding="utf-8")) if approval else {}
    for field in APPROVAL_FIELDS:
        if manifest.get(field) is not True:
            blockers.append(f"APPROVAL:{field}")
    if manifest.get("manuscript_sha256") != digest:
        blockers.append("APPROVAL:manuscript_sha256_not_signed")
    if not (isinstance(manifest.get("target_journal"), str)
            and manifest["target_journal"].strip()):
        blockers.append("APPROVAL:target_journal")
    # A documented primary-source discrepancy may remain in a critical review
    # only when transparently quarantined and explicitly approved by humans.
    # It is NOT an automatic numerical correction.
    return {
        "schema": "R01-QC-C122",
        "manuscript": str(manuscript),
        "manuscript_sha256": digest,
        "ledger": str(ledger),
        "ledger_rows": len(rows),
        "missing_ledger_columns": missing_columns,
        "reference_count": len(reference_numbers),
        "checks": checks,
        "unresolved_source_claim_ids": source_blockers,
        "decision": "ELIGIBLE_FOR_HUMAN_SUBMISSION"
        if not blockers else "BLOCK_SUBMISSION",
        "blockers": blockers,
        "disclaimer": (
            "A pass only permits human submission; it is never evidence "
            "of actual submission, acceptance, publication, or source truth."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manuscript", required=True, type=Path)
    parser.add_argument("--ledger", required=True, type=Path)
    parser.add_argument("--approval", type=Path, default=None)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()
    result = assess(args.manuscript, args.ledger, args.approval)
    rendered = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    raise SystemExit(0 if result["decision"] == "ELIGIBLE_FOR_HUMAN_SUBMISSION" else 2)


if __name__ == "__main__":
    main()
