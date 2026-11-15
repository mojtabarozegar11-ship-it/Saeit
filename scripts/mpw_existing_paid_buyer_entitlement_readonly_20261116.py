#!/usr/bin/env python3
"""Read only ONE correctly linked historic paid TRX buyer's delivery controls.

Runs on the existing authorized cPanel app. Only bounded aggregate booleans
are emitted. No invoice creation, buyer identity, email, TXID, file content,
amount, wallet, URL or bearer link may reach public Actions logs.
This DOES NOT prove an independent buyer's acknowledgment or fresh finality.
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


def exact_one_to_one(model, field_name, related_label):
    """Only traverse an actual exact-model one-to-one FK, never a numeric ID."""
    if model is None:
        return False
    for field in model._meta.fields:
        if field.name == field_name:
            meta = getattr(getattr(field, "related_model", None), "_meta", None)
            return (getattr(field, "one_to_one", False) is True
                    and getattr(meta, "label_lower", None) == related_label)
    return False


def product_kind(value):
    """Never infer a downloadable asset from a vague non-game product type."""
    if value in ("digital", "digital_book") and type(value) is str:
        return "explicit_digital"
    if value == "game_cosmetic":
        return "game_cosmetic"
    return "other_or_unknown"


def _model(name):
    from django.apps import apps
    try:
        return apps.get_model("mpw_commerce", name)
    except LookupError:
        return None


def _base():
    return {
        "schema": "mpw.existing_paid_buyer.same_order_entitlement.readonly.v1",
        "read_only": True,
        "no_money_or_customer_messages": True,
        "same_order_candidate_found": False,
        "candidate_product_kind": None,
        "candidate_account_kind": None,
        "guest_outbox_missing_for_guest": None,
        "paid_scan_exhaustive": None,
        "item_scan_exhaustive": None,
        "ready_fulfillment_model_fk_verified": None,
        "same_item_ready_digital_fulfillment": None,
        "exact_core_invoice_order_fk_verified": None,
        "same_order_commerce_invoice_present": None,
        "same_order_commerce_invoice_paid": None,
        "exact_receipt_invoice_fk_verified": None,
        "same_invoice_commerce_receipt_present": None,
        "guest_delivery_core_order_fk_verified": None,
        "same_order_guest_outbox_present": None,
        "same_order_guest_receipt_mail_sent": None,
        "private_item_file_accessible": None,
        "legacy_commerce_entitlement_allowed": None,
        "walletless_same_buyer_download_allowed": None,
        "actual_buyer_authenticated_get_performed": False,
        "independent_buyer_acknowledged_delivery": False,
        "selected_order_fresh_solidity_checked": False,
        "production_db_or_files_changed": False,
    }


def _asset_exists(item):
    try:
        from mpw_commerce.downloads import _private_file
    except (ImportError, AttributeError):
        return None
    try:
        _private_file(item)  # stat/resolve only; NEVER open or read contents.
        return True
    except (FileNotFoundError, OSError, ValueError):
        return False
    except Exception:
        return None


def _legacy_access(item, buyer_id):
    try:
        from mpw_commerce.entitlements import can_access_purchased_digital_item
        return can_access_purchased_digital_item(item.pk, buyer_id) is True
    except Exception:
        return None


def _walletless_access(intent, buyer_id):
    try:
        from services.mpw_walletless_commercial_intent import commercial_buyer_status
        value = commercial_buyer_status(intent.pk, buyer_id)
        if type(value) is not dict or type(value.get("can_download")) is not bool:
            return None
        return value["can_download"]
    except Exception:
        return None


def inspect_one():
    from core.models import PaymentIntent, OrderItem, LedgerEntry
    from core.crown_tron_receipts import verified_walletless_credit

    result = _base()
    paid = PaymentIntent.objects.filter(
        provider=PROVIDER, status="paid",
    ).select_related("order__customer").order_by("pk")
    result["paid_scan_exhaustive"] = paid.count() <= MAX_PAID
    Fulfillment = _model("CommerceFulfillment")
    result["ready_fulfillment_model_fk_verified"] = exact_one_to_one(
        Fulfillment, "item", "core.orderitem",
    )
    if not result["ready_fulfillment_model_fk_verified"]:
        return result

    for intent in paid[:MAX_PAID]:
        order = intent.order
        if order.customer.is_staff is True or order.customer.is_superuser is True:
            continue  # nonstaff is still NOT proof of an independent external buyer
        if verified_walletless_credit(order, intent) is not True:
            continue
        if LedgerEntry.objects.filter(
            order_id=order.pk,
            entry_type__in=("refund", "reversal", "chargeback"),
        ).exists():
            continue
        items = OrderItem.objects.filter(
            order_id=order.pk,
        ).select_related("product").order_by("pk")
        within_limit = items.count() <= MAX_ITEMS
        for item in items[:MAX_ITEMS]:
            kind = product_kind(item.product.product_type)
            if kind == "game_cosmetic":
                continue
            if not Fulfillment.objects.filter(
                item_id=item.pk, kind="digital", status="ready",
            ).exists():
                continue

            result["same_order_candidate_found"] = True
            result["candidate_product_kind"] = kind
            try:
                from services.mpw_trx_guest_delivery import _guest_user
                result["candidate_account_kind"] = (
                    "guest" if _guest_user(order.customer) is True
                    else "registered_or_other"
                )
            except (ImportError, AttributeError):
                # No conclusion if the actual guest-account classifier is absent.
                result["candidate_account_kind"] = None
            result["item_scan_exhaustive"] = within_limit
            result["same_item_ready_digital_fulfillment"] = True
            result["private_item_file_accessible"] = _asset_exists(item)
            result["legacy_commerce_entitlement_allowed"] = _legacy_access(
                item, order.customer_id,
            )
            result["walletless_same_buyer_download_allowed"] = _walletless_access(
                intent, order.customer_id,
            )

            Invoice = _model("CommerceInvoice")
            result["exact_core_invoice_order_fk_verified"] = exact_one_to_one(
                Invoice, "order", "core.order",
            )
            if result["exact_core_invoice_order_fk_verified"]:
                invoice = Invoice.objects.filter(order_id=order.pk).first()
                result["same_order_commerce_invoice_present"] = invoice is not None
                result["same_order_commerce_invoice_paid"] = (
                    invoice.status == "paid" if invoice is not None else False
                )
                Receipt = _model("CommerceReceipt")
                result["exact_receipt_invoice_fk_verified"] = exact_one_to_one(
                    Receipt, "invoice", "mpw_commerce.commerceinvoice",
                )
                if result["exact_receipt_invoice_fk_verified"] and invoice is not None:
                    result["same_invoice_commerce_receipt_present"] = (
                        Receipt.objects.filter(invoice_id=invoice.pk).exists()
                    )

            Guest = _model("GuestTrxDelivery")
            result["guest_delivery_core_order_fk_verified"] = exact_one_to_one(
                Guest, "order", "core.order",
            )
            if result["guest_delivery_core_order_fk_verified"]:
                outbox = Guest.objects.filter(order_id=order.pk).first()
                result["same_order_guest_outbox_present"] = outbox is not None
                if result["candidate_account_kind"] is not None:
                    result["guest_outbox_missing_for_guest"] = (
                        result["candidate_account_kind"] == "guest" and outbox is None
                    )
                result["same_order_guest_receipt_mail_sent"] = (
                    outbox.receipt_state == "sent" if outbox is not None else False
                )
            return result
    return result


def main():
    if not ROOT.is_dir() or ROOT.is_symlink() or ROOT.resolve() != ROOT:
        report = _base()
        report["inspection_available"] = False
        report["error_type"] = "UntrustedTenant"
    else:
        try:
            os.chdir(ROOT)
            sys.path.insert(0, str(ROOT))
            os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
            import django
            django.setup()
            report = inspect_one()
            report["inspection_available"] = True
            report["error_type"] = None
        except Exception as exc:
            report = _base()
            report["inspection_available"] = False
            report["error_type"] = type(exc).__name__
    print("MPW_ONE_PAID_BUYER_ENTITLEMENT_READONLY=" + json.dumps(
        report, sort_keys=True, separators=(",", ":"),
    ))


if __name__ == "__main__":
    main()
