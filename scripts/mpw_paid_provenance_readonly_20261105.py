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


TRACKED_SKUS = (72, 225, 779, 879)


def tracked_sku_paid_summary(rows, total):
    """Aggregate only verified-in-database evidence, never customer identities.

    One paid intent containing a SKU is one count, regardless of quantity.
    Zero in a truncated sample must not be presented as zero across the DB.
    These counters do NOT prove an independent mainnet transfer or download.
    """
    paid = {str(sku): 0 for sku in TRACKED_SKUS}
    credits = {str(sku): 0 for sku in TRACKED_SKUS}
    prepared = {str(sku): 0 for sku in TRACKED_SKUS}
    tracked = set(TRACKED_SKUS)
    for row in rows:
        products = row.get("products", [])
        if not isinstance(products, list):
            continue
        sku_ids = {sku for sku in products if type(sku) is int and sku in tracked}
        for sku in sku_ids:
            key = str(sku)
            paid[key] += 1
            if row.get("persisted_walletless_credit_verified") is True:
                credits[key] += 1
            fulfillment = row.get("fulfillment")
            if isinstance(fulfillment, dict) and type(fulfillment.get("ready")) is int:
                if fulfillment["ready"] > 0:
                    prepared[key] += 1
    return {
        "tracked_skus": list(TRACKED_SKUS),
        "sample_complete": total == len(rows) and not any(
            row.get("products_truncated") is True for row in rows),
        "paid_intents_containing_sku": paid,
        "persisted_walletless_credit_intents_containing_sku": credits,
        "paid_intents_with_any_ready_fulfillment_containing_sku": prepared,
        "independent_mainnet_payment_reverified": False,
        "authenticated_buyer_download_verified": False,
        "zero_is_global_only_if_sample_complete": True,
        "unit": "payment_intents_with_sku_not_units_sold",
    }


def fulfillment_for_order(order_id):
    """Count linked state only; READY is not proof the buyer downloaded."""
    try:
        model = apps.get_model("mpw_commerce", "CommerceFulfillment")
        fields = {field.name for field in model._meta.get_fields()}
        if "order" in fields:
            records = model.objects.filter(order_id=order_id)
        elif "order_item" in fields:
            records = model.objects.filter(order_item__order_id=order_id)
        elif "item" in fields:
            records = model.objects.filter(item__order_id=order_id)
        else:
            return {"linkage": "not_available", "ready": None, "total": None}
        total = records.count()
        if "status" in fields:
            ready = records.filter(status__iexact="ready").count()
            statuses = dict(Counter(str(value)[:48] for value in records.values_list("status", flat=True)[:50]))
            return {"linkage": "order_or_item", "ready": ready, "total": total, "status_counts": statuses}
        return {"linkage": "order", "ready": None, "total": total}
    except (LookupError, AttributeError, TypeError, ValueError):
        return {"linkage": "not_available", "ready": None, "total": None}



def fulfillment_model_shape():
    """Field names and related model labels only; no stored values or buyer details."""
    try:
        model = apps.get_model("mpw_commerce", "CommerceFulfillment")
        fields = []
        for field in model._meta.fields:
            related = getattr(field, "related_model", None)
            fields.append({
                "field": str(field.name)[:64],
                "type": str(field.get_internal_type())[:40],
                "related_model": str(related._meta.label_lower)[:90] if related else None,
            })
        return {"available": True, "records": model.objects.count(), "fields": fields[:35]}
    except (LookupError, AttributeError, TypeError, ValueError):
        return {"available": False, "records": None, "fields": []}



def delivery_model_inventory():
    """Schema and count only. These are NOT proof of authenticated downloads."""
    names = ("CommerceReceipt", "CommerceEntitlement", "CommerceDownload")
    result = {}
    for name in names:
        try:
            model = apps.get_model("mpw_commerce", name)
            fields = model._meta.fields
            result[name] = {
                "available": True,
                "total_records": model.objects.count(),
                "field_names": [str(f.name)[:60] for f in fields[:35]],
                "related_model_labels": {
                    str(f.name)[:60]: str(f.related_model._meta.label_lower)[:80]
                    for f in fields if getattr(f, "related_model", None)
                },
            }
        except LookupError:
            result[name] = {"available": False, "total_records": None}
        except Exception as exc:
            result[name] = {"available": None, "error_type": type(exc).__name__}
    return result


def delivery_records_for_order(order_id):
    """Inspect database-linked evidence without returning buyer or order identifiers."""
    result = {}
    for name in ("CommerceReceipt", "CommerceEntitlement", "CommerceDownload"):
        try:
            model = apps.get_model("mpw_commerce", name)
            fields = {f.name: f for f in model._meta.fields}
            relation = None
            for candidate, lookup in (
                ("order", "order_id"),
                ("item", "item__order_id"),
                ("order_item", "order_item__order_id"),
            ):
                f = fields.get(candidate)
                related = getattr(f, "related_model", None)
                if related and related._meta.label_lower in (
                    "core.order" if candidate == "order" else "core.orderitem",
                ):
                    relation = lookup
                    break
            if relation is None and "invoice" in fields:
                parent = getattr(fields["invoice"], "related_model", None)
                if parent is not None and any(
                    f.name == "order" and getattr(f, "related_model", None)
                    and f.related_model._meta.label_lower == "core.order"
                    for f in parent._meta.fields
                ):
                    relation = "invoice__order_id"
            if relation is None:
                result[name] = {"linkage": "not_established", "records": None}
                continue
            qs = model.objects.filter(**{relation: order_id})
            evidence = {"linkage": relation, "records": qs.count()}
            if "status" in fields:
                evidence["status_counts"] = dict(Counter(
                    str(v)[:48] for v in qs.values_list("status", flat=True)[:30]
                ))
            if "downloaded_at" in fields:
                evidence["downloaded_at_nonnull"] = qs.filter(downloaded_at__isnull=False).count()
            result[name] = evidence
        except LookupError:
            result[name] = {"linkage": "model_absent", "records": None}
        except Exception as exc:
            result[name] = {"linkage": "query_failed", "error_type": type(exc).__name__, "records": None}
    return result


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
            "products_truncated": len(products) > 12,
            "provider": provider,
            "order_paid_flag": order.status == "paid",
            "customer_class": customer_class,
            "processed_finalized_events": processed,
            "matching_credit_ledger_rows": credits,
            "persisted_walletless_credit_verified": verified,
            "fulfillment": fulfillment_for_order(order.pk),
            "delivery_record_evidence": delivery_records_for_order(order.pk),
            "authenticated_buyer_download_proven": False,
        })
    print("MPW_PAID_PROVENANCE_READONLY=" + json.dumps({
        "paid_intent_count": total,
        "rows_examined": len(rows),
        "truncated": total > len(rows),
        "provider_counts_examined": dict(sorted(provider_counts.items())),
        "walletless_persisted_credit_verified": valid_walletless_credits,
        "tracked_sku_summary": tracked_sku_paid_summary(rows, total),
        "fulfillment_schema_metadata": fulfillment_model_shape(),
        "delivery_model_inventory": delivery_model_inventory(),
        "independent_mainnet_recheck_performed": False,
        "customer_download_e2e_performed": False,
        "production_db_writes": False,
        "customer_pii_logged": False,
        "rows": rows,
    }, sort_keys=True, ensure_ascii=False))


if __name__ == "__main__":
    run()
