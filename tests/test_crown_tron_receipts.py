"""Walletless TRX ledger receipt must be independently server-verified before use.

These are DB-contract tests, NOT evidence of a real mainnet transfer.
"""
import hashlib
import json
from decimal import Decimal

import pytest
from django.contrib.auth.models import AnonymousUser

from core.crown_fleet import owned_skus
from core.models import LedgerEntry, Order, OrderItem, PaymentIntent, PaymentWebhookEvent, Product

TX = "a" * 64
DIGEST = "b" * 64
RECEIVER = "T" + "A" * 33
PROVIDER = "mpw_walletless_trx_v1"


@pytest.fixture
def paid_walletless(django_user_model):
    user = django_user_model.objects.create_user(username="tron-buyer")
    product = Product.objects.create(
        title="Spectre", product_type="game_cosmetic", price="4.99",
        currency="USD", active=True,
        metadata={"crown_sku": "cd-spectre", "rights_cleared": True,
                  "crown_checkout_verified": True},
    )
    order = Order.objects.create(customer=user, status="paid", total="4.99", currency="USD")
    item = OrderItem.objects.create(order=order, product=product, quantity=1,
                                    unit_price="4.99", currency="USD")
    envelope = {"v": 1, "to": RECEIVER, "sun": 19960000, "rate": "0.25",
                "at": "2026-10-22T08:00:00+00:00"}
    idem = "wltrx1:" + hashlib.sha256(RECEIVER.encode("ascii")).hexdigest() + ":19960000"
    intent = PaymentIntent.objects.create(
        order=order, amount="4.99", currency="USD", status="paid",
        provider=PROVIDER, provider_reference=json.dumps(envelope), idempotency_key=idem,
    )
    event = PaymentWebhookEvent.objects.create(
        payment_intent=intent, provider=PROVIDER, event_id=TX,
        event_type="tron_finalized", status="processed", payload_hash=DIGEST,
    )
    ledger = LedgerEntry.objects.create(
        order=order, payment_intent=intent, entry_type="credit",
        amount="4.99", currency="USD",
        reference="walletless:tron-mainnet:" + TX,
        metadata={"payment_method": PROVIDER, "network": "tron-mainnet",
                  "tx_hash": TX, "sender": "T" + "B" * 33,
                  "evidence_digest": DIGEST, "walletless_receipt_event_id": event.pk},
    )
    return user, product, order, item, intent, event, ledger


@pytest.mark.django_db
def test_walletless_verified_receipt_restores_jet_to_buyer_only(paid_walletless, django_user_model):
    user, _, _, _, _, _, _ = paid_walletless
    assert owned_skus(user) == ["cd-spectre"]
    assert owned_skus(AnonymousUser()) == []
    assert owned_skus(django_user_model.objects.create_user(username="not-the-buyer")) == []


@pytest.mark.django_db
@pytest.mark.parametrize("failure", [
    "pending_intent", "wrong_provider", "empty_reference", "wrong_idempotency",
    "bad_invoice", "wrong_currency", "underpaid_order", "underpaid_ledger",
    "extra_order_item", "missing_event", "unprocessed_event", "bad_event_tx",
    "bad_digest", "wrong_ledger_reference", "wrong_network", "wrong_sender",
    "wrong_evidence_digest", "wrong_event_pk", "missing_ledger", "duplicated_credit",
    "refund", "reversal", "chargeback",
])
def test_incomplete_or_replayed_tron_receipt_never_unlocks(paid_walletless, failure):
    user, product, order, item, intent, event, ledger = paid_walletless
    if failure == "pending_intent":
        intent.status = "awaiting_chain"; intent.save(update_fields=["status"])
    elif failure == "wrong_provider":
        intent.provider = "demo"; intent.save(update_fields=["provider"])
    elif failure == "empty_reference":
        intent.provider_reference = ""; intent.save(update_fields=["provider_reference"])
    elif failure == "wrong_idempotency":
        intent.idempotency_key = "fake"; intent.save(update_fields=["idempotency_key"])
    elif failure == "bad_invoice":
        intent.provider_reference = json.dumps({"v": 1, "to": RECEIVER, "sun": 0, "rate": "0.25", "at": "2026-10-22"})
        intent.save(update_fields=["provider_reference"])
    elif failure == "wrong_currency":
        intent.currency = "TRX"; intent.save(update_fields=["currency"])
    elif failure == "underpaid_order":
        order.total = Decimal("5.00"); order.save(update_fields=["total"])
    elif failure == "underpaid_ledger":
        ledger.amount = Decimal("4.98"); ledger.save(update_fields=["amount"])
    elif failure == "extra_order_item":
        OrderItem.objects.create(order=order, product=product, quantity=1, unit_price="0.00", currency="USD")
    elif failure == "missing_event":
        event.delete()
    elif failure == "unprocessed_event":
        event.status = "received"; event.save(update_fields=["status"])
    elif failure == "bad_event_tx":
        event.event_id = "unverified"; event.save(update_fields=["event_id"])
    elif failure == "bad_digest":
        event.payload_hash = "not-a-proof"; event.save(update_fields=["payload_hash"])
    elif failure == "wrong_ledger_reference":
        ledger.reference = "walletless:other:" + TX; ledger.save(update_fields=["reference"])
    elif failure in ("wrong_network", "wrong_sender", "wrong_evidence_digest", "wrong_event_pk"):
        md = dict(ledger.metadata)
        md[{"wrong_network": "network", "wrong_sender": "sender",
            "wrong_evidence_digest": "evidence_digest",
            "wrong_event_pk": "walletless_receipt_event_id"}[failure]] = {
            "wrong_network": "tron-testnet", "wrong_sender": "",
            "wrong_evidence_digest": "c"*64, "wrong_event_pk": event.pk + 1,
        }[failure]
        ledger.metadata = md; ledger.save(update_fields=["metadata"])
    elif failure == "missing_ledger":
        ledger.delete()
    elif failure == "duplicated_credit":
        LedgerEntry.objects.create(order=order, payment_intent=intent, entry_type="credit",
                                   amount="4.99", currency="USD", reference="walletless:other-credit")
    elif failure in ("refund", "reversal", "chargeback"):
        LedgerEntry.objects.create(order=order, payment_intent=intent, entry_type=failure,
                                   amount="4.99", currency="USD", reference="walletless:"+failure)
    assert owned_skus(user) == []
