#!/usr/bin/env python3
"""Validate non-sensitive ZM_ACTIONS_V1 receipts before importing them.

Usage: python scripts/validate_zm_actions_receipt.py report.md
No network, database writes, or external dependencies.
"""
import json
import re
import sys
from pathlib import Path

START = "ZM_ACTIONS_V1_START"
END = "ZM_ACTIONS_V1_END"
REPORT = re.compile(r"^## گزارش ۰۵-([۰-۹0-9]{4,}) \\| (\\d{4}-\\d\\d-\\d\\d \\d\\d:\\d\\d UTC) \\| ([A-Za-z0-9_-]{8,128})$", re.M)
EVIDENCE = re.compile(r"^https://github\\.com/mojtabarozegar11-ship-it/Saeit/(?:commit/[0-9a-f]{40}|actions/runs/[0-9]+|pull/[0-9]+|issues/[0-9]+)$")
STATUSES = {"completed", "partial", "blocked", "not_started"}

def validate(document: str) -> list[str]:
    errors = []
    if document.count(START) != 1 or document.count(END) != 1:
        return ["expected exactly one receipt block"]
    header = REPORT.search(document)
    if not header:
        errors.append("missing canonical Persian report header")
    try:
        payload = json.loads(document.split(START, 1)[1].split(END, 1)[0].strip())
    except (ValueError, IndexError):
        return errors + ["invalid JSON receipt"]
    if not isinstance(payload, dict) or payload.get("version") != 1:
        errors.append("invalid receipt version")
    code = payload.get("report_code")
    if header:
        number = header.group(1).translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789"))
        if code != "05-" + number:
            errors.append("report code does not match header")
    if not isinstance(code, str) or not re.fullmatch(r"05-[0-9]{4,}", code):
        errors.append("invalid report code")
        code = "05-INVALID"
    actions = payload.get("actions")
    if not isinstance(actions, list) or len(actions) > 20:
        return errors + ["actions must be an array of at most 20 entries"]
    ids = set()
    for i, action in enumerate(actions, 1):
        if not isinstance(action, dict):
            errors.append(f"action {i}: not an object")
            continue
        identifier = action.get("id")
        if not isinstance(identifier, str) or not re.fullmatch(r"ZM" + re.escape(code) .replace("05-", "05-") + r"-A(?:0[1-9]|1[0-9]|20)", identifier):
            # Canonical form ZM05-NNNN-A01.
            expected_prefix = "ZM" + code
            if not isinstance(identifier, str) or not re.fullmatch(re.escape(expected_prefix) + r"-A(?:0[1-9]|1[0-9]|20)", identifier):
                errors.append(f"action {i}: invalid id")
        if identifier in ids:
            errors.append(f"action {i}: duplicate id")
        ids.add(identifier)
        if action.get("status") not in STATUSES:
            errors.append(f"action {i}: invalid status")
        for field in ("title_fa", "impact_fa"):
            if not isinstance(action.get(field), str) or not action[field].strip():
                errors.append(f"action {i}: missing {field}")
        url = action.get("evidence_url")
        if not isinstance(url, str) or (url and not EVIDENCE.fullmatch(url)):
            errors.append(f"action {i}: invalid evidence URL")
        if action.get("status") == "completed" and not url:
            errors.append(f"action {i}: completed without evidence")
        if action.get("status") != "completed" and url:
            errors.append(f"action {i}: incomplete action must have empty evidence")
    return errors

if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("usage: validate_zm_actions_receipt.py REPORT.md")
    failures = validate(Path(sys.argv[1]).read_text(encoding="utf-8"))
    for failure in failures:
        print(failure, file=sys.stderr)
    sys.exit(1 if failures else 0)
