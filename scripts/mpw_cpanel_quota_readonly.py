#!/usr/bin/env python3
"""Redact the cPanel account-level Quota.get_quota_info response.

The script runs on the ephemeral GitHub runner, never on cPanel, and does not
read environment variables, secrets, customer data, or application databases.
"""

import json
import re
import sys


QUOTA_KEYS = (
    "megabyte_limit",
    "megabytes_used",
    "megabytes_remain",
    "under_megabyte_limit",
    "under_backup_threshold",
    "under_quota_overall",
    "backup_warning_threshold_pct",
    "inodes_used",
    "inode_limit",
    "under_inode_limit",
)
SAFE_TEXT = re.compile(r"^[A-Za-z0-9 .,%/+-]{1,64}$")


def safe_scalar(value):
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return value if abs(value) < 10**18 else None
    if isinstance(value, str) and SAFE_TEXT.fullmatch(value):
        return value
    return None


def main():
    # A bounded read only of the remote API's *stdout*; no raw response printed.
    data = sys.stdin.buffer.read(262145)
    if len(data) > 262144:
        print("MPW_QUOTA_ERROR=response_too_large", file=sys.stderr)
        return 1
    try:
        payload = json.loads(data)
    except (ValueError, UnicodeDecodeError):
        print("MPW_QUOTA_ERROR=invalid_json", file=sys.stderr)
        return 1
    if not isinstance(payload, dict) or payload.get("status") in (0, False):
        print("MPW_QUOTA_ERROR=api_failed", file=sys.stderr)
        return 1
    raw = payload.get("data")
    metrics = {}
    if isinstance(raw, dict):
        for key in QUOTA_KEYS:
            value = safe_scalar(raw.get(key))
            if value is not None:
                metrics[key] = value
    summary = {
        "api_success": payload.get("status") in (1, True),
        "metrics": metrics,
        "requested": "Quota.get_quota_info",
        "full_backup_verified": False,
        "production_isolation_proven": False,
    }
    print("MPW_CPANEL_QUOTA_READONLY=" + json.dumps(summary, sort_keys=True))
    if not summary["api_success"] or not all(
        field in metrics for field in ("megabyte_limit", "megabytes_used", "megabytes_remain")
    ):
        print("MPW_QUOTA_ERROR=missing_quota_values", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
