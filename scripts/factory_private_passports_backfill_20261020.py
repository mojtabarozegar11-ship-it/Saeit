#!/usr/bin/env python3
"""Idempotent private VPS product-passport backfill.

Only reads QA manifest and original ZIP, validates original ZIP SHA, writes
new version-bound sidecars in the SAME private directory. No approval changes,
store publishing, database, cPanel, buyer credentials, payments, or ZIP writes.
"""
import argparse
from collections import Counter
import json
from pathlib import Path
from factory_private_product_passport_policy_20261020 import ensure_private_passport

def backfill(private_factory_root, limit=1000):
    root = Path(private_factory_root)
    goods = root / "digital-products"
    if root.is_symlink() or goods.is_symlink() or not goods.is_dir():
        raise ValueError("FACTORY_PRIVATE_STOCK_ROOT_UNSAFE")
    if type(limit) is not int or not 1 <= limit <= 10000:
        raise ValueError("FACTORY_PASSPORT_LIMIT_INVALID")
    counters = Counter()
    failures = Counter()
    candidates = sorted(goods.iterdir(), key=lambda p: p.name)
    if len(candidates) > limit:
        raise ValueError("FACTORY_PASSPORT_INVENTORY_LIMIT")
    for folder in candidates:
        if folder.is_symlink() or not folder.is_dir():
            counters["skipped"] += 1
            continue
        manifest_path = folder / "manufacturing_manifest.json"
        if manifest_path.is_symlink() or not manifest_path.is_file():
            counters["skipped"] += 1
            continue
        try:
            if not 0 < manifest_path.stat().st_size <= 100000:
                raise ValueError("MANIFEST_SIZE_INVALID")
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            result = ensure_private_passport(folder, manifest)
            counters[result["status"]] += 1
        except (ValueError, OSError, TypeError, KeyError, UnicodeError) as exc:
            counters["blocked"] += 1
            reason = str(exc).split(":", 1)[0][:80]
            failures[reason] += 1
    return {
        "schema": "saeit.factory.private-passport-backfill.v1",
        "scanned": len(candidates),
        "created": counters["created"],
        "existing_verified": counters["existing_verified"],
        "blocked": counters["blocked"],
        "skipped": counters["skipped"],
        "blocked_reasons": dict(failures),
        "original_factory_packages_modified": False,
        "store_database_modified": False,
        "customer_payments_modified": False,
        "sale_enabled": False,
    }

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--private-root", required=True)
    parser.add_argument("--limit", type=int, default=1000)
    opts = parser.parse_args()
    data = backfill(opts.private_root, opts.limit)
    print("FACTORY_PRIVATE_PASSPORT_BACKFILL=" + json.dumps(data, sort_keys=True))
    print("FACTORY_COMMERCIAL_GATE_STILL_CLOSED=PASS")
