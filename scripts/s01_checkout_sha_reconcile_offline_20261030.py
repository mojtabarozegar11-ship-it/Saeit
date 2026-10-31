#!/usr/bin/env python3
"""S-01 offline checkout preimage SHA reconciliation; no site or factory access.

Run against an authorized local COPY of the cPanel checkout source. This tool
does not connect to a host, create a backup, read customers, or approve release.
A hash match proves only byte identity, never Passenger DB or paid delivery.
"""
import argparse
import ast
import hashlib
import json
import re
from pathlib import Path

from scripts.s01_checkout_invoice_static_readonly_20261029 import read_regular

CHECKOUT_REL = "mpw_commerce/product_checkout_page.py"


def python_ast_digest(data):
    """Hash normalized Python syntax without executing or exposing source."""
    try:
        tree = ast.parse(data)
    except (SyntaxError, UnicodeError, ValueError):
        return None
    return hashlib.sha256(ast.dump(tree, include_attributes=False).encode("utf-8")).hexdigest()


def assess(root, expected_sha256, approved_root=None):
    if not isinstance(expected_sha256, str) or not re.fullmatch(r"[0-9a-f]{64}", expected_sha256):
        raise ValueError("expected SHA-256 must be 64 lowercase hex characters")
    # Optional approved reference must itself match the release pin. An
    # unverified comparison copy cannot legitimize a changed cPanel file.
    approved_sha = None
    approved_data = None
    if approved_root is not None:
        approved_data = read_regular(Path(approved_root), CHECKOUT_REL)
        approved_sha = hashlib.sha256(approved_data).hexdigest()
    data = read_regular(Path(root), CHECKOUT_REL)
    observed = hashlib.sha256(data).hexdigest()
    approved_valid = approved_sha is None or approved_sha == expected_sha256
    observed_ast = python_ast_digest(data)
    approved_ast = python_ast_digest(approved_data) if approved_data is not None else None
    # Compare bytes ONLY when the separate approved reference matches the
    # pre-existing pin. This never repins a changed production source and
    # never prints source content, credentials, excerpts or a unified diff.
    comparison = None
    if approved_data is not None and approved_valid:
        offset = next((i for i, (a, b) in enumerate(zip(approved_data, data))
                       if a != b), min(len(approved_data), len(data)))
        identical = approved_data == data
        comparison = {
            "byte_identical": identical,
            "first_difference_offset": None if identical else offset,
            "approved_source_bytes": len(approved_data),
            # Semantic equivalence is diagnostic ONLY; it never authorizes
            # repinning a changed source, bypassing backup or deployment.
            "python_ast_equivalent": (
                approved_ast == observed_ast
                if approved_ast is not None and observed_ast is not None else None
            ),
            "difference_kind": ("IDENTICAL" if identical else
                                "APPROVED_PREFIX" if offset == len(approved_data) else
                                "OBSERVED_PREFIX" if offset == len(data) else
                                "BYTE_MISMATCH"),
        }
    return {
        "scope": "S01_OFFLINE_CHECKOUT_PREIMAGE_SHA_ONLY",
        "status": ("APPROVED_COPY_SHA_MISMATCH" if not approved_valid else
                   "MATCH" if observed == expected_sha256 else "SOURCE_SHA_DRIFT"),
        "approved_copy_verified": approved_sha == expected_sha256 if approved_sha else False,
        "approved_sha256": approved_sha,
        "approved_reference_comparison": comparison,
        "expected_sha256": expected_sha256,
        "observed_sha256": observed,
        "source_bytes": len(data),
        "observed_python_syntax_valid": observed_ast is not None,
        "approved_python_syntax_valid": (
            approved_ast is not None if approved_data is not None else None
        ),
        "source_modified": False,
        "backup_created": False,
        "offhost_restore_verified": False,
        "passenger_db_authority_verified": False,
        "paid_delivery_verified": False,
        "release_permitted": False,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, help="local authorized checkout source COPY root")
    parser.add_argument("--expected", required=True, help="pinned SHA-256 from approved release record")
    parser.add_argument("--approved-root", help="optional authorized local approved source COPY root")
    args = parser.parse_args(argv)
    try:
        result = assess(args.root, args.expected, approved_root=args.approved_root)
    except (OSError, RuntimeError, ValueError):
        print(json.dumps({"scope": "S01_OFFLINE_CHECKOUT_PREIMAGE_SHA_ONLY",
                          "status": "BLOCKED_SOURCE_UNREADABLE_OR_INVALID",
                          "release_permitted": False}, sort_keys=True))
        return 3
    print(json.dumps(result, sort_keys=True))
    return 0 if result["status"] == "MATCH" else 3 if result["status"] == "APPROVED_COPY_SHA_MISMATCH" else 2


if __name__ == "__main__":
    raise SystemExit(main())
