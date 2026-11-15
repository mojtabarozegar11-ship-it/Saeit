#!/usr/bin/env python3
"""Owner-only, zero-write cPanel diagnostic of *existing* TRX payment evidence.

No new invoice, charge, chain request, email, user creation or payment state
transition. Prints contract booleans only: never names, emails, raw addresses,
amounts, transaction hashes, secrets, numeric sales totals or source code.
A positive persisted receipt flag is NOT independent live-chain finality.
"""
from __future__ import annotations

import hashlib
import inspect
import json
import os
import sys
from pathlib import Path

HOST_ROOT = Path("/home/zomorod2/Saeit-staging")
PROVIDER = "mpw_walletless_trx_v1"
MAX_REVIEW = 25
CANARY_FLAG = "MPW_WALLETLESS_TRX_MERCHANT_CANARY_PASSED"
PUBLIC_FLAG = "MPW_WALLETLESS_TRX_PUBLIC_ENABLED"
ADDRESS = "THFNU1iEXHd71WjEgjqUksd2UnMg2pUi73"


def analyze_gate_source(source: str) -> dict:
    """A direct source mention only; no ungrounded promise about helper logic."""
    if type(source) is not str or not source:
        return {"source_available": False, "direct_canary_reference": False,
                "direct_public_reference": False, "source_hash_present": False}
    return {
        "source_available": True,
        "direct_canary_reference": CANARY_FLAG in source,
        "direct_public_reference": PUBLIC_FLAG in source,
        "source_hash_present": True,
    }


def classify_payment_evidence(*, paid_intent_present, stored_receipt_found,
                              recorded_delivery_present, scope_exhaustive):
    """Separate durable bookkeeping from actual delivered purchase and RPC."""
    return {
        "paid_intent_present": paid_intent_present is True,
        "stored_verified_receipt_contract_present": stored_receipt_found is True,
        "any_delivery_event_recorded_unattributed": recorded_delivery_present is True,
        "paid_receipt_review_exhaustive": scope_exhaustive is True,
        "independent_current_chain_finality_checked": False,
        "specific_customer_receipt_and_delivery_matched": False,
        "new_customer_payments_created": False,
        "revenue_amount_assessed": False,
    }


def _read_existing_receipt_state():
    """Inspect only existing persisted status, even if a verifier is not deployed."""
    from core.models import PaymentIntent

    paid = PaymentIntent.objects.filter(provider=PROVIDER, status="paid")
    # Boolean presence; no paid count or buyer fields printed to public CI.
    has_paid = paid.exists()
    has_more_than_review_cap = paid.count() > MAX_REVIEW

    validator = None
    receipt_validator_available = False
    receipt_error_type = None
    try:
        from core.crown_tron_receipts import verified_walletless_credit
        validator = verified_walletless_credit
        receipt_validator_available = callable(validator)
    except ImportError as exc:
        receipt_error_type = type(exc).__name__

    receipt_found = False
    if receipt_validator_available:
        for intent in paid.select_related("order").order_by("pk")[:MAX_REVIEW]:
            try:
                if validator(intent.order, intent) is True:
                    receipt_found = True
            except (ValueError, TypeError, AttributeError, KeyError):
                continue

    recorded_delivery = False
    delivery_event_model_available = False
    try:
        from core.models import CommerceFunnelEvent
        delivery_event_model_available = True
        recorded_delivery = CommerceFunnelEvent.objects.filter(
            event_name="delivery_success"
        ).exists()
    except ImportError:
        pass

    record = classify_payment_evidence(
        paid_intent_present=has_paid,
        stored_receipt_found=receipt_found,
        recorded_delivery_present=recorded_delivery,
        scope_exhaustive=not has_more_than_review_cap,
    )
    record["paid_intent_model_available"] = True
    record["stored_receipt_validator_available"] = receipt_validator_available
    record["stored_receipt_validator_error_type"] = receipt_error_type
    record["delivery_event_model_available"] = delivery_event_model_available
    return record


def main():
    if not HOST_ROOT.is_dir() or HOST_ROOT.is_symlink():
        raise SystemExit("LIVE_ROOT_MISMATCH")
    if HOST_ROOT.resolve() != HOST_ROOT:
        raise SystemExit("UNEXPECTED_LIVE_ROOT")
    os.chdir(HOST_ROOT)
    sys.path.insert(0, str(HOST_ROOT))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    try:
        import django
        django.setup()
        from django.conf import settings
        from django.db import connection
        from services.mpw_walletless_commercial_intent import _commercial_db
        from services.mpw_trx_commercial_web import _configured_receiver
    except Exception as exc:
        print("MPW_TRX_CANARY_RECEIPT_READONLY_SETUP=" + type(exc).__name__)
        raise SystemExit(3) from None

    source = inspect.getsource(_commercial_db)
    try:
        _commercial_db(settings, connection)
        current_gate_passed = True
    except Exception:
        current_gate_passed = False
    try:
        receiver_match = _configured_receiver() == ADDRESS
    except Exception:
        receiver_match = False

    try:
        recorded = _read_existing_receipt_state()
        db_state_available = True
        db_error_type = None
    except Exception as exc:
        # The caller cannot treat an unavailable DB as zero paid customers.
        recorded = classify_payment_evidence(
            paid_intent_present=False, stored_receipt_found=False,
            recorded_delivery_present=False, scope_exhaustive=False,
        )
        db_state_available = False
        db_error_type = type(exc).__name__

    report = {
        "schema": "mpw.trx.canary.existing_receipts.readonly.v1",
        "read_only": True,
        "merchant_host": "mojplaywin.com",
        "receiver_matches_owner_qr": receiver_match,
        "public_enabled": getattr(settings, PUBLIC_FLAG, None) is True,
        "merchant_canary_passed": getattr(settings, CANARY_FLAG, None) is True,
        "commercial_guard_currently_allows": current_gate_passed,
        "possible_release_mismatch": (
            getattr(settings, PUBLIC_FLAG, None) is True
            and getattr(settings, CANARY_FLAG, None) is not True
            and current_gate_passed
        ),
        "commercial_guard_source": analyze_gate_source(source),
        "commercial_guard_sha256": hashlib.sha256(source.encode("utf-8")).hexdigest(),
        "db_state_available": db_state_available,
        "db_error_type": db_error_type,
        "stored_paid_evidence": recorded,
        "no_wallet_or_customer_data_printed": True,
        "no_host_changes_or_financial_writes": True,
    }
    print("MPW_TRX_CANARY_RECEIPT_READONLY="
          + json.dumps(report, sort_keys=True))


if __name__ == "__main__":
    main()
