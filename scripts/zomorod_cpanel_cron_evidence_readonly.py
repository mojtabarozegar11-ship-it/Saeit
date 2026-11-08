#!/usr/bin/env python3
"""Bounded, read-only cPanel cron evidence for owner-authenticated relay.

Never logs cron lines, account paths, commands, credentials, or personal data.
A present cron entry is NOT proof that its worker executed successfully.
"""
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


def summarize_cron(raw):
    if not isinstance(raw, str) or len(raw) > MAX_CRON_CHARS:
        return {"READBACK": "UNVERIFIED"}
    entries = tuple(
        line.strip() for line in raw.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    )
    result = {"READBACK": "OK", "ACTIVE_ENTRIES": str(min(len(entries), 10000))}
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
