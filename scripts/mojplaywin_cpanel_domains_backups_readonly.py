#!/usr/bin/env python3
"""Sanitize read-only UAPI DomainInfo list_domains / Backup list_backups.

Runs on a GitHub runner; consumes stdin. Raw cPanel user/domain/backup filenames,
other hosted domain names, home paths and sensitive metadata are NEVER printed.
No backup creation, restore, payment or host file access.
"""
from __future__ import annotations

import argparse
import json
import sys

MAIN = {"mojplaywin.com", "www.mojplaywin.com"}


def unwrap(doc: dict):
    if not isinstance(doc, dict):
        raise ValueError("UAPI root not object")
    result = doc.get("result")
    if not isinstance(result, dict) or result.get("status") not in (1, "1", True):
        raise ValueError("UAPI failure or missing status")
    return result.get("data")


def summary_domains(doc: dict) -> dict:
    data = unwrap(doc)
    if not isinstance(data, dict):
        raise ValueError("DomainInfo did not return an object")
    domain_sets = {}
    for category in ("addon_domains", "parked_domains", "sub_domains"):
        entries = data.get(category)
        if entries is None:
            domain_sets[category] = None
        elif isinstance(entries, list):
            domain_sets[category] = len(entries)
        else:
            raise ValueError("unexpected domain array type")
    named = []
    for category in ("addon_domains", "parked_domains", "sub_domains"):
        listed = data.get(category) or []
        named.extend(str(item).lower().strip() for item in listed if isinstance(item, str))
    if isinstance(data.get("main_domain"), str):
        named.append(data["main_domain"].lower().strip())
    return {
        "classification": "READ_ONLY_CPANEL_DOMAINS",
        "api_response_valid": True,
        "main_mojplaywin_domain_listed": "mojplaywin.com" in named,
        "mojplaywin_subdomain_count": sum(v.endswith(".mojplaywin.com") for v in named),
        "domain_type_counts": domain_sets,
        "unknown_domains_not_disclosed": True,
        "path_based_child_sites_not_enumerated": True,
        "release_permitted": False,
    }


def summary_backups(doc: dict) -> dict:
    data = unwrap(doc)
    if isinstance(data, list):
        entries = data
    elif isinstance(data, dict):
        found = [v for v in data.values() if isinstance(v, list)]
        # An unrecognized structure is not evidence of zero backups.
        if not found:
            raise ValueError("unrecognized backup list response")
        entries = [item for group in found for item in group]
    else:
        raise ValueError("unrecognized backup list response")
    known_statuses = {"complete": 0, "pending": 0, "other_or_unreported": 0}
    for entry in entries:
        status = str(entry.get("status", "")).lower().strip() if isinstance(entry, dict) else ""
        if status == "complete":
            known_statuses["complete"] += 1
        elif status in ("pending", "in_progress", "running", "processing"):
            known_statuses["pending"] += 1
        else:
            known_statuses["other_or_unreported"] += 1
    return {
        "classification": "READ_ONLY_CPANEL_BACKUP_LIST",
        "api_response_valid": True,
        "api_list_entry_count": len(entries),
        "reported_status_counts": known_statuses,
        "backup_location_or_scope_verified": False,
        "full_database_and_media_backup_verified": False,
        "restore_test_verified": False,
        "api_can_omit_offsite_or_nonstandard_backups": True,
        "release_permitted": False,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--kind", choices=("domains", "backups"), required=True)
    args = parser.parse_args()
    try:
        doc = json.load(sys.stdin)
        result = summary_domains(doc) if args.kind == "domains" else summary_backups(doc)
    except (ValueError, TypeError, OSError, json.JSONDecodeError) as exc:
        print(json.dumps({"classification":"READ_ONLY_UAPI_METADATA_ERROR",
                          "kind":args.kind,"error_type":type(exc).__name__,
                          "release_permitted":False}))
        raise SystemExit(2) from None
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
