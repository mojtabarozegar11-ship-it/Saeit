#!/usr/bin/env python3
"""Bounded, read-only cPanel cron evidence for owner-authenticated relay.

Never logs cron lines, account paths, commands, credentials, or personal data.
A present cron entry is NOT proof that its worker executed successfully.
"""
import datetime as dt
import json
import re
import stat
from pathlib import Path
import os
import pwd
import subprocess

SITE_MARKER = "# zm-site-agents-only-v100"
ROBOT_MARKERS = (
    ("MPW_V91", "MPW_V91_MAIN_ONLY_20261018"),
    ("MPW_V11", "MPW_V11_MAIN_ONLY_SITE_HEALTH_20261018"),
    ("MPW_QUALITY", "MPW_ZOMOROD_QUALITY_REVIEW_MAIN_ONLY_20261018"),
    ("MPW_MANAGEMENT", "MPW_ZOMOROD_MANAGEMENT_INTELLIGENCE_MAIN_ONLY_20261018"),
    ("MPW_EVOLUTION", "MPW_PRIVATE_EVOLUTION_MAIN_ONLY_20261018"),
    ("MPW_MODULES", "MPW_77_MODULES_MAIN_ONLY_20261018"),
    ("MPW_MAIN_ROBOTS", "MPW_MAIN_PRIVATE_EXECUTION_ROBOTS_20261018"),
    ("MPW_EXTENDED_ROBOTS", "MPW_MAIN_EXTENDED_ROBOTS_20261018"),
)
MAX_CRON_CHARS = 131072
MANAGEMENT_MARKER = "ZM_CMD_SCAN_20261102"
MANAGEMENT_SCHEDULE = ("17", "*/6", "*", "*", "*")
MANAGEMENT_COMMAND = (
    "/usr/local/bin/php /home/zomorod2/.private/zomorod-business/"
    "command_scan_cli.php >> /home/zomorod2/.private/zomorod-business/"
    "command-scan-cron.log 2>&1"
)
MANAGEMENT_LOG = Path("/home/zomorod2/.private/zomorod-business/command-scan-cron.log")
LOG_TAIL_BYTES = 16384



def _management_cron_state(entries):
    marked = [line for line in entries if re.search(
        r"(?:^|\s)#\s*" + MANAGEMENT_MARKER + r"\s*$", line
    )]
    if not marked:
        return "ABSENT"
    if len(marked) != 1:
        return "DUPLICATE"
    fields = marked[0].split(maxsplit=5)
    if len(fields) != 6 or tuple(fields[:5]) != MANAGEMENT_SCHEDULE:
        return "SCHEDULE_MISMATCH"
    command = re.sub(r"\s+#\s*" + MANAGEMENT_MARKER + r"\s*$", "", fields[5])
    return ("CONFIGURED_ONCE" if " ".join(command.split()) == MANAGEMENT_COMMAND
            else "COMMAND_MISMATCH")


def _management_log_state():
    """Fresh structured output, never proof that the daemon initiated it."""
    now = dt.datetime.now().astimezone()
    due_candidates = [
        dt.datetime.combine(
            now.date() - dt.timedelta(days=days_back),
            dt.time(hour, 17), now.tzinfo,
        )
        for days_back in (0, 1) for hour in (18, 12, 6, 0)
    ]
    due = max(t for t in due_candidates if t <= now)
    try:
        meta = MANAGEMENT_LOG.lstat()
        if not stat.S_ISREG(meta.st_mode):
            return "NONREGULAR"
        descriptor = os.open(MANAGEMENT_LOG, os.O_RDONLY | os.O_NOFOLLOW)
        with os.fdopen(descriptor, "rb") as stream:
            current = os.fstat(stream.fileno())
            if not stat.S_ISREG(current.st_mode):
                return "NONREGULAR"
            if (current.st_dev, current.st_ino) != (meta.st_dev, meta.st_ino):
                return "CHANGED_DURING_READ"
            stamp = dt.datetime.fromtimestamp(current.st_mtime, now.tzinfo)
            if stamp > now + dt.timedelta(minutes=1):
                return "FUTURE_TIMESTAMP"
            if stamp < due:
                return "STALE"
            stream.seek(max(0, current.st_size - LOG_TAIL_BYTES))
            tail = stream.read(LOG_TAIL_BYTES)
    except FileNotFoundError:
        return "MISSING"
    except OSError:
        return "UNAVAILABLE"
    if not tail.endswith(b"\n"):
        return "PARTIAL_OR_EMPTY"
    nonempty = [line for line in tail.decode("utf-8", "replace").splitlines()
                if line.strip()]
    if not nonempty:
        return "PARTIAL_OR_EMPTY"
    try:
        last = json.loads(nonempty[-1])
    except (TypeError, ValueError):
        return "RECENT_UNCLASSIFIED"
    return ("RECENT_OK_OUTPUT" if isinstance(last, dict)
            and last.get("status") == "ok" else "RECENT_UNCLASSIFIED")


def summarize_cron(raw):
    if not isinstance(raw, str) or len(raw) > MAX_CRON_CHARS:
        return {"READBACK": "UNVERIFIED"}
    entries = tuple(
        line.strip() for line in raw.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    )
    result = {"READBACK": "OK", "ACTIVE_ENTRIES": str(min(len(entries), 10000))}
    result["MANAGEMENT_COMMAND_CRON"] = _management_cron_state(entries)
    result["MANAGEMENT_COMMAND_LOG"] = _management_log_state()
    result["MANAGEMENT_CRON_EXECUTION_PROVEN"] = "NO"
    result["MANAGEMENT_CRON_TIMEZONE_VERIFIED"] = "NO"
    site = [line for line in entries if SITE_MARKER in line]
    if not site:
        result["SITE_AGENTS_TEN_MINUTE"] = "ABSENT"
    elif len(site) > 1:
        result["SITE_AGENTS_TEN_MINUTE"] = "DUPLICATE"
    elif site[0].startswith("*/10 * * * * "):
        result["SITE_AGENTS_TEN_MINUTE"] = "SCHEDULED_MARKER_PRESENT"
    else:
        result["SITE_AGENTS_TEN_MINUTE"] = "SCHEDULE_MISMATCH"
    for label, marker in ROBOT_MARKERS:
        count = sum(marker in entry for entry in entries)
        result[label] = "PRESENT_ONCE" if count == 1 else ("ABSENT" if count == 0 else "DUPLICATE")
    result["WORKER_EXECUTION_PROVEN"] = "NO"
    result["PRIVATE_DURABLE_RECEIPT_PROVEN"] = "NO"
    return result


def main():
    if pwd.getpwuid(os.geteuid()).pw_name != "zomorod2":
        raise SystemExit("CPANEL_CRON_IDENTITY_REJECTED")
    try:
        proc = subprocess.run(
            ["crontab", "-l"], capture_output=True, text=True,
            timeout=15, check=False,
        )
    except (OSError, subprocess.TimeoutExpired, UnicodeError):
        summary = {"READBACK": "UNAVAILABLE"}
    else:
        summary = (
            summarize_cron(proc.stdout)
            if proc.returncode == 0 else {"READBACK": "UNAVAILABLE"}
        )
    for key, value in summary.items():
        print("CPANEL_CRON_" + key + "=" + value)


if __name__ == "__main__":
    main()
