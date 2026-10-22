#!/usr/bin/env python3
"""Fail-closed, independent quality-1000 evidence validator. No deployment side effects."""
import argparse
import hashlib
import json
from pathlib import Path

REQUIRED = ("functionality", "security", "performance", "mobile", "originality",
            "documentation", "reproducibility", "domain_expert", "commercial_readiness", "delivery")
def validate(data, root):
    failures = []
    if not isinstance(data, dict) or data.get("schema") != "saeit.quality1000.v1":
        return ["INVALID_SCHEMA"]
    criteria = data.get("criteria")
    if not isinstance(criteria, dict):
        return ["MISSING_CRITERIA"]
    for name in REQUIRED:
        item = criteria.get(name)
        if not isinstance(item, dict) or item.get("score") != 100 or item.get("status") != "passed":
            failures.append(name + ":NOT_PASSED")
            continue
        evidence = item.get("evidence")
        if not isinstance(evidence, list) or not evidence:
            failures.append(name + ":NO_EVIDENCE")
            continue
        for record in evidence:
            if not isinstance(record, dict):
                failures.append(name + ":INVALID_EVIDENCE")
                continue
            rel, digest = record.get("path"), record.get("sha256")
            if not isinstance(rel, str) or not isinstance(digest, str) or len(digest) != 64:
                failures.append(name + ":INVALID_REFERENCE")
                continue
            path = root / rel
            if path.is_symlink() or not path.is_file() or not path.resolve().is_relative_to(root.resolve()):
                failures.append(name + ":MISSING_OR_UNSAFE_FILE")
                continue
            if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
                failures.append(name + ":HASH_MISMATCH")
    if data.get("independent_review") is not True:
        failures.append("INDEPENDENT_REVIEW_REQUIRED")
    if data.get("owner_publication_approval") is not True:
        failures.append("OWNER_APPROVAL_REQUIRED")
    return failures

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--root", type=Path, required=True)
    args = parser.parse_args()
    try:
        data = json.loads(args.manifest.read_text(encoding="utf-8"))
        failures = validate(data, args.root)
    except (OSError, ValueError, TypeError) as exc:
        failures = ["MANIFEST_READ_OR_PARSE_ERROR"]
    print(json.dumps({"quality1000": "PASS" if not failures else "BLOCKED", "failures": failures}, ensure_ascii=False))
    raise SystemExit(0 if not failures else 1)
if __name__ == "__main__":
    main()
