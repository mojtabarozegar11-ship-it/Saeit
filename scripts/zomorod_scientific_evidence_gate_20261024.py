#!/usr/bin/env python3
"""Evidence intake gate for Zomorod Melal research records.

This tool creates review CANDIDATES only. It does not attest scientific findings,
authenticate people, or publish to the site. Private inputs must not be committed.
Stdlib-only, no network access and no filesystem mutation.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

PROJECT_ID = re.compile(r"^ZM-RP-[0-9]{4}-[0-9]{4,6}$")
SHA256 = re.compile(r"^[a-fA-F0-9]{64}$")
VALID_STAGES = {"registered", "in_progress", "analysis", "completed_report", "published"}
PUBLIC_EVIDENCE_TYPES = {"report", "dataset", "protocol", "publication", "repository", "laboratory_report"}
MAX_RECORDS = 100_000


def text_field(raw, name, minimum=4, maximum=1500):
    value = raw.get(name)
    if not isinstance(value, str) or not minimum <= len(value.strip()) <= maximum:
        raise ValueError(f"{name}:missing_or_invalid")
    return value.strip()


def iso_date(value, name):
    if not isinstance(value, str):
        raise ValueError(f"{name}:missing")
    try:
        parsed = date.fromisoformat(value)
    except ValueError:
        raise ValueError(f"{name}:not_iso_date") from None
    if parsed > datetime.now(timezone.utc).date():
        raise ValueError(f"{name}:future_date")
    return value


def public_https(url):
    if not isinstance(url, str) or len(url) > 2048:
        return False
    try:
        p = urlparse(url)
        host = (p.hostname or "").lower().rstrip(".")
        return (
            p.scheme == "https" and bool(host) and "." in host
            and not host.endswith((".local", ".internal"))
            and host not in {"localhost", "127.0.0.1", "0.0.0.0"}
            and not p.username and not p.password and not p.fragment
            and not host.replace(".", "").isdigit()
        )
    except ValueError:
        return False


def evaluate(record):
    """Return an allowlisted public-review candidate and reasons; never publish."""
    problems = []
    if not isinstance(record, dict):
        return None, ["record:not_object"]
    pid = record.get("project_id")
    if not isinstance(pid, str) or not PROJECT_ID.fullmatch(pid):
        problems.append("project_id:invalid")
    fields = {}
    for key, mini, maxi in (
        ("title", 8, 250),
        ("scientific_lead", 4, 180),
        ("research_question", 20, 1500),
        ("methods", 40, 5000),
        ("limitations", 20, 3000),
    ):
        try:
            fields[key] = text_field(record, key, mini, maxi)
        except ValueError as exc:
            problems.append(str(exc))
    stage = record.get("stage")
    if stage not in VALID_STAGES:
        problems.append("stage:invalid")
    try:
        updated = iso_date(record.get("updated_at"), "updated_at")
    except ValueError as exc:
        problems.append(str(exc))
        updated = None

    references = record.get("evidence")
    public_refs = []
    if not isinstance(references, list) or not references:
        problems.append("evidence:empty")
    else:
        for idx, item in enumerate(references[:100]):
            if not isinstance(item, dict) or item.get("kind") not in PUBLIC_EVIDENCE_TYPES:
                problems.append(f"evidence[{idx}]:kind_invalid")
                continue
            if item.get("visibility") != "public" or item.get("disclosure_permission") is not True:
                problems.append(f"evidence[{idx}]:not_cleared_for_disclosure")
                continue
            url = item.get("url")
            digest = item.get("sha256")
            if not public_https(url) or not isinstance(digest, str) or not SHA256.fullmatch(digest):
                problems.append(f"evidence[{idx}]:url_or_digest_invalid")
                continue
            public_refs.append({"kind": item["kind"], "url": url, "sha256": digest.lower()})
        if len(references) > 100:
            problems.append("evidence:too_many")
        if not public_refs:
            problems.append("evidence:no_disclosable_reference")

    permission = record.get("public_disclosure")
    if not isinstance(permission, dict) or permission.get("approved") is not True:
        problems.append("public_disclosure:not_approved")
    else:
        if not isinstance(permission.get("receipt_sha256"), str) or not SHA256.fullmatch(permission["receipt_sha256"]):
            problems.append("public_disclosure:receipt_digest_invalid")
        try:
            iso_date(permission.get("approved_at"), "public_disclosure.approved_at")
        except ValueError as exc:
            problems.append(str(exc))
    if problems:
        return None, problems
    public_candidate = {
        "project_id": pid,
        "title": fields["title"],
        "scientific_lead": fields["scientific_lead"],
        "research_question": fields["research_question"],
        "methods": fields["methods"],
        "limitations": fields["limitations"],
        "stage": stage,
        "updated_at": updated,
        "evidence": public_refs,
        "disclosure_receipt_sha256": permission["receipt_sha256"].lower(),
        "scientific_verification": "NOT_INDEPENDENTLY_VERIFIED",
        "publication_state": "REVIEW_CANDIDATE_NOT_PUBLISHED",
    }
    return public_candidate, []


def audit_records(records):
    if not isinstance(records, list) or len(records) > MAX_RECORDS:
        raise ValueError("input:expected_bounded_list")
    seen = set()
    candidates, rejected = [], []
    for index, rec in enumerate(records):
        pid = rec.get("project_id") if isinstance(rec, dict) else None
        candidate, issues = evaluate(rec)
        if isinstance(pid, str) and pid in seen:
            issues = list(issues) + ["project_id:duplicate"]
            candidate = None
        if isinstance(pid, str):
            seen.add(pid)
        if candidate is not None:
            candidates.append(candidate)
        else:
            rejected.append({"row": index, "project_id": pid if isinstance(pid, str) else None,
                             "reasons": sorted(set(issues))})
    candidates.sort(key=lambda item: item["project_id"])
    result = {
        "schema": "zomorod.research.evidence-review-candidates.v1",
        "input_count": len(records),
        "candidate_count": len(candidates),
        "rejected_count": len(rejected),
        "automatic_publication_allowed": False,
        "independent_scientific_certification_granted": False,
        "candidates": candidates,
        "rejected": rejected,
    }
    return result


def self_test():
    digest = hashlib.sha256(b"example proof").hexdigest()
    good = {
        "project_id": "ZM-RP-2026-0001",
        "title": "Example evidence-linked study",
        "scientific_lead": "Named Lead",
        "research_question": "What is the measurable change in the test plot?",
        "methods": "A registered protocol with controls and a clearly documented baseline.",
        "limitations": "Synthetic example only; no field observations were collected.",
        "stage": "registered",
        "updated_at": "2026-10-24",
        "evidence": [{"kind": "protocol", "url": "https://example.org/protocol",
                      "sha256": digest, "visibility": "public", "disclosure_permission": True}],
        "public_disclosure": {"approved": True, "approved_at": "2026-10-24",
                              "receipt_sha256": digest},
        "private_personal_information": "THIS MUST NOT BE EXPORTED",
    }
    empty = audit_records([])
    assert empty["candidate_count"] == 0 and not empty["automatic_publication_allowed"]
    valid = audit_records([good])
    assert valid["candidate_count"] == 1
    assert "private_personal_information" not in json.dumps(valid)
    assert valid["candidates"][0]["scientific_verification"] == "NOT_INDEPENDENTLY_VERIFIED"
    bad = dict(good, public_disclosure={"approved": False})
    assert audit_records([bad])["rejected_count"] == 1
    assert audit_records([good, good])["rejected_count"] == 1
    bad_link = dict(good, evidence=[dict(good["evidence"][0], url="http://localhost/private")])
    assert audit_records([bad_link])["candidate_count"] == 0
    bad_private = dict(good, evidence=[dict(good["evidence"][0], disclosure_permission=False)])
    assert audit_records([bad_private])["candidate_count"] == 0
    assert not public_https("https://127.0.0.1/x")
    print("7 evidence-gate checks passed", file=sys.stderr)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", help="Private JSON file containing an array of research records")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        self_test()
        return 0
    if not args.input:
        parser.error("--input is required unless --self-test")
    # Private input read locally; only allowlisted candidate fields leave the process.
    records = json.loads(Path(args.input).read_text(encoding="utf-8"))
    result = audit_records(records)
    json.dump(result, sys.stdout, ensure_ascii=False, indent=2, sort_keys=True)
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
