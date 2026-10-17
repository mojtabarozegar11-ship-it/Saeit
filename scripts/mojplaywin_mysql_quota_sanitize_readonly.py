#!/usr/bin/env python3
"""Sanitize read-only cPanel MySQL names and quota data before CI output.

Accepts UAPI JSON on stdin, NEVER prints DB names/users/credentials or raw API
messages. Fails closed on unsuccessful UAPI response. No server writes.
"""
import json
import sys


def safe_number(value):
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return max(0, int(value))
    if isinstance(value, str) and value.isdigit():
        return int(value)
    return None


def sanitize(payload, kind):
    envelope = payload.get("result") if isinstance(payload, dict) else None
    good = isinstance(envelope, dict) and envelope.get("status") in (1, "1")
    data = envelope.get("data") if good else None
    base = {"classification": "READ_ONLY_CPANEL_"+kind.upper(),
            "uapi_succeeded": good, "backup_created": False,
            "database_contents_read": False, "release_permitted": False}
    if kind == "mysql":
        databases = data if isinstance(data, list) else (
            data.get("databases") if isinstance(data, dict) else None)
        databases = databases if isinstance(databases, list) else []
        sizes = [safe_number(x.get("disk_usage")) for x in databases if isinstance(x, dict)]
        base.update({
            "database_count": len(databases),
            "all_sizes_reported": len(sizes) == len(databases) and all(x is not None for x in sizes),
            "reported_database_bytes_total": sum(x for x in sizes if x is not None),
            "names_users_and_passwords_redacted": True,
        })
    elif kind == "quota":
        if not isinstance(data, dict):
            data = {}
        base.update({
            "local_account_bytes_used": safe_number(data.get("bytes_used")) or safe_number(data.get("disk_used")),
            "local_account_bytes_limit": safe_number(data.get("byte_limit")) or safe_number(data.get("disk_limit")),
            "quota_shape_parsed": bool(data),
        })
    else:
        raise ValueError("unsupported sanitizer")
    return base


if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in ("mysql", "quota"):
        raise SystemExit("supported: mysql, quota")
    try:
        obj = json.load(sys.stdin)
        result = sanitize(obj, sys.argv[1])
    except Exception:
        print(json.dumps({"classification": "READ_ONLY_CPANEL_PREFLIGHT_ERROR",
                          "uapi_succeeded": False, "backup_created": False,
                          "release_permitted": False}))
        raise SystemExit(1)
    print(json.dumps(result, sort_keys=True))
    if not result["uapi_succeeded"]:
        raise SystemExit(1)
