#!/usr/bin/env python3
"""S-01 offline checkout preimage SHA reconciliation; no site or factory access.

Run against an authorized local COPY of the cPanel checkout source. This tool
does not connect to a host, create a backup, read customers, or approve release.
A hash match proves only byte identity, never Passenger DB or paid delivery.
"""
import argparse
import hashlib
import json
import re
from pathlib import Path

from scripts.s01_checkout_invoice_static_readonly_20261029 import read_regular

CHECKOUT_REL = "mpw_commerce/product_checkout_page.py"


def assess(root, expected_sha256):
    if not isinstance(expected_sha256, str) or not re.fullmatch(r"[0-9a-f]{64}", expected_sha256):
        raise ValueError("expected SHA-256 must be 64 lowercase hex characters")
    data = read_regular(Path(root), CHECKOUT_REL)
    observed = hashlib.sha256(data).hexdigest()
    return {
        "scope": "S01_OFFLINE_CHECKOUT_PREIMAGE_SHA_ONLY",
        "status": "MATCH" if observed == expected_sha256 else "SOURCE_SHA_DRIFT",
        "expected_sha256": expected_sha256,
        "observed_sha256": observed,
        "source_bytes": len(data),
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
    args = parser.parse_args(argv)
    try:
        result = assess(args.root, args.expected)
    except (OSError, RuntimeError, ValueError):
        print(json.dumps({"scope": "S01_OFFLINE_CHECKOUT_PREIMAGE_SHA_ONLY",
                          "status": "BLOCKED_SOURCE_UNREADABLE_OR_INVALID",
                          "release_permitted": False}, sort_keys=True))
        return 3
    print(json.dumps(result, sort_keys=True))
    return 0 if result["status"] == "MATCH" else 2


if __name__ == "__main__":
    raise SystemExit(main())
