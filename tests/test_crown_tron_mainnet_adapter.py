"""Crown checkout: isolated Django DB exercises, never real customer payments.

RPC observations are controlled in tests. Green CI is not a live acceptance test.
"""
from contextlib import nullcontext
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from django.test import Client, override_settings
from core.models import (
    LedgerEntry, Order, OrderItem, PaymentIntent, PaymentWebhookEvent, Product,
)
from core.crown_fleet import owned_skus
from services.mpw_tron_independent_solidified_rpc import hex_to_tron_address
from services.mpw_trx_walletless_core import PaymentHold, SolidifiedTransfer
from services import mpw_crown_mainnet_checkout as shop

RECEIVER = hex_to_tron_address("41" + "11" * 20)
SENDER = hex_to_tron_address("41" + "22" * 20)
OTHER = hex_to_tron_address("41" + "33" * 20)
TX = "a" * 64


@pytest.fixture
def jet_buyer(django_user_model):
    buyer = django_user_model.objects.create_user(
        username="crown-verified-test-user", password="not-a-real-password",
    )
    other = django_user_model.objects.create_user(username="different-crown-user")
    product = Product.objects.create(
        title="Spectre", product_type="game_cosmetic", price=Decimal("4.99"),
        currency="USD", active=True, metadata={
            "crown_sku": "cd-spectre", "rights_cleared": True,
            "crown_checkout_verified": True,
        },
    )
    return buyer, other, product


@pytest.fixture
def approved_test_sources(monkeypatch):
    a = SimpleNamespace(source_id="node-a")
    b = SimpleNamespace(source_id="node-b")
    monkeypatch.setattr(shop, "_configuration", lambda: (RECEIVER, (a, b)))
    monkeypatch.setattr(shop, "_exclusive_allocation", nullcontext)
    monkeypatch.setattr(shop, "query_solidified_head", lambda _: 12345)
    monkeypatch.setattr(
        shop, "_quote",
        lambda: (Decimal("0.25"), datetime.now(timezone.utc)),
    )
    return a, b


def test_unapproved_configuration_fails_closed():
    assert shop.mainnet_checkout_ready() is False


def test_recipient_must_pass_tron_checksum():
    assert shop._address(RECEIVER) == RECEIVER
    with pytest.raises(PaymentHold):
        shop._address(RECEIVER[:-1] + ("A" if RECEIVER[-1] != "A" else "B"))


@pytest.mark.django_db
def test_default_sqlite_cannot_create_real_invoice(jet_buyer):
    buyer, _, product = jet_buyer
    with pytest.raises(PaymentHold):
        shop.start_crown_checkout(buyer_id=buyer.pk, product_id=product.pk)
    assert Order.objects.count() == 0


@pytest.mark.django_db
def test_retry_uses_same_intent_without_duplicate_order(jet_buyer, approved_test_sources):
    buyer, _, product = jet_buyer
    first = shop.start_crown_checkout(buyer_id=buyer.pk, product_id=product.pk)
    again = shop.start_crown_checkout(buyer_id=buyer.pk, product_id=product.pk)
    assert first == again
    assert Order.objects.count() == 1
    assert PaymentIntent.objects.count() == 1
    assert PaymentIntent.objects.get().status == "awaiting_chain"
    assert LedgerEntry.objects.count() == 0
    assert owned_skus(buyer) == []


@pytest.mark.django_db
@override_settings(ALLOWED_HOSTS=["mojplaywin.com"])
def test_owner_scoped_invoice_hides_amount_from_other_user(jet_buyer, approved_test_sources):
    buyer, other, product = jet_buyer
    url = shop.start_crown_checkout(buyer_id=buyer.pk, product_id=product.pk)
    customer = Client(HTTP_HOST="mojplaywin.com")
    customer.force_login(buyer)
    r = customer.get(url)
    assert r.status_code == 200
    assert b"TRON Mainnet" in r.content
    assert RECEIVER.encode() in r.content
    assert b"USDT" in r.content
    customer.force_login(other)
    assert customer.get(url).status_code == 404


def _mock_chain(monkeypatch, recipient=RECEIVER, amount_offset=0, mismatched_source=False):
    def lookup(provider, txid):
        intent = PaymentIntent.objects.select_related("order").get()
        invoice = shop._unpack(intent)
        return SolidifiedTransfer(
            source_id=provider.source_id, tx_hash=txid,
            network="tron-mainnet",
            recipient=OTHER if mismatched_source and provider.source_id == "node-b" else recipient,
            sender=SENDER,
            amount_sun=invoice.amount_sun + amount_offset,
            block_time=invoice.issued_at + timedelta(seconds=2),
            solidified=True, transfer_contract=True, execution_success=True,
        )
    monkeypatch.setattr(shop, "query_solidified_transfer", lookup)


@pytest.mark.django_db
@override_settings(ALLOWED_HOSTS=["mojplaywin.com"])
def test_double_solidified_receipt_unlocks_only_owner_once(
    jet_buyer, approved_test_sources, monkeypatch,
):
    buyer, other, product = jet_buyer
    url = shop.start_crown_checkout(buyer_id=buyer.pk, product_id=product.pk)
    _mock_chain(monkeypatch)
    customer = Client(HTTP_HOST="mojplaywin.com")
    customer.force_login(buyer)
    r = customer.post(url, {"txid": TX})
    assert r.status_code == 302
    assert customer.get(url).status_code == 200
    assert b"Payment verified" in customer.get(url).content
    assert owned_skus(buyer) == ["cd-spectre"]
    assert owned_skus(other) == []
    assert Order.objects.get().status == "paid"
    assert PaymentIntent.objects.get().status == "paid"
    assert PaymentWebhookEvent.objects.count() == 1
    assert LedgerEntry.objects.count() == 1
    # Replay MUST NOT grant twice or append another ledger credit.
    with pytest.raises(PaymentHold):
        shop._settle(PaymentIntent.objects.get().pk, buyer.pk, TX)
    assert LedgerEntry.objects.count() == 1


@pytest.mark.django_db
@override_settings(ALLOWED_HOSTS=["mojplaywin.com"])
@pytest.mark.parametrize("bad_case", ["amount", "recipient", "txid"])
def test_unverified_payment_never_grants_or_writes_credit(
    jet_buyer, approved_test_sources, monkeypatch, bad_case,
):
    buyer, _, product = jet_buyer
    url = shop.start_crown_checkout(buyer_id=buyer.pk, product_id=product.pk)
    _mock_chain(
        monkeypatch,
        amount_offset=1 if bad_case == "amount" else 0,
        mismatched_source=bad_case == "recipient",
    )
    client = Client(HTTP_HOST="mojplaywin.com")
    client.force_login(buyer)
    invalid = "not-a-txid" if bad_case == "txid" else TX
    assert client.post(url, {"txid": invalid}).status_code == 409
    assert Order.objects.get().status == "pending"
    assert owned_skus(buyer) == []
    assert not LedgerEntry.objects.exists()
    assert not PaymentWebhookEvent.objects.exists()


@pytest.mark.django_db
def test_tampered_mariadb_intent_never_settles(jet_buyer, approved_test_sources):
    buyer, _, product = jet_buyer
    shop.start_crown_checkout(buyer_id=buyer.pk, product_id=product.pk)
    intent = PaymentIntent.objects.get()
    intent.idempotency_key = "wrong"  # One-way reserved SUN fingerprint.
    intent.save(update_fields=["idempotency_key"])
    with pytest.raises(PaymentHold):
        shop._unpack(intent)
    assert owned_skus(buyer) == []


@pytest.mark.django_db
@override_settings(ALLOWED_HOSTS=["mojplaywin.com"],
                   CROWN_TRX_AUTO_DISCOVERY_ENABLED=True,
                   CROWN_TRX_INDEXER_KEY="test-indexer-key-for-tests")
def test_auto_discovery_requires_two_rpc_proofs_before_unlock(
    jet_buyer, approved_test_sources, monkeypatch,
):
    """Buyer does not supply TxID; indexed hash is independently reverified."""
    from django.core.cache import cache
    cache.clear()
    buyer, _, product = jet_buyer
    url = shop.start_crown_checkout(buyer_id=buyer.pk, product_id=product.pk)
    _mock_chain(monkeypatch)
    monkeypatch.setattr(shop, "discover_native_candidates", lambda invoice, key: [TX])
    client = Client(HTTP_HOST="mojplaywin.com")
    client.force_login(buyer)
    assert client.get(url).status_code == 302
    assert owned_skus(buyer) == ["cd-spectre"]
    assert client.get(url).status_code == 200
    assert LedgerEntry.objects.count() == 1


@pytest.mark.django_db
@override_settings(ALLOWED_HOSTS=["mojplaywin.com"],
                   CROWN_TRX_AUTO_DISCOVERY_ENABLED=True,
                   CROWN_TRX_INDEXER_KEY="test-indexer-key-for-tests")
def test_indexer_fake_candidate_does_not_grant_jet(
    jet_buyer, approved_test_sources, monkeypatch,
):
    from django.core.cache import cache
    cache.clear()
    buyer, _, product = jet_buyer
    url = shop.start_crown_checkout(buyer_id=buyer.pk, product_id=product.pk)
    _mock_chain(monkeypatch, amount_offset=1)
    monkeypatch.setattr(shop, "discover_native_candidates", lambda invoice, key: [TX])
    client = Client(HTTP_HOST="mojplaywin.com")
    client.force_login(buyer)
    assert client.get(url).status_code == 200
    assert owned_skus(buyer) == []
    assert not LedgerEntry.objects.exists()


@pytest.mark.django_db(transaction=True)
def test_actual_mariadb_named_lock_atomic_settlement(
    django_user_model, monkeypatch,
):
    """Only the isolated CI MariaDB, never live wallet funds or real nodes."""
    from django.db import connection
    if connection.vendor != "mysql":
        pytest.skip("Runs exclusively in the MariaDB service CI job")
    a = SimpleNamespace(source_id="node-a")
    b = SimpleNamespace(source_id="node-b")
    monkeypatch.setattr(shop, "_configuration", lambda: (RECEIVER, (a, b)))
    monkeypatch.setattr(shop, "query_solidified_head", lambda _: 1234)
    monkeypatch.setattr(
        shop, "_quote",
        lambda: (Decimal("0.25"), datetime.now(timezone.utc)),
    )
    buyer = django_user_model.objects.create_user(username="mariadb-buyer")
    product = Product.objects.create(
        title="Spectre", product_type="game_cosmetic", price="4.99",
        currency="USD", active=True,
        metadata={"crown_sku": "cd-spectre", "rights_cleared": True,
                  "crown_checkout_verified": True},
    )
    path = shop.start_crown_checkout(buyer_id=buyer.pk, product_id=product.pk)
    assert path.endswith("/")
    # Exercise actual SELECT GET_LOCK / RELEASE_LOCK and transaction.atomic.
    assert shop.start_crown_checkout(buyer_id=buyer.pk, product_id=product.pk) == path
    _mock_chain(monkeypatch)
    intent = PaymentIntent.objects.get()
    assert shop._settle(intent.pk, buyer.pk, TX) is True
    assert owned_skus(buyer) == ["cd-spectre"]
    assert Order.objects.filter(status="paid").count() == 1
    assert LedgerEntry.objects.count() == 1
    with pytest.raises(PaymentHold):
        shop._settle(intent.pk, buyer.pk, TX)
    assert LedgerEntry.objects.count() == 1


@pytest.mark.django_db
def test_legacy_paid_order_missing_payment_intent_fails_closed(jet_buyer):
    buyer, _, product = jet_buyer
    order = Order.objects.create(
        customer=buyer, status="paid", total=Decimal("4.99"), currency="USD",
    )
    OrderItem.objects.create(
        order=order, product=product, quantity=1,
        unit_price=Decimal("4.99"), currency="USD",
    )
    assert owned_skus(buyer) == []  # No real PaymentIntent or chain evidence.
