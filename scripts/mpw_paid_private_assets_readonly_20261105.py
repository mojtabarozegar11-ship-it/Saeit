#!/usr/bin/env python3
"""Read-only production proof of paid-order private assets and email claims.

No customer values, paths, hashes, invoice references, or wallet IDs are emitted.
This does not impersonate a buyer, serve files, or prove completed download.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path


ROOT = Path("/home/zomorod2/Saeit-staging")
if not ROOT.is_dir() or ROOT.is_symlink():
    raise RuntimeError("UNEXPECTED_LIVE_RUNTIME_ROOT")
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django

django.setup()

from django.apps import apps
from django.conf import settings
from core.models import GuestOrderEmail, OrderItem, PaymentIntent
from core.crown_tron_receipts import PROVIDER, verified_walletless_credit
from mpw_commerce.buyer_orders import _private_file


def file_verified(item):
    """Verify a protected file against its recorded SHA-256 without disclosing it."""
    file_path = _private_file(item)
    if not isinstance(file_path, Path):
        return False
    if file_path.is_symlink() or not file_path.is_file():
        return False
    size = file_path.stat().st_size
    if size < 1000 or size > 64 * 1024 * 1024:
        return False
    metadata = getattr(item.product, "metadata", None)
    if not isinstance(metadata, dict):
        return False
    commerce = metadata.get("mpw_commerce", {})
    expected = commerce.get("sha256") if isinstance(commerce, dict) else None
    if not isinstance(expected, str) or len(expected) != 64:
        return False
    digest = hashlib.sha256()
    with file_path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest() == expected.lower()


def run():
    Fulfillment = apps.get_model("mpw_commerce", "CommerceFulfillment")
    paid = PaymentIntent.objects.filter(provider=PROVIDER, status="paid")
    total = paid.count()
    if total > 10:
        raise RuntimeError("PAID_AUDIT_BOUND_EXCEEDED")

    result = {
        "source": "live_mariadb_and_private_cpanel_files",
        "paid_intents": total,
        "distinct_paid_orders": 0,
        "verified_local_paid_orders": 0,
        "paid_orders_with_checkout_email_claim": 0,
        "items_examined": 0,
        "items_with_ready_fulfillment": 0,
        "items_with_verified_private_file_sha256": 0,
        "every_paid_item_asset_verified": False,
        "buyer_download_proven": False,
        "recovery_flag_on": getattr(settings, "MPW_GUEST_RECOVERY_ENABLED", False) is True,
        "recovery_email_approved": getattr(settings, "MPW_GUEST_RECOVERY_EMAIL_APPROVED", False) is True,
        "customer_identifiers_logged": False,
        "production_writes": False,
        "outbound_email": False,
        "blockchain_requests": False,
    }
    seen = set()
    for intent in paid.select_related("order").order_by("pk")[:10]:
        order = intent.order
        if order.pk in seen:
            continue
        seen.add(order.pk)
        result["verified_local_paid_orders"] += int(bool(verified_walletless_credit(order, intent)))
        result["paid_orders_with_checkout_email_claim"] += int(
            GuestOrderEmail.objects.filter(order_id=order.pk).exists()
        )
        items = OrderItem.objects.filter(order_id=order.pk).select_related("product")
        for item in items:
            result["items_examined"] += 1
            result["items_with_ready_fulfillment"] += int(
                Fulfillment.objects.filter(item_id=item.pk, status__iexact="ready").exists()
            )
            result["items_with_verified_private_file_sha256"] += int(file_verified(item))
    result["distinct_paid_orders"] = len(seen)
    result["every_paid_item_asset_verified"] = bool(result["items_examined"]) and (
        result["items_examined"] == result["items_with_ready_fulfillment"]
        == result["items_with_verified_private_file_sha256"]
    )
    print("MPW_PAID_PRIVATE_ASSET_READONLY=" + json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    run()
