"""Live purchase URL does not collect money or create orders until audited."""
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from django.test import Client, override_settings
from django.urls import reverse

from core.models import Order, Product


@pytest.fixture
def jet_and_buyer(django_user_model):
    buyer = django_user_model.objects.create_user(username="crown-paying-buyer", password="temporary-for-test")
    jet = Product.objects.create(
        title="X-22 Spectre", product_type="game_cosmetic",
        currency="USD", price="4.99", active=True,
        metadata={"crown_sku": "cd-spectre", "rights_cleared": True,
                  "crown_checkout_verified": True},
    )
    return buyer, jet


@pytest.mark.django_db
@override_settings(ALLOWED_HOSTS=["mojplaywin.com"], CROWN_STORE_ENABLED=False)
def test_disabled_checkout_blocks_get_post_and_writes_nothing(jet_and_buyer):
    buyer, jet = jet_and_buyer
    url = reverse("crown_cosmetic_checkout", kwargs={"product_id": jet.pk})
    assert url == f"/store/crown/{jet.pk}/checkout/"
    client = Client(HTTP_HOST="mojplaywin.com")
    client.force_login(buyer)
    assert client.get(url).status_code == 503
    assert client.post(url).status_code == 503
    assert Order.objects.count() == 0


@pytest.mark.django_db
@override_settings(ALLOWED_HOSTS=["mojplaywin.com"], CROWN_STORE_ENABLED=True, CROWN_PAYMENT_GATEWAY_APPROVED=True)
def test_missing_audited_adapter_blocks_even_approved_metadata(jet_and_buyer):
    buyer, jet = jet_and_buyer
    url = reverse("crown_cosmetic_checkout", kwargs={"product_id": jet.pk})
    client = Client(HTTP_HOST="mojplaywin.com")
    client.force_login(buyer)
    with patch("core.crown_checkout.import_module", side_effect=ImportError):
        assert client.get(url).status_code == 503
        assert client.post(url).status_code == 503
    assert Order.objects.count() == 0


@pytest.mark.django_db
@override_settings(ALLOWED_HOSTS=["mojplaywin.com"], CROWN_STORE_ENABLED=True, CROWN_PAYMENT_GATEWAY_APPROVED=True)
def test_post_only_dispatches_to_audited_server_adapter(jet_and_buyer):
    buyer, jet = jet_and_buyer
    url = reverse("crown_cosmetic_checkout", kwargs={"product_id": jet.pk})
    client = Client(HTTP_HOST="mojplaywin.com")
    client.force_login(buyer)
    adapter = SimpleNamespace(
        mainnet_checkout_ready=lambda: True,
        start_crown_checkout=lambda **kw: "/commerce/trx-easy/invoice/123/",
    )
    with patch("core.crown_checkout.import_module", return_value=adapter):
        response = client.get(url)
        assert response.status_code == 200
        assert "no-store" in response["Cache-Control"]
        assert b"4.99" in response.content
        result = client.post(url, {"amount": "-999", "receiver": "attacker", "txid": "fake"})
        assert result.status_code == 302
        assert result["Location"] == "/commerce/trx-easy/invoice/123/"
    assert Order.objects.count() == 0  # Only provider can ever create orders.


@pytest.mark.django_db
@override_settings(ALLOWED_HOSTS=["mojplaywin.com"], CROWN_STORE_ENABLED=True, CROWN_PAYMENT_GATEWAY_APPROVED=True)
@pytest.mark.parametrize("invalid", [
    "https://attacker.invalid/pay", "//attacker.invalid/commerce/",
    "/commerce/../admin/", "/commerce/pay/?amount=0", "/admin/",
])
def test_bad_adapter_redirect_cannot_escape_store(jet_and_buyer, invalid):
    buyer, jet = jet_and_buyer
    client = Client(HTTP_HOST="mojplaywin.com")
    client.force_login(buyer)
    adapter = SimpleNamespace(
        mainnet_checkout_ready=lambda: True,
        start_crown_checkout=lambda **kw: invalid,
    )
    with patch("core.crown_checkout.import_module", return_value=adapter):
        r = client.post(reverse("crown_cosmetic_checkout", kwargs={"product_id": jet.pk}))
        assert r.status_code == 503
    assert Order.objects.count() == 0


@pytest.mark.django_db
@override_settings(ALLOWED_HOSTS=["mojplaywin.com"])
def test_different_brand_host_cannot_use_checkout(jet_and_buyer):
    _, jet = jet_and_buyer
    r = Client(HTTP_HOST="zomorodmelal.ir")
    # Django rejects a disallowed host before our explicit brand check.
    assert r.get(reverse("crown_cosmetic_checkout", kwargs={"product_id": jet.pk})).status_code == 400
