from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from django.contrib.auth.models import AnonymousUser
from django.test import RequestFactory, override_settings

from core.crown_fleet import catalogue, fleet, owned_skus
from core.models import LedgerEntry, Order, OrderItem, PaymentIntent, Product


@pytest.fixture
def purchase(django_user_model):
    user = django_user_model.objects.create_user(username="pilot")
    p = Product.objects.create(title="Spectre", product_type="game_cosmetic", price="4.00", currency="USD", active=True,
        metadata={"crown_sku": "cd-spectre", "crown_checkout_verified": True, "rights_cleared": True})
    o = Order.objects.create(customer=user, status="paid", total="4.00", currency="USD")
    item = OrderItem.objects.create(order=o, product=p, quantity=1, unit_price="4.00", currency="USD")
    intent = PaymentIntent.objects.create(order=o, amount="4.00", currency="USD", status="succeeded", provider="tron", provider_reference="chain-proof", idempotency_key="crown-one")
    ledger = LedgerEntry.objects.create(order=o, payment_intent=intent, entry_type="payment", amount="4.00", currency="USD", reference="verified-payment")
    return SimpleNamespace(user=user, p=p, o=o, item=item, intent=intent, ledger=ledger)


@pytest.mark.django_db
def test_verified_payment_restores_and_is_account_scoped(purchase, django_user_model):
    assert owned_skus(purchase.user) == ["cd-spectre"]
    assert owned_skus(AnonymousUser()) == []
    assert owned_skus(django_user_model.objects.create_user(username="other")) == []


@pytest.mark.django_db
@pytest.mark.parametrize("failure", ["unpaid", "pending", "underpaid", "overpaid", "no_ledger", "refund", "wrong_currency", "demo", "no_reference", "bad_item_total"])
def test_browser_or_incomplete_settlement_does_not_unlock(purchase, failure):
    x = purchase
    if failure == "unpaid":
        x.o.status = "pending"; x.o.save()
    elif failure == "pending":
        x.intent.status = "ready_for_gateway"; x.intent.save()
    elif failure in ("underpaid", "overpaid"):
        x.ledger.amount = Decimal("3.99") if failure == "underpaid" else Decimal("4.01"); x.ledger.save()
    elif failure == "no_ledger":
        x.ledger.delete()
    elif failure == "refund":
        LedgerEntry.objects.create(order=x.o, entry_type="refund", amount="4.00", currency="USD", reference="refund")
    elif failure == "wrong_currency":
        x.intent.currency = "TRX"; x.intent.save()
    elif failure == "demo":
        x.intent.provider = "demo"; x.intent.save()
    elif failure == "no_reference":
        x.intent.provider_reference = ""; x.intent.save()
    elif failure == "bad_item_total":
        x.item.unit_price = Decimal("2.00"); x.item.save()
    assert owned_skus(x.user) == []


@pytest.mark.django_db
@override_settings(CROWN_STORE_ENABLED=True)
def test_catalogue_requires_checkout_verification_and_unambiguous_sku(purchase):
    # An approved product still cannot expose a dead or guessed payment link.
    assert catalogue()[0]["available"] is False
    assert catalogue()[0]["checkout"] is None
    with patch("core.crown_fleet.gateway_ready", return_value=True), patch("core.crown_fleet.reverse", return_value=f"/store/crown/{purchase.p.pk}/checkout/"):
        item = catalogue()[0]
        assert item["available"] is True
        assert item["checkout"] == f"/store/crown/{purchase.p.pk}/checkout/"
        purchase.p.metadata["crown_checkout_verified"] = False; purchase.p.save()
        assert catalogue()[0]["available"] is False
        purchase.p.metadata["crown_checkout_verified"] = True; purchase.p.save()
        Product.objects.create(title="duplicate", product_type="game_cosmetic", active=True, price="4.00", currency="USD", metadata=purchase.p.metadata)
        assert catalogue()[0]["available"] is False

@pytest.mark.django_db
@override_settings(CROWN_STORE_ENABLED=True)
def test_checkout_must_be_local_store_route(purchase):
    for invalid in ("https://other.example/checkout/", "//other.example/store/", "/admin/", "/store/../admin/"):
        with patch("core.crown_fleet.gateway_ready", return_value=True), patch("core.crown_fleet.reverse", return_value=invalid):
            assert catalogue()[0]["available"] is False
            assert catalogue()[0]["checkout"] is None



@pytest.mark.django_db
@override_settings(CROWN_STORE_ENABLED=False, ALLOWED_HOSTS=["mojplaywin.com"])
def test_no_live_sale_by_default_and_no_cache(purchase):
    assert catalogue()[0]["available"] is False
    r = RequestFactory().get("/api/crown-defender/fleet/", HTTP_HOST="mojplaywin.com")
    r.user = purchase.user
    response = fleet(r)
    assert response.status_code == 200
    assert "private" in response["Cache-Control"] and "no-store" in response["Cache-Control"]
    assert response["Vary"] == "Cookie"
