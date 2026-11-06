#!/usr/bin/env python3
"""Redact the cPanel account-level StatsBar quota response.

The script runs on the ephemeral GitHub runner, never on cPanel, and does not
read environment variables, secrets, customer data, or application databases.
"""

import json
import re
import sys


ALLOWED_IDS = {"diskusage", "mysqldiskusage", "fileusage"}
METRIC_KEYS = ("usage", "maximum", "normalized", "percent", "percentused", "used", "limit")
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
    rows = raw if isinstance(raw, list) else []
    if isinstance(raw, dict):
        rows = [v for v in raw.values() if isinstance(v, dict)]
    metrics = {}
    for row in rows:
        if not isinstance(row, dict) or row.get("id") not in ALLOWED_IDS:
            continue
        metric = {}
        for key in METRIC_KEYS:
            if key in row:
                value = safe_scalar(row[key])
                if value is not None:
                    metric[key] = value
        metrics[row["id"]] = metric
    summary = {
        "api_success": payload.get("status") in (1, True),
        "metrics": metrics,
        "requested": sorted(ALLOWED_IDS),
        "full_backup_verified": False,
        "production_isolation_proven": False,
    }
    print("MPW_CPANEL_QUOTA_READONLY=" + json.dumps(summary, sort_keys=True))
    if not summary["api_success"] or "diskusage" not in metrics:
        print("MPW_QUOTA_ERROR=missing_disk_usage", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
