#!/usr/bin/env python3
"""Redact cPanel's single-domain docroot metadata for PR #2127.

The source is a read-only UAPI `DomainInfo single_domain_data` result.
No paths, credentials, other domains or raw UAPI content are logged.
"""
from __future__ import annotations

import json
import sys


EXPECTED_DOMAIN = "zomorodmelal.ir"
EXPECTED_DOCUMENT_ROOT = "/home/zomorod2/public_html"


def _entries(node):
    if isinstance(node, dict):
        if "domain" in node and any(
            key in node for key in ("documentroot", "document_root", "docroot")
        ):
            yield node
        for value in node.values():
            yield from _entries(value)
    elif isinstance(node, list):
        for value in node:
            yield from _entries(value)


def sanitize(raw):
    if not isinstance(raw, dict):
        raise ValueError("Expected a UAPI JSON object")
    result = raw.get("result")
    if not isinstance(result, dict) or result.get("status") in (0, False, "0"):
        raise ValueError("UAPI failed or has no status object")

    roots = []
    for entry in _entries(result.get("data", result)):
        if str(entry.get("domain") or "").strip().lower() != EXPECTED_DOMAIN:
            continue
        root = str(
            entry.get("documentroot") or entry.get("document_root")
            or entry.get("docroot") or ""
        ).strip()
        if root:
            roots.append(root)

    unique = set(roots)
    if len(unique) == 1:
        root = next(iter(unique)).rstrip("/")
        root_class = (
            "expected_public_html" if root == EXPECTED_DOCUMENT_ROOT
            else "other_unverified"
        )
    elif not unique:
        root_class = "not_reported"
    else:
        root_class = "ambiguous"

    return {
        "classification": "READ_ONLY_MANAGEMENT_DOMAIN_DOCROOT",
        "target_domain": EXPECTED_DOMAIN,
        "target_domain_records": len(roots),
        "document_root_class": root_class,
        "expected_public_html_attested": root_class == "expected_public_html",
        "active_python_interpreter_attested": False,
        "release_permitted": False,
        "raw_paths_or_secrets_emitted": False,
    }


def main():
    try:
        data = sanitize(json.load(sys.stdin))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({
            "classification": "DOMAIN_DOCROOT_FAILED",
            "error_type": type(exc).__name__,
            "release_permitted": False,
        }))
        raise SystemExit(2) from None
    print(json.dumps(data, sort_keys=True, ensure_ascii=False))


if __name__ == "__main__":
    main()
