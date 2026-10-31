#!/usr/bin/env python3
"""Build a private, read-only Zomorod proposal register from an approved CSV.

No financial SQLite tables are opened. Without --install this command only
validates and reports aggregate counts. Never put the private CSV in Git.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import os
from pathlib import Path
import re
import sys
import tempfile

REQUIRED = {
    "source_id", "external_key", "title_or_subject", "official_title_verified",
    "decision", "execution_state", "planned_operational_jobs",
    "actual_employees_hired", "owner", "classification_or_parent",
    "budget_irr", "accounting_document_created", "source_evidence",
}
DECISIONS = {"approved", "rejected", "undetermined"}
KEY_PATTERN = re.compile(r"ZM-(?:[0-9]{3}[A-Z]?|EX-[0-9]{2,3}-[A-Z])\Z")
JOBS_PATTERN = re.compile(r"(?:0|[1-9][0-9]*)(?:\.0)?\Z")


def fail(reason: str) -> None:
    raise ValueError(reason)


def parse_csv(path: Path) -> dict:
    raw = path.read_bytes()
    if not raw or len(raw) > 2_000_000:
        fail("CSV size outside accepted range")
    digest = hashlib.sha256(raw).hexdigest()
    try:
        content = raw.decode("utf-8-sig")
    except UnicodeError:
        fail("CSV must be UTF-8")
    reader = csv.DictReader(io.StringIO(content, newline=""))
    if not reader.fieldnames or not REQUIRED.issubset(reader.fieldnames):
        fail("CSV required columns missing")
    if len(reader.fieldnames) != len(set(reader.fieldnames)):
        fail("CSV contains duplicate column names")
    records = []
    seen = set()
    for row in reader:
        if None in row or any(v is None for v in row.values()):
            fail("CSV row contains unexpected columns")
        key = row["external_key"].strip()
        code = row["source_id"].strip()
        if not KEY_PATTERN.fullmatch(key) or key in seen:
            fail("Invalid or duplicated proposal key: " + key)
        if key != "ZM-" + (code.zfill(3) if code.isdecimal() else code):
            fail("Proposal key and source identifier mismatch: " + key)
        seen.add(key)
        decision = row["decision"].strip()
        if decision not in DECISIONS:
            fail("Unexpected proposal decision: " + key)
        verified = row["official_title_verified"].strip()
        if verified not in ("True", "False"):
            fail("Invalid title verification flag: " + key)
        title = row["title_or_subject"].strip()
        if decision == "approved" and not title:
            fail("Approved proposal has no title: " + key)
        jobs_text = row["planned_operational_jobs"].strip()
        if decision == "approved":
            if not JOBS_PATTERN.fullmatch(jobs_text):
                fail("Approved proposal lacks nonnegative integer jobs: " + key)
            jobs = int(jobs_text.split(".")[0])
        else:
            if jobs_text:
                fail("Non-approved proposal has allocated jobs: " + key)
            jobs = None
        if row["actual_employees_hired"].strip():
            fail("Actual hires must not be imported from planning CSV: " + key)
        if row["budget_irr"].strip():
            fail("Financial budget must be imported only by accounting workflow: " + key)
        if row["accounting_document_created"].strip() != "False":
            fail("Unexpected financial-document field: " + key)
        state = row["execution_state"].strip()
        if state != ("planned" if decision == "approved" else "not_approved"):
            fail("Execution state inconsistent with decision: " + key)
        records.append({
            "external_key": key,
            "source_id": code,
            "title": title,
            "official_title_verified": verified == "True",
            "decision": decision,
            "execution_state": state,
            "planned_operational_jobs": jobs,
            "actual_employees_hired": None,
            "owner": row["owner"].strip(),
            "classification_or_parent": row["classification_or_parent"].strip(),
            "source_evidence": row["source_evidence"].strip(),
            "review_required": key == "ZM-142",  # conflicting older status; no execution authority
        })
    if not records:
        fail("No proposal records found")
    counts = {d: sum(r["decision"] == d for r in records) for d in sorted(DECISIONS)}
    summary = {
        "records": len(records),
        "approved": counts["approved"],
        "rejected": counts["rejected"],
        "undetermined": counts["undetermined"],
        "planned_operational_jobs": sum(r["planned_operational_jobs"] or 0 for r in records),
        "actual_employees_hired": None,
        "titles_needing_verification": sum(not r["official_title_verified"] for r in records),
        "decision_review_flags": sum(r["review_required"] for r in records),
    }
    return {"version": 1, "source_sha256": digest, "summary": summary, "items": records}


def install(snapshot: dict, target: Path) -> str:
    if target.name != "approvals_snapshot.json":
        fail("Target filename must be approvals_snapshot.json")
    if not target.is_absolute() or target.is_symlink():
        fail("Target must be an absolute, non-symlink path")
    parent = target.parent
    if not parent.is_dir() or parent.is_symlink():
        fail("Existing private target directory required")
    if parent.stat().st_mode & 0o077:
        fail("Private target directory must not grant group/other access")
    if target.exists():
        if not target.is_file():
            fail("Existing snapshot is not a regular file")
        existing = json.loads(target.read_text(encoding="utf-8"))
        if existing.get("source_sha256") == snapshot["source_sha256"]:
            return "ALREADY_INSTALLED"
        fail("Different existing snapshot: backup and controlled replacement required")
    payload = (json.dumps(snapshot, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")
    fd, temporary = tempfile.mkstemp(prefix=".approvals-", suffix=".tmp", dir=parent)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        if target.exists():
            fail("Target appeared during installation")
        # Exact target is new; never overwrite an existing master register.
        os.link(temporary, target)
        os.unlink(temporary)
        return "INSTALLED"
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("csv", type=Path)
    p.add_argument("--install", action="store_true", help="Create a new private snapshot only")
    p.add_argument("--output", type=Path)
    p.add_argument("--expected-sha256")
    p.add_argument("--expected-records", type=int)
    p.add_argument("--expected-approved", type=int)
    p.add_argument("--expected-rejected", type=int)
    p.add_argument("--expected-undetermined", type=int)
    p.add_argument("--expected-jobs", type=int)
    args = p.parse_args(argv)
    try:
        snapshot = parse_csv(args.csv)
        s = snapshot["summary"]
        controls = [
            ("sha256", snapshot["source_sha256"], args.expected_sha256),
            ("records", s["records"], args.expected_records),
            ("approved", s["approved"], args.expected_approved),
            ("rejected", s["rejected"], args.expected_rejected),
            ("undetermined", s["undetermined"], args.expected_undetermined),
            ("planned jobs", s["planned_operational_jobs"], args.expected_jobs),
        ]
        if args.install and (args.output is None or any(expected is None for _, _, expected in controls)):
            fail("Install needs --output and every expected count/digest control")
        for label, actual, expected in controls:
            if expected is not None and actual != expected:
                fail("Expectation mismatch for " + label)
        outcome = install(snapshot, args.output) if args.install else "VALIDATED_READ_ONLY"
        print("ZM_APPROVAL_REGISTER=" + outcome)
        print("SOURCE_SHA256=" + snapshot["source_sha256"])
        for key, value in s.items():
            print(key.upper() + "=" + ("unavailable" if value is None else str(value)))
        print("FINANCIAL_DB_TOUCHED=no")
        return 0
    except (OSError, ValueError, csv.Error, json.JSONDecodeError) as exc:
        print("ZM_APPROVAL_REGISTER=BLOCKED", file=sys.stderr)
        print("ERROR_CLASS=" + type(exc).__name__, file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
