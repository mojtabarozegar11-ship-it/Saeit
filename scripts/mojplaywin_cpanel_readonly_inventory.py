#!/usr/bin/env python3
"""Sanitize READ-ONLY cPanel Passenger app inventory.

Reads ONLY the result of `uapi --output=json PassengerApps list_applications`
from stdin on a GitHub runner. Does not read or write databases, web pages,
server credentials, or filesystem files and NEVER authorizes publication.
"""
from __future__ import annotations

import hashlib
import json
import sys

TARGET_DOMAINS = {"mojplaywin.com", "www.mojplaywin.com"}
KNOWN_PROTECTED_PREFIXES = (
    "/mojtaba.roozegar/", "/picm/", "/studio.Roham/", "/saman/",
    "/zahra$$/", "/farnaz/", "/taniya/",
)
SHARED_MARKER = "saeit-staging"


def walk_apps(node):
    if isinstance(node, dict):
        if any(k in node for k in ("app_root", "app_path", "application_root", "base_uri", "app_uri", "application_uri")):
            yield node
        for value in node.values():
            yield from walk_apps(value)
    elif isinstance(node, list):
        for value in node:
            yield from walk_apps(value)


def sanitize(raw):
    if not isinstance(raw, dict):
        raise ValueError("UAPI root must be an object")
    result = raw.get("result")
    if isinstance(result, dict) and result.get("status") in (0, False, "0"):
        raise ValueError("cPanel UAPI explicitly reports failure")
    apps = []
    seen = set()
    for entry in walk_apps(raw.get("result", raw)):
        domain = str(entry.get("domain") or "").lower().strip()
        uri = str(entry.get("base_uri") or entry.get("app_uri") or entry.get("application_uri") or "/").strip()
        app_root = str(entry.get("app_root") or entry.get("app_path") or entry.get("application_root") or entry.get("path") or "")
        if not domain or not app_root:
            continue
        key = (domain, uri, app_root)
        if key in seen:
            continue
        seen.add(key)
        apps.append({"domain": domain, "uri": uri, "root": app_root})
    main = [x for x in apps if x["domain"] in TARGET_DOMAINS]
    mappings = []
    for x in sorted(main, key=lambda z: (z["domain"], z["uri"])):
        root_hash = hashlib.sha256(x["root"].encode("utf-8")).hexdigest()[:16]
        mappings.append({
            "domain": x["domain"],
            "base_uri": (x["uri"] if x["uri"].rstrip("/") + "/" in ("/", *KNOWN_PROTECTED_PREFIXES) else "(unlisted-path-" + hashlib.sha256(x["uri"].encode("utf-8")).hexdigest()[:12] + ")") if x["uri"].startswith("/") else "(invalid)",
            "app_root_fingerprint": root_hash,
            "references_shared_saeit_staging": SHARED_MARKER in x["root"].lower(),
        })
    main_paths = [x["base_uri"].rstrip("/") + "/" for x in mappings]
    return {
        "classification": "READ_ONLY_PASSENGER_INVENTORY",
        "uapi_records_discovered": len(apps),
        "mojplaywin_passenger_mappings": mappings,
        "other_domain_mapping_count": len(apps) - len(main),
        "known_independent_prefixes": list(KNOWN_PROTECTED_PREFIXES),
        "known_independent_prefixes_with_explicit_passenger_mapping": [
            prefix for prefix in KNOWN_PROTECTED_PREFIXES if prefix in main_paths
        ],
        "important_limitation": "UAPI Passenger application mappings cannot enumerate Django route-only or rewrite-served subsites; full route and cPanel document-root audit remains required",
        "production_isolation_proven": False,
        "recoverable_backups_verified": False,
        "release_permitted": False,
        "secrets_or_full_app_root_paths_printed": False,
    }


def main():
    try:
        result = sanitize(json.load(sys.stdin))
    except (json.JSONDecodeError, OSError, ValueError) as exc:
        print(json.dumps({"classification": "UAPI_INVENTORY_FAILED", "error_type": type(exc).__name__, "release_permitted": False}))
        raise SystemExit(2) from None
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
