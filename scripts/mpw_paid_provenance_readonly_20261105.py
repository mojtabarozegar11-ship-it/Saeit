#!/usr/bin/env python3
"""Read-only, privacy-safe reconciliation of MojPlayWin paid flags.

Never creates an order, contacts a blockchain node, reads buyer email,
touches private downloads, or prints IDs, addresses or transaction hashes.
A paid database flag is not proof of a completed customer delivery.
"""
from __future__ import annotations

import json
import os
import sys
from collections import Counter
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
from core.models import LedgerEntry, OrderItem, PaymentIntent, PaymentWebhookEvent
from core.crown_tron_receipts import PROVIDER, verified_walletless_credit


def fulfillment_for_order(order_id):
    """Count linked state only; READY is not proof the buyer downloaded."""
    try:
        model = apps.get_model("mpw_commerce", "CommerceFulfillment")
        fields = {field.name for field in model._meta.get_fields()}
        if "order" in fields:
            records = model.objects.filter(order_id=order_id)
        elif "order_item" in fields:
            records = model.objects.filter(order_item__order_id=order_id)
        else:
            return {"linkage": "not_available", "ready": None, "total": None}
        total = records.count()
        if "status" in fields:
            ready = records.filter(status__iexact="ready").count()
            return {"linkage": "order", "ready": ready, "total": total}
        return {"linkage": "order", "ready": None, "total": total}
    except (LookupError, AttributeError, TypeError, ValueError):
        return {"linkage": "not_available", "ready": None, "total": None}


def run():
    paid = PaymentIntent.objects.filter(status="paid").select_related("order")
    total = paid.count()
    rows = []
    provider_counts = Counter()
    valid_walletless_credits = 0
    for intent in paid.order_by("pk")[:100]:
        order = intent.order
        provider = str(intent.provider or "")[:64]
        provider_counts[provider] += 1
        products = sorted(set(OrderItem.objects.filter(order_id=order.pk).values_list("product_id", flat=True)))
        processed = PaymentWebhookEvent.objects.filter(
            payment_intent_id=intent.pk,
            provider=PROVIDER,
            event_type="tron_finalized",
            status="processed",
        ).count()
        credits = LedgerEntry.objects.filter(
            order_id=order.pk, payment_intent_id=intent.pk, entry_type="credit"
        ).count()
        verified = bool(verified_walletless_credit(order, intent)) if provider == PROVIDER else False
        valid_walletless_credits += int(verified)
        customer = getattr(order, "customer", None)
        customer_class = (
            "unknown" if customer is None else
            "staff" if getattr(customer, "is_staff", False) or getattr(customer, "is_superuser", False)
            else "nonstaff_unverified"
        )
        rows.append({
            "products": products[:12],
            "provider": provider,
            "order_paid_flag": order.status == "paid",
            "customer_class": customer_class,
            "processed_finalized_events": processed,
            "matching_credit_ledger_rows": credits,
            "persisted_walletless_credit_verified": verified,
            "fulfillment": fulfillment_for_order(order.pk),
            "authenticated_buyer_download_proven": False,
        })
    print("MPW_PAID_PROVENANCE_READONLY=" + json.dumps({
        "paid_intent_count": total,
        "rows_examined": len(rows),
        "truncated": total > len(rows),
        "provider_counts_examined": dict(sorted(provider_counts.items())),
        "walletless_persisted_credit_verified": valid_walletless_credits,
        "independent_mainnet_recheck_performed": False,
        "customer_download_e2e_performed": False,
        "production_db_writes": False,
        "customer_pii_logged": False,
        "rows": rows,
    }, sort_keys=True, ensure_ascii=False))


if __name__ == "__main__":
    run()
