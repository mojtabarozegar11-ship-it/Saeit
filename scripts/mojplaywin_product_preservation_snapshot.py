#!/usr/bin/env python3
"""Read-only evidence for preserving *all real* Product records across publication.

Nothing in the present shared Product schema says which site a product belongs
to. Never infer MojPlayWin ownership from price, currency, product title,
authenticated user, current hostname or whether a product is active. Resolve
unknown product provenance manually BEFORE showing it on a domain or publishing.

Run only by authorized staff using a READ-ONLY database connection; the output
contains record fingerprints but NOT customer details, titles, wallet data or
product metadata. Output must be kept private, not committed to the repo.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal
from hashlib import sha256
import json
import os
from pathlib import Path

OWNERSHIP_KEYS = ("site", "domain", "storefront_host", "brand_domain")
MAIN_HOSTS = frozenset(("mojplaywin.com", "www.mojplaywin.com"))


def owner_for(metadata: object) -> str:
    if not isinstance(metadata, dict):
        return "unverified"
    values = []
    for key in OWNERSHIP_KEYS:
        host = metadata.get(key)
        if isinstance(host, str) and host.strip():
            cleaned = host.lower().strip().rstrip("/")
            if cleaned.startswith("https://"):
                cleaned = cleaned[8:]
            elif cleaned.startswith("http://"):
                cleaned = cleaned[7:]
            # Only explicit exact host declarations count; never trust a path,
            # loose substring, URL parameters, ports or arbitrary brand text.
            if "/" in cleaned or ":" in cleaned or "@" in cleaned or "?" in cleaned:
                return "ambiguous"
            values.append(cleaned)
    if not values:
        return "unverified"
    domains = set(values)
    if len(domains) > 1:
        return "ambiguous"
    return "mojplaywin" if domains.issubset(MAIN_HOSTS) else "other_explicit_domain"


def canonical(value):
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, dict):
        return {str(k): canonical(v) for k, v in sorted(value.items())}
    if isinstance(value, (tuple, list)):
        return [canonical(x) for x in value]
    if isinstance(value, (datetime,)):
        return value.isoformat()
    return value


def fingerprint(record: dict) -> str:
    payload = json.dumps(canonical(record), ensure_ascii=False,
                         sort_keys=True, separators=(",", ":"))
    return sha256(payload.encode("utf-8")).hexdigest()


PRODUCT_FIELDS = (
    "id", "title", "product_type", "price", "currency", "active",
    "owner_id", "knowledge_article_id", "metadata",
)
ORDER_FIELDS = ("id", "customer_id", "status", "total", "currency")
ITEM_FIELDS = ("id", "order_id", "product_id", "quantity", "unit_price", "currency")
PAYMENT_FIELDS = (
    "id", "order_id", "amount", "currency", "idempotency_key",
    "status", "provider", "provider_reference",
)


def capture_inventory():
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    import django
    django.setup()
    from django.db import connections
    from core.models import Product, Order, OrderItem, PaymentIntent

    if connections["default"].settings_dict.get("NAME") in ("", None):
        raise RuntimeError("No database configured: refusing to guess product inventory.")
    tables = (
        ("products", Product, PRODUCT_FIELDS),
        ("orders", Order, ORDER_FIELDS),
        ("order_items", OrderItem, ITEM_FIELDS),
        ("payment_intents", PaymentIntent, PAYMENT_FIELDS),
    )
    proof = {}
    ownership = Counter()
    for kind, model, fields in tables:
        # Only SELECT statements; read-only DB permissions recommended.
        rows = model.objects.order_by("pk").values(*fields).iterator(chunk_size=500)
        entry = {}
        for record in rows:
            pk = str(record["id"])
            entry[pk] = fingerprint(record)
            if kind == "products":
                ownership[owner_for(record["metadata"])] += 1
        proof[kind] = entry
    return {
        "schema": "mojplaywin-preservation-v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "scope": "shared_database_read_only",
        "products_by_explicit_provenance": dict(sorted(ownership.items())),
        "ownership_confirmed_for_every_product":
            not any(ownership[key] for key in ("unverified", "ambiguous")),
        "record_count": {k: len(v) for k, v in proof.items()},
        "row_sha256": proof,
        "payment_networks_tested": False,
        "product_files_verified": False,
        "checkout_integrity_verified": False,
    }


def compare(before: dict, after: dict) -> dict:
    if before.get("schema") != "mojplaywin-preservation-v1" or after.get("schema") != "mojplaywin-preservation-v1":
        return {"accepted": False, "errors": ["incompatible_inventory_schema"]}
    if "row_sha256" not in before or "row_sha256" not in after:
        return {"accepted": False, "errors": ["missing_private_record_fingerprints"]}
    errors = []
    diffs = {}
    for table in ("products", "orders", "order_items", "payment_intents"):
        old = before["row_sha256"].get(table, {})
        new = after["row_sha256"].get(table, {})
        removed = [pk for pk in old if pk not in new]
        modified = [pk for pk in old if pk in new and old[pk] != new[pk]]
        diffs[table] = {
            "before": len(old), "after": len(new),
            "removed_existing": len(removed), "modified_existing": len(modified),
            "added": len(set(new) - set(old)),
        }
        if removed or modified:
            errors.append(f"{table}: existing records removed or changed")
    if not before.get("ownership_confirmed_for_every_product"):
        errors.append("before: product-domain ownership unverified")
    if not after.get("ownership_confirmed_for_every_product"):
        errors.append("after: product-domain ownership unverified")
    return {
        "accepted": not errors,
        "errors": errors,
        "comparisons": diffs,
        "warning": "File media, active crypto payment and live checkout must also be checked independently.",
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--compare-with", type=Path)
    p.add_argument("--acknowledge-readonly-db", action="store_true")
    args = p.parse_args()
    if not args.acknowledge_readonly_db:
        raise SystemExit("Read-only database access must be explicitly acknowledged.")
    now = capture_inventory()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    if args.output.exists():
        raise SystemExit("Refusing to overwrite an existing preservation snapshot.")
    args.output.write_text(json.dumps(now, ensure_ascii=False, indent=2), encoding="utf-8")
    try:
        args.output.chmod(0o600)
    except OSError:
        pass
    print("MojPlayWin shared product integrity snapshot saved privately.")
    print("Record counts:", now["record_count"])
    print("Explicit product-domain ownership:", now["products_by_explicit_provenance"])
    if args.compare_with:
        before = json.loads(args.compare_with.read_text(encoding="utf-8"))
        diff = compare(before, now)
        print("Existing record preservation:", "PASS" if diff["accepted"] else "BLOCKED")
        print("Table diff counts:", diff["comparisons"])
        print("Unresolved:", diff["errors"])
        if not diff["accepted"]:
            raise SystemExit(1)


if __name__ == "__main__":
    main()
