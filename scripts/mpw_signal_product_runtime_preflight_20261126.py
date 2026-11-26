#!/usr/bin/env python3
"""Read-only runtime inventory for paid Signal Desk subscription products.

This command never creates products, invoices, orders or subscriptions and
never changes public-sale settings. It only reports whether the database has
the exact product records required by the existing subscription adapter.
"""

from __future__ import annotations

import json
import os
import sys
from decimal import Decimal

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django

django.setup()

from core.models import Product  # noqa: E402


EXPECTED = {
    "education-weekly": {"price": Decimal("9.90"), "weeks": 1},
    "education-monthly": {"price": Decimal("29.90"), "weeks": 4},
    "education-quarterly": {"price": Decimal("79.90"), "weeks": 12},
}


def _safe_metadata(value):
    return value if isinstance(value, dict) else {}


def _inspect(plan_id, rule):
    candidates = list(
        Product.objects.filter(metadata__signal_plan_id=plan_id)
        .order_by("pk")
    )
    rows = []
    for product in candidates:
        metadata = _safe_metadata(product.metadata)
        commerce = metadata.get("mpw_commerce")
        rows.append(
            {
                "id": product.pk,
                "title": product.title,
                "active": product.active is True,
                "product_type": product.product_type,
                "price": str(product.price),
                "currency": product.currency,
                "rights_cleared": metadata.get("rights_cleared") is True,
                "commerce_enabled": (
                    isinstance(commerce, dict)
                    and commerce.get("enabled") is True
                ),
                "fulfillment": (
                    commerce.get("fulfillment")
                    if isinstance(commerce, dict)
                    else None
                ),
            }
        )
    exact = [
        row
        for row in rows
        if (
            row["active"]
            and row["product_type"] == "subscription"
            and row["price"] == str(rule["price"])
            and row["currency"] == "USD"
            and row["rights_cleared"]
            and row["commerce_enabled"]
            and row["fulfillment"] == "subscription"
        )
    ]
    return {
        "expected_price_usd": str(rule["price"]),
        "expected_term_weeks": rule["weeks"],
        "candidate_count": len(rows),
        "candidates": rows,
        "exact_active_product_count": len(exact),
        "ready_for_adapter": len(exact) == 1,
    }


def main():
    plans = {plan_id: _inspect(plan_id, rule) for plan_id, rule in EXPECTED.items()}
    all_inventory_ready = all(item["ready_for_adapter"] for item in plans.values())
    report = {
        "schema": "mojtaba.signal.product_runtime_preflight.v1",
        "read_only": True,
        "public_signal_subscription_enabled": False,
        "public_sale_changed": False,
        "all_expected_products_present": all_inventory_ready,
        "plans": plans,
        "note": (
            "This inventory check does not prove feed, review, delivery, "
            "renewal, refund or production settlement readiness."
        ),
    }
    print(json.dumps(report, ensure_ascii=False, sort_keys=True, default=str))
    return 0 if all_inventory_ready else 2


if __name__ == "__main__":
    raise SystemExit(main())
