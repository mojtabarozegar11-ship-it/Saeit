"""Strict parsing for numbered ChatGPT management-cycle issue comments.

The repository owner may report actions, but a comment is *not* evidence of
bank settlement, deployment, or model attribution. Import as unreviewed.
"""
import re
from datetime import datetime, timezone

PUBLIC_ISSUE_API = (
    "https://api.github.com/repos/mojtabarozegar11-ship-it/Saeit/issues/1725/comments"
)
AUTHOR_LOGIN = "mojtabarozegar11-ship-it"
_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789")
_TITLE = re.compile(
    r"^##[ \t]*گزارش[ \t]+([0-9]{2})-([0-9]{4,8})[ \t]*\|[ \t]*"
    r"(20[0-9]{2}-[0-9]{2}-[0-9]{2}[ \t]+[0-9]{2}:[0-9]{2}[ \t]+UTC)"
    r"[ \t]*\|[ \t]*(?:(?:run_id[ \t]+)|(?:شناسه[ \t]+اجرا[ \t]*:[ \t]*))?([A-Za-z0-9_-]{8,128})[ \t]*$"
)
# Exact historical management receipts omitted by the earlier strict header parser.
# This is deliberately NOT an unrestricted alternative title grammar.
LEGACY_MANAGEMENT_RECOVERY = {
    "05-0041": (6594492539, "ZM-APP-GUARDED-RECONCILIATION"),
    "05-0042": (6594657783, "ZM-RECOVERABLE-APP-PROMOTION"),
    "05-0043": (6594791099, "ZM-ISOLATED-REAL-DATA-ACCEPTANCE"),
    "05-0044": (6594862748, "ZM-RELEASE-DEPENDENCY-GATE"),
}
_LEGACY_MANAGEMENT_TITLE = re.compile(
    r"^##[ \\t]*گزارش[ \\t]+اجرایی[ \\t]+(05)-([0-9]{4})[ \\t]+—[ \\t]+"
    r"([0-9]{1,2})[ \\t]+نوامبر[ \\t]+(2026)[ \\t]*\\|[ \\t]*([A-Za-z0-9_-]{8,128})$"
)



def extract_receipt(item):
    if not isinstance(item, dict) or not isinstance(item.get("user"), dict):
        return None
    if item["user"].get("login") != AUTHOR_LOGIN:
        return None
    comment_id = item.get("id")
    if type(comment_id) is not int or comment_id < 1:
        return None
    original = item.get("body")
    if not isinstance(original, str) or len(original) < 20 or len(original) > 8000:
        return None
    title_line = original.splitlines()[0].translate(_DIGITS)
    match = _TITLE.fullmatch(title_line)
    if match:
        cycle, number, when, run = match.groups()
        try:
            occurred_at = datetime.strptime(when, "%Y-%m-%d %H:%M UTC").replace(tzinfo=timezone.utc)
        except ValueError:
            return None
    else:
        legacy = _LEGACY_MANAGEMENT_TITLE.fullmatch(title_line)
        if not legacy:
            return None
        cycle, number, day, year, run = legacy.groups()
        code = f"{cycle}-{number}"
        if (day, year) != ("3", "2026") or LEGACY_MANAGEMENT_RECOVERY.get(code) != (comment_id, run):
            return None
        stamp = item.get("created_at")
        if not isinstance(stamp, str):
            return None
        try:
            occurred_at = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
        except ValueError:
            return None
        if occurred_at.tzinfo is None:
            return None
        occurred_at = occurred_at.astimezone(timezone.utc)
    report_code = f"{cycle}-{number}"
    return {
        "report_code": report_code,
        "cycle_code": cycle,
        "run_reference": run,
        "occurred_at": occurred_at,
        "title": f"گزارش چرخه {cycle} شماره {number}",
        "body": original,
        "evidence_url": (
            "https://github.com/mojtabarozegar11-ship-it/Saeit/issues/1725"
            f"#issuecomment-{comment_id}"
        ),
    }
