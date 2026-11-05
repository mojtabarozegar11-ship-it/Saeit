"""Validate non-sensitive ZM_ACTIONS_V1 receipts before importing them.

Use from trusted report intake before any write.
No network, database writes, or external dependencies.
"""
import json
import re
from datetime import datetime

START = "ZM_ACTIONS_V1_START"
END = "ZM_ACTIONS_V1_END"
# Keep the same accepted first-line shape as github_chatgpt_reports._TITLE.
# The parser normalizes Persian digits; both ASCII and Persian digits are valid.
DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789")
REPORT = re.compile(
    r"^##[ \t]*گزارش[ \t]+([0-9]{2})-([0-9]{4,8})[ \t]*\|[ \t]*"
    r"(20[0-9]{2}-[0-9]{2}-[0-9]{2}[ \t]+[0-9]{2}:[0-9]{2}[ \t]+UTC)"
    r"[ \t]*\|[ \t]*([A-Za-z0-9_-]{8,128})[ \t]*$"
)
EVIDENCE = re.compile(r"^https://github\.com/mojtabarozegar11-ship-it/Saeit/(?:commit/[0-9a-f]{40}|actions/runs/[0-9]+|pull/[0-9]+|issues/[0-9]+)$")
STATUSES = {"completed", "partial", "blocked", "not_started"}
LEGACY_CYCLE_05_MAX = 57


def validate_for_import(report_code: str, document: str) -> list[str]:
    """Fail closed for new cycle-05 reports, while preserving audited legacy.

    The canonical management issue contains 05-0001..05-0057. Several old
    reports predate the structured schema, so retroactive rejection would
    make an existing read-only import unusable. Other cycles are unaffected.
    """
    if not isinstance(report_code, str) or not re.fullmatch(r"05-[0-9]{4,}", report_code):
        return []
    if int(report_code.split("-", 1)[1]) <= LEGACY_CYCLE_05_MAX:
        return []
    return validate(document, expected_report_code=report_code)

def validate(document: str, historical_ids=None, expected_report_code=None) -> list[str]:
    """Validate a receipt; historical_ids must come from a trusted complete index.

    The caller must supply the existing IDs when enforcing cross-report uniqueness.
    This function never reads or modifies the financial database.
    """
    errors = []
    if document.count(START) != 1 or document.count(END) != 1:
        return ["expected exactly one receipt block"]
    header_line = document.splitlines()[0].translate(DIGITS) if document else ""
    header = REPORT.fullmatch(header_line)
    if header:
        try:
            datetime.strptime(header.group(3), "%Y-%m-%d %H:%M UTC")
        except ValueError:
            errors.append("invalid report UTC timestamp")
    if not header:
        errors.append("missing canonical report header")
    if document.index(START) >= document.index(END):
        return errors + ["receipt markers are reversed"]
    try:
        payload = json.loads(document.split(START, 1)[1].split(END, 1)[0].strip())
    except (ValueError, IndexError):
        return errors + ["invalid JSON receipt"]
    if not isinstance(payload, dict):
        return errors + ["receipt must be a JSON object"]
    if payload.get("version") != 1:
        errors.append("invalid receipt version")
    code = payload.get("report_code")
    if header:
        if code != header.group(1) + "-" + header.group(2):
            errors.append("report code does not match header")
    if expected_report_code is not None and code != expected_report_code:
        errors.append("report code does not match extracted receipt")
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
        expected_prefix = "ZM" + code
        if not isinstance(identifier, str) or not re.fullmatch(re.escape(expected_prefix) + r"-A(?:0[1-9]|1[0-9]|20)", identifier):
            errors.append(f"action {i}: invalid id")
        if isinstance(identifier, str):
            if identifier in ids:
                errors.append(f"action {i}: duplicate id")
            if historical_ids is not None and identifier in historical_ids:
                errors.append(f"action {i}: id already exists in history")
            ids.add(identifier)
        if not isinstance(action.get("status"), str) or action["status"] not in STATUSES:
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

