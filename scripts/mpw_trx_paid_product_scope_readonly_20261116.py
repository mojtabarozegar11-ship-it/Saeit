#!/usr/bin/env python3
"""Privacy-safe classification of ACTUAL prior TRX paid orders and fulfillment.

Runs on the authorized live cPanel tenant; zero writes, RPC, email, download
or invoice creation. Results are aggregate booleans, never row IDs, payment
amounts, transaction hashes, buyer identities, wallet balances or secrets.
The purpose is to distinguish in-game cosmetic ownership from downloadable
products; absence of a download is NOT evidence that a game item was undelivered.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path("/home/zomorod2/Saeit-staging")
PROVIDER = "mpw_walletless_trx_v1"
MAX_ORDERS = 25
MAX_ITEMS = 30
READY_STATUSES = frozenset(("ready", "complete", "completed", "delivered"))


def category(product_type):
    """Classify *only* an explicitly reviewed non-download game category."""
    if type(product_type) is not str:
        return "unknown"
    if product_type == "game_cosmetic":
        return "game_cosmetic"
    return "other_product_type"


def match_core_relation(model, name):
    """Reject unrelated mpw_commerce order models that merely reuse an ID."""
    if model is None:
        return None
    for field in model._meta.fields:
        if field.name != name:
            continue
        related = getattr(field, "related_model", None)
        actual = getattr(getattr(related, "_meta", None), "label_lower", "")
        expected = {
            "order": "core.order",
            "order_item": "core.orderitem",
            "item": "core.orderitem",
        }.get(name)
        return actual if actual == expected else None
    return None


def fulfillment_evidence(order, items):
    """Only count rows linked by an ORM FK *to core.Order or core.OrderItem*."""
    from django.apps import apps
    try:
        model = apps.get_model("mpw_commerce", "CommerceFulfillment")
    except LookupError:
        return {"model_available": False, "core_relation_proven": False,
                "same_order_fulfillment_present": False,
                "same_order_ready_record_present": False}
    fks = {name: match_core_relation(model, name)
           for name in ("order", "item", "order_item")}
    filters = []
    if fks["order"] == "core.order":
        filters.append({"order_id": order.pk})
    elif fks["item"] == "core.orderitem":
        filters.extend({"item_id": item.pk} for item in items)
    elif fks["order_item"] == "core.orderitem":
        filters.extend({"order_item_id": item.pk} for item in items)
    if not filters:
        return {"model_available": True, "core_relation_proven": False,
                "same_order_fulfillment_present": False,
                "same_order_ready_record_present": False}
    has = False
    ready = False
    for lookup in filters[:MAX_ITEMS]:
        qs = model.objects.filter(**lookup)
        if qs.exists():
            has = True
            if any(field.name == "status" for field in model._meta.fields):
                for state in READY_STATUSES:
                    if qs.filter(status__iexact=state).exists():
                        ready = True
                        break
    return {"model_available": True, "core_relation_proven": True,
            "same_order_fulfillment_present": has,
            "same_order_ready_record_present": ready}


def evidence_flags(*, paid, verified, is_staff, has_items,
                   cosmetic, other, owned_cosmetic, fulfillment, refund):
    """Only strict booleans, never convert unknown order type into a failure."""
    for value in (paid, verified, is_staff, has_items, cosmetic, other,
                  owned_cosmetic, refund):
        if type(value) is not bool:
            raise ValueError("nonboolean payment-state evidence")
    return {
        "has_stored_paid_intent": paid,
        "has_valid_stored_walletless_receipt": verified,
        "staff_or_owner_test_account": is_staff,
        "order_has_items": has_items,
        "order_contains_in_game_cosmetic": cosmetic,
        "order_contains_other_or_unknown_type": other,
        "cosmetic_sku_visible_in_buyer_game_fleet": owned_cosmetic,
        "order_has_refund_or_reversal": refund,
        "same_order_fulfillment_fk_proven": fulfillment["core_relation_proven"] is True,
        "same_order_fulfillment_row_present": fulfillment["same_order_fulfillment_present"] is True,
        "same_order_fulfillment_ready": fulfillment["same_order_ready_record_present"] is True,
        "digital_file_delivery_evaluated": False,
        "buyer_download_e2e_performed": False,
        "fresh_tron_solidity_checked": False,
        "actual_external_buyer_proven": False,
    }


def inspect_existing():
    from core.models import PaymentIntent, OrderItem, LedgerEntry
    from core.crown_tron_receipts import verified_walletless_credit
    from core.crown_fleet import SKUS, owned_skus

    paid = PaymentIntent.objects.filter(
        provider=PROVIDER, status="paid"
    ).select_related("order__customer").order_by("pk")
    overflow = paid.count() > MAX_ORDERS
    agg = {
        "stored_paid_order_present": False,
        "valid_walletless_ledger_receipt_present": False,
        "valid_paid_order_with_nonstaff_account_present": False,
        "valid_paid_order_with_staff_account_present": False,
        "verified_paid_order_with_no_items_present": False,
        "verified_paid_game_cosmetic_present": False,
        "verified_paid_other_product_present": False,
        "verified_paid_game_cosmetic_owned_present": False,
        "verified_paid_same_order_fulfillment_present": False,
        "verified_paid_same_order_ready_fulfillment_present": False,
        "verified_paid_refund_or_reversal_present": False,
        "fulfillment_relation_to_core_order_observed": False,
        "any_verified_paid_customer_download_proven": False,
        "external_buyer_identity_independently_proven": False,
        "fresh_solidity_confirmation_performed": False,
        "paid_order_review_exhaustive": not overflow,
        "items_cap_exceeded": False,
        "read_only": True,
    }

    for intent in paid[:MAX_ORDERS]:
        agg["stored_paid_order_present"] = True
        order = intent.order
        try:
            verified = verified_walletless_credit(order, intent) is True
        except (TypeError, ValueError, AttributeError, KeyError):
            continue
        if not verified:
            continue
        agg["valid_walletless_ledger_receipt_present"] = True
        is_staff = order.customer.is_staff is True or order.customer.is_superuser is True
        agg["valid_paid_order_with_staff_account_present"] |= is_staff
        agg["valid_paid_order_with_nonstaff_account_present"] |= not is_staff

        items_qs = OrderItem.objects.filter(order_id=order.pk).select_related("product").order_by("pk")
        if items_qs.count() > MAX_ITEMS:
            agg["items_cap_exceeded"] = True
        items = list(items_qs[:MAX_ITEMS])
        if not items:
            agg["verified_paid_order_with_no_items_present"] = True

        product_categories = [category(item.product.product_type) for item in items]
        cosmetic = "game_cosmetic" in product_categories
        other = any(kind != "game_cosmetic" for kind in product_categories)
        agg["verified_paid_game_cosmetic_present"] |= cosmetic
        agg["verified_paid_other_product_present"] |= other

        refund = LedgerEntry.objects.filter(
            order_id=order.pk, entry_type__in=("refund", "reversal", "chargeback")
        ).exists()
        agg["verified_paid_refund_or_reversal_present"] |= refund

        sku_owned = False
        if cosmetic and not refund:
            try:
                visible = set(owned_skus(order.customer))
                sku_owned = any(
                    category(item.product.product_type) == "game_cosmetic"
                    and isinstance(item.product.metadata, dict)
                    and item.product.metadata.get("crown_sku") in SKUS
                    and item.product.metadata.get("crown_sku") in visible
                    for item in items
                )
            except (TypeError, ValueError, AttributeError, KeyError):
                sku_owned = False
        agg["verified_paid_game_cosmetic_owned_present"] |= sku_owned

        fulfillment = fulfillment_evidence(order, items)
        agg["fulfillment_relation_to_core_order_observed"] |= (
            fulfillment["core_relation_proven"] is True
        )
        agg["verified_paid_same_order_fulfillment_present"] |= (
            fulfillment["same_order_fulfillment_present"] is True
        )
        agg["verified_paid_same_order_ready_fulfillment_present"] |= (
            fulfillment["same_order_ready_record_present"] is True
        )

    return agg


def main():
    if not ROOT.is_dir() or ROOT.is_symlink() or ROOT.resolve() != ROOT:
        raise SystemExit("UNEXPECTED_LIVE_TENANT")
    os.chdir(ROOT)
    sys.path.insert(0, str(ROOT))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    try:
        import django
        django.setup()
        data = inspect_existing()
        data["db_inspection_available"] = True
        data["db_error_type"] = None
    except Exception as exc:
        data = {"db_inspection_available": False,
                "db_error_type": type(exc).__name__,
                "read_only": True,
                "paid_order_review_exhaustive": False,
                "fresh_solidity_confirmation_performed": False}
    # Treat no result and missing DB as UNKNOWN, never as absence of real money.
    print("MPW_TRX_PAID_PRODUCT_SCOPE_READONLY=" + json.dumps({
        "schema": "mpw.trx.existing.paid.product.delivery.v1",
        "merchant_host": "mojplaywin.com",
        **data,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
