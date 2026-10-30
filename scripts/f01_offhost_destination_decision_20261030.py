#!/usr/bin/env python3
"""Fail-closed, offline F-01 sizing of an existing backup vs account-specific quota.
Never authorizes a transfer, restart, cleanup, deployment, or worker launch.
A self-asserted JSON quota record is NOT independent provider attestation.
"""
import argparse
import datetime as dt
import json
import sys

UTC = dt.timezone.utc
EXTRA_RESERVE_BYTES = 1024 ** 3

def _utc(value):
    if not isinstance(value, str):
        return None
    try:
        parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed.astimezone(UTC) if parsed.tzinfo else None
    except ValueError:
        return None

def _int(value):
    return type(value) is int and value >= 0

def assess(source, destination=None, now=None):
    now = now or dt.datetime.now(UTC)
    reasons = []
    source = source if isinstance(source, dict) else {}
    dest = destination if isinstance(destination, dict) else {}
    stamp = _utc(source.get("observed_utc"))
    if (source.get("schema") != "f01-backup-source-inventory.v1"
            or source.get("status") != "INSPECT_ONLY"
            or source.get("read_only") is not True
            or source.get("truncated") is not False):
        reasons.append("SOURCE_INVENTORY_UNTRUSTED_OR_INCOMPLETE")
    if stamp is None or not 0 <= (now - stamp).total_seconds() <= 1800:
        reasons.append("SOURCE_INVENTORY_NOT_FRESH")
    entries = source.get("newest_three_metadata_only")
    entries = entries if isinstance(entries, list) else []
    valid = []
    for item in entries:
        if not isinstance(item, dict):
            continue
        size, date = item.get("bytes"), _utc(item.get("mtime_utc"))
        if _int(size) and 100 <= size <= 8 * 1024 ** 3 and date and date <= now:
            valid.append((size, date))
    if not valid:
        reasons.append("NO_VALID_EXISTING_SNAPSHOT_METADATA")
        latest_size = latest_age = minimum_free = None
    else:
        latest_size, latest_date = max(valid, key=lambda p: p[1])
        latest_age = round((now - latest_date).total_seconds() / 3600, 2)
        if latest_age > 24:
            reasons.append("SNAPSHOT_OLDER_THAN_24_HOURS")
        minimum_free = latest_size * 2 + EXTRA_RESERVE_BYTES
    for flag, reason in (
        ("database_consistency_verified", "DATABASE_CONSISTENCY_NOT_VERIFIED"),
        ("offhost_backup_exists_verified", "OFFHOST_BACKUP_NOT_VERIFIED"),
        ("restore_verified", "ISOLATED_RESTORE_NOT_VERIFIED"),
    ):
        if source.get(flag) is not True:
            reasons.append(reason)
    free = dest.get("account_free_bytes")
    dst_time = _utc(dest.get("observed_utc"))
    quota_verified = (
        dest.get("account_quota_evidence") == "INDEPENDENTLY_VERIFIED"
        and dest.get("same_destination_account") is True
        and dst_time is not None
        and 0 <= (now - dst_time).total_seconds() <= 1800
        and _int(free)
    )
    if not quota_verified:
        reasons.append("ACCOUNT_QUOTA_NOT_INDEPENDENTLY_VERIFIED")
        free = None
    elif minimum_free is not None and free < minimum_free:
        reasons.append("ACCOUNT_FREE_BELOW_SNAPSHOT_PLUS_RESERVE")
    critical = {
        "SOURCE_INVENTORY_UNTRUSTED_OR_INCOMPLETE",
        "SOURCE_INVENTORY_NOT_FRESH",
        "NO_VALID_EXISTING_SNAPSHOT_METADATA",
        "SNAPSHOT_OLDER_THAN_24_HOURS",
        "ACCOUNT_QUOTA_NOT_INDEPENDENTLY_VERIFIED",
        "ACCOUNT_FREE_BELOW_SNAPSHOT_PLUS_RESERVE",
    }
    sizing = (minimum_free is not None and free is not None
              and free >= minimum_free and not critical.intersection(reasons))
    return {
        "schema": "f01-offhost-destination-decision.v1",
        "status": "CAPACITY_CANDIDATE_ONLY" if sizing else "BLOCKED",
        "latest_snapshot_bytes": latest_size,
        "latest_snapshot_age_hours": latest_age,
        "minimum_account_free_bytes_for_one_snapshot_and_rehearsal": minimum_free,
        "verified_account_free_bytes": free,
        "capacity_sizing_passed": sizing,
        "reasons": sorted(set(reasons)),
        "transfer_authorized": False,
        "reboot_authorized": False,
        "backup_verified": False,
        "restore_verified": False,
        "live_worker_verified": False,
    }

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source-inventory", required=True)
    p.add_argument("--account-quota-evidence")
    args = p.parse_args()
    try:
        with open(args.source_inventory, encoding="utf-8") as handle:
            source = json.load(handle)
        if args.account_quota_evidence:
            with open(args.account_quota_evidence, encoding="utf-8") as handle:
                dest = json.load(handle)
        else:
            dest = None
    except (OSError, ValueError):
        source, dest = {}, None
    result = assess(source, dest)
    print(json.dumps(result, sort_keys=True))
    return 0 if result["status"] == "CAPACITY_CANDIDATE_ONLY" else 2

if __name__ == "__main__":
    sys.exit(main())
