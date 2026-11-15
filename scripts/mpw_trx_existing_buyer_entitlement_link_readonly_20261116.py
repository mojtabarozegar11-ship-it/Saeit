#!/usr/bin/env python3
"""Scoped, read-only diagnosis of the REAL paid walletless order's buyer access.

Never creates/repairs receipts or entitlements, never downloads a private file.
Only joins models when an actual Django FK points to the exact core Order or
OrderItem; coincidental numeric IDs across apps MUST NOT be treated as proof.
Result contains boolean aggregated evidence only, no buyer names/IDs, payment
amounts, email addresses, order IDs, paths, URLs, tokens, or transaction hashes.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path("/home/zomorod2/Saeit-staging")
PROVIDER = "mpw_walletless_trx_v1"
MAX_PAID = 25
MAX_ITEMS = 30


def fk_matches(model, name, expected):
    """True only for a real FK of this exact Django related model."""
    if model is None:
        return False
    try:
        f = model._meta.get_field(name)
        related = getattr(f, "related_model", None)
        return getattr(getattr(related, "_meta", None), "label_lower", None) == expected
    except (LookupError, AttributeError, TypeError):
        return False


def evaluate_links(*, core_paid, commerce_invoice_available,
                   commerce_invoice_paid, commerce_receipt_available,
                   commerce_receipt_same_invoice, fulfillment_ready,
                   checker_says_allowed, checks_are_related):
    """Do not assert paid digital delivery solely from READY or credit event."""
    flags = (
        core_paid, commerce_invoice_available, commerce_invoice_paid,
        commerce_receipt_available, commerce_receipt_same_invoice,
        fulfillment_ready, checker_says_allowed, checks_are_related,
    )
    if any(type(x) is not bool for x in flags):
        raise ValueError("exact boolean facts required")
    return {
        "core_paid_receipt_consistent": core_paid,
        "same_order_commerce_invoice_found": commerce_invoice_available,
        "same_order_commerce_invoice_paid": commerce_invoice_paid,
        "same_order_commerce_receipt_found": commerce_receipt_available,
        "same_order_commerce_receipt_invoice_link_proven": commerce_receipt_same_invoice,
        "same_core_item_fulfillment_ready": fulfillment_ready,
        "authenticated_buyer_entitlement_checker_allows": checker_says_allowed,
        "all_relations_verified_by_django_fk": checks_are_related,
        "requires_invoice_bridge_review": core_paid and checks_are_related and not commerce_invoice_available,
        "requires_receipt_bridge_review": core_paid and checks_are_related and commerce_invoice_available and not commerce_receipt_available,
        "entitlement_denied_despite_ready": core_paid and fulfillment_ready and not checker_says_allowed,
        "file_download_observed": False,
        "buyer_acknowledgment_observed": False,
        "new_paid_order_created": False,
        "wallet_transfer_or_fee_created": False,
        "source_only_no_automatic_entitlement_grant": True,
    }


def inspect_order():
    from django.apps import apps
    from core.models import OrderItem, PaymentIntent, LedgerEntry
    from core.crown_tron_receipts import verified_walletless_credit

    invoice_model = apps.get_model("mpw_commerce", "CommerceInvoice")
    receipt_model = apps.get_model("mpw_commerce", "CommerceReceipt")
    fulfillment_model = apps.get_model("mpw_commerce", "CommerceFulfillment")
    invoice_fk = fk_matches(invoice_model, "order", "core.order")
    receipt_fk = fk_matches(receipt_model, "invoice", "mpw_commerce.commerceinvoice")
    fulfillment_fk = (
        fk_matches(fulfillment_model, "item", "core.orderitem")
        or fk_matches(fulfillment_model, "order_item", "core.orderitem")
    )
    linkage_proven = invoice_fk and receipt_fk and fulfillment_fk

    entitlement_imported = False
    entitlement_core_model = False
    checker = None
    try:
        import mpw_commerce.entitlements as entitlements
        checker = getattr(entitlements, "can_access_purchased_digital_item", None)
        module_item = getattr(entitlements, "OrderItem", None)
        entitlement_core_model = (
            getattr(getattr(module_item, "_meta", None), "label_lower", None) ==
            "core.orderitem"
        )
        entitlement_imported = callable(checker)
    except ImportError:
        pass

    result = {
        "schema": "mpw.trx.walletless.paid.commerce.invoice_link.v1",
        "read_only": True,
        "core_invoice_fk_proven": invoice_fk,
        "commerce_receipt_fk_proven": receipt_fk,
        "core_fulfillment_item_fk_proven": fulfillment_fk,
        "commerce_entitlement_checker_available": entitlement_imported,
        "commerce_entitlement_reads_core_orderitem": entitlement_core_model,
        "paid_nonstaff_order_found": False,
        "same_order_paid_receipt_present": False,
        "noncosmetic_paid_item_found": False,
        "product_is_active": False,
        "invoice_record_present": False,
        "invoice_paid_record_present": False,
        "receipt_for_same_invoice_present": False,
        "same_item_ready_fulfillment_present": False,
        "same_buyer_entitlement_allowed": False,
        "refund_or_reversal_present": False,
        "same_order_links_eligible_for_inference": linkage_proven,
        "buyer_download_executed": False,
        "buyer_acknowledgment_proven": False,
        "new_payment_or_financial_write": False,
    }
    qs = PaymentIntent.objects.filter(
        provider=PROVIDER, status="paid"
    ).select_related("order__customer").order_by("pk")
    result["paid_scope_exhaustive"] = qs.count() <= MAX_PAID

    for intent in qs[:MAX_PAID]:
        order = intent.order
        if order.customer.is_staff is True or order.customer.is_superuser is True:
            continue
        if verified_walletless_credit(order, intent) is not True:
            continue
        if LedgerEntry.objects.filter(
            order_id=order.pk, entry_type__in=("refund", "reversal", "chargeback")
        ).exists():
            result["refund_or_reversal_present"] = True
            continue
        result["paid_nonstaff_order_found"] = True
        result["same_order_paid_receipt_present"] = True

        items = list(OrderItem.objects.filter(
            order_id=order.pk
        ).select_related("product").order_by("pk")[:MAX_ITEMS])
        result["item_scan_exhaustive"] = (
            OrderItem.objects.filter(order_id=order.pk).count() <= MAX_ITEMS
        )
        if invoice_fk:
            invoices = invoice_model.objects.filter(order_id=order.pk)
            result["invoice_record_present"] = invoices.exists()
            result["invoice_paid_record_present"] = invoices.filter(
                status__iexact="paid"
            ).exists()
        else:
            invoices = None

        if invoice_fk and receipt_fk:
            result["receipt_for_same_invoice_present"] = receipt_model.objects.filter(
                invoice__order_id=order.pk
            ).exists()

        for item in items:
            if item.product.product_type == "game_cosmetic":
                continue
            result["noncosmetic_paid_item_found"] = True
            result["product_is_active"] |= item.product.active is True

            if fulfillment_fk:
                if fk_matches(fulfillment_model, "item", "core.orderitem"):
                    linked = fulfillment_model.objects.filter(item_id=item.pk)
                else:
                    linked = fulfillment_model.objects.filter(order_item_id=item.pk)
                if linked.filter(status__iexact="ready").exists():
                    result["same_item_ready_fulfillment_present"] = True
                if linked.filter(status__iexact="complete").exists():
                    result["same_item_ready_fulfillment_present"] = True

            if checker is not None and entitlement_core_model:
                try:
                    if checker(item.pk, order.customer_id) is True:
                        result["same_buyer_entitlement_allowed"] = True
                except (TypeError, ValueError, KeyError, AttributeError):
                    continue
        break

    if result["paid_nonstaff_order_found"]:
        result.update(evaluate_links(
            core_paid=result["same_order_paid_receipt_present"],
            commerce_invoice_available=result["invoice_record_present"],
            commerce_invoice_paid=result["invoice_paid_record_present"],
            commerce_receipt_available=result["receipt_for_same_invoice_present"],
            commerce_receipt_same_invoice=result["receipt_for_same_invoice_present"],
            fulfillment_ready=result["same_item_ready_fulfillment_present"],
            checker_says_allowed=result["same_buyer_entitlement_allowed"],
            checks_are_related=linkage_proven,
        ))
    return result


def main():
    if not ROOT.is_dir() or ROOT.is_symlink() or ROOT.resolve() != ROOT:
        raise SystemExit("UNTRUSTED_TENANT")
    os.chdir(ROOT)
    sys.path.insert(0, str(ROOT))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    try:
        import django
        django.setup()
        result = inspect_order()
        result["inspection_available"] = True
        result["error_type"] = None
    except Exception as exc:
        result = {"schema": "mpw.trx.walletless.paid.commerce.invoice_link.v1",
                  "read_only": True,
                  "inspection_available": False,
                  "error_type": type(exc).__name__,
                  "paid_scope_exhaustive": False,
                  "new_payment_or_financial_write": False,
                  "buyer_download_executed": False}
    print("MPW_TRX_EXISTING_BUYER_LINK_READONLY="
          + json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
