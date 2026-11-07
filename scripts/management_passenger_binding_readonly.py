#!/usr/bin/env python3
"""Redact a cPanel Passenger UAPI response for management release gates.

The only input is JSON from ``PassengerApps list_applications``; no production
filesystem, environment, database or code is accessed by this processor.
"""
from __future__ import annotations

import json
import re
import sys


TARGET_DOMAINS = {"zomorodmelal.ir", "www.zomorodmelal.ir"}
EXPECTED_MAIN_ROOT = "/home/zomorod2/Saeit"


def _entries(node):
    if isinstance(node, dict):
        if any(key in node for key in (
            "app_root", "app_path", "application_root",
            "base_uri", "app_uri", "application_uri",
        )):
            yield node
        for value in node.values():
            yield from _entries(value)
    elif isinstance(node, list):
        for value in node:
            yield from _entries(value)


def _root_class(value):
    # Never assume an unverified relative path or a trailing /.. is the same
    # as the absolute, currently observed source directory.
    if value == EXPECTED_MAIN_ROOT or value == EXPECTED_MAIN_ROOT + "/":
        return "exact_main_root"
    if value in ("Saeit", "Saeit/"):
        return "relative_saeit_unverified"
    if "saeit-staging" in value.lower():
        return "staging_root"
    return "other_or_unverified_root"


def sanitize(raw):
    if not isinstance(raw, dict):
        raise ValueError("Expected a UAPI JSON object")
    result = raw.get("result")
    if isinstance(result, dict) and result.get("status") in (0, False, "0"):
        raise ValueError("UAPI reported failure")

    found = []
    dedupe = set()
    for app in _entries(raw.get("result", raw)):
        domain = str(app.get("domain") or "").strip().lower()
        root = str(app.get("app_root") or app.get("app_path") or app.get("application_root") or app.get("path") or "").strip()
        if not domain or not root:
            continue
        uri = str(app.get("base_uri") or app.get("app_uri") or app.get("application_uri") or "/")
        key = (domain, root, uri)
        if key in dedupe:
            continue
        dedupe.add(key)
        if domain not in TARGET_DOMAINS:
            continue
        claimed_python = str(app.get("python_version") or app.get("runtime_version") or "")
        if not re.fullmatch(r"3\.(?:[0-9]|1[0-9])(?:\.\d+)?", claimed_python):
            claimed_python = "not_declared"
        found.append({
            "domain": domain,
            "app_root_class": _root_class(root),
            "declared_python_version": claimed_python,
            # URI strings can include sensitive/rewrite-only subsite paths.
            "root_uri_mapping": "root" if uri == "/" else "non_root_unverified",
        })

    exact = sum(x["app_root_class"] == "exact_main_root" for x in found)
    return {
        "classification": "READ_ONLY_MANAGEMENT_PASSENGER_BINDING",
        "uapi_records_discovered": len(dedupe),
        "target_domain_mapping_count": len(found),
        "target_domain_mappings": found,
        "exact_source_root_mapping_present": exact > 0,
        # This UAPI alone never attests the *running* interpreter, current
        # source revision, production isolation or recoverable backup.
        "active_interpreter_attested": False,
        "source_runtime_match_attested": False,
        "production_isolation_proven": False,
        "recoverable_backups_verified": False,
        "release_permitted": False,
        "raw_application_paths_or_secrets_emitted": False,
    }


def main():
    try:
        data = sanitize(json.load(sys.stdin))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"classification": "PASSENGER_BINDING_FAILED", "error_type": type(exc).__name__, "release_permitted": False}))
        raise SystemExit(2) from None
    print(json.dumps(data, sort_keys=True, ensure_ascii=False))


if __name__ == "__main__":
    main()
