"""Host isolation, fail-closed checkout and no fake-settlement tests."""
from decimal import Decimal
from unittest.mock import patch
from pathlib import Path
import pytest
from django.test import override_settings
from core.models import LedgerEntry, Order, PaymentIntent, Product, KnowledgeArticle
from core.mojplaywin_crypto_models import MojCryptoOffer, MojCryptoInvoice
from core.mojplaywin_chain_verify import Proof, VerificationError
from core.mojplaywin_crypto_gateway import settle


@pytest.fixture
def buyer(django_user_model):
    return django_user_model.objects.create_user(username="crypto-buyer", password="safe-test-password")


@pytest.fixture
def priced_offer(django_user_model, tmp_path):
    owner = django_user_model.objects.create_user(username="crypto-owner", password="safe-test-password")
    (tmp_path / "sample.pdf").write_bytes(b"%PDF-1.4 test file")
    article = KnowledgeArticle.objects.create(title="Published checkout content", slug="crypto-approved-checkout", content="book content", published=True)
    product = Product.objects.create(
        title="Approved chess study", product_type="ebook", price="9.00",
        currency="USD", active=True, owner=owner, knowledge_article=article,
    )
    offer = MojCryptoOffer.objects.create(
        product=product, asset="ETH", atomic_amount=Decimal("10000000000000000"),
        active=True, private_file="sample.pdf",
    )
    return offer, tmp_path


@pytest.mark.django_db
def test_gateway_disabled_and_other_hosts_rejected(client, buyer, priced_offer):
    offer, folder = priced_offer
    client.force_login(buyer)
    with override_settings(ALLOWED_HOSTS=["testserver", "mojplaywin.com", "zomorodmelal.ir"], MOJPLAYWIN_CRYPTO_ENABLED=False):
        assert client.post(f"/checkout/crypto/buy/{offer.pk}/", HTTP_HOST="mojplaywin.com").status_code == 404
    with override_settings(
        ALLOWED_HOSTS=["testserver", "mojplaywin.com", "zomorodmelal.ir"],
        MOJPLAYWIN_CRYPTO_ENABLED=True,
        MOJPLAYWIN_PRIVATE_ASSET_ROOT=str(folder),
        MOJPLAYWIN_ETH_ADDRESS="0x" + "1" * 40,
        MOJPLAYWIN_ETH_RPC_URL="https://eth.example.org",
    ):
        assert client.post(f"/checkout/crypto/buy/{offer.pk}/", HTTP_HOST="zomorodmelal.ir").status_code == 404
    assert Order.objects.count() == 0


@pytest.mark.django_db
def test_invoice_created_from_server_price_and_owned_by_customer(client, buyer, priced_offer):
    offer, folder = priced_offer
    with override_settings(
        ALLOWED_HOSTS=["mojplaywin.com"],
        MOJPLAYWIN_CRYPTO_ENABLED=True,
        MOJPLAYWIN_PRIVATE_ASSET_ROOT=str(folder),
        MOJPLAYWIN_ETH_ADDRESS="0x" + "1" * 40,
        MOJPLAYWIN_ETH_RPC_URL="https://eth.example.org",
    ):
        client.force_login(buyer)
        response = client.post(
            f"/checkout/crypto/buy/{offer.pk}/",
            {"amount": "0", "status": "paid", "destination": "attacker"},
            HTTP_HOST="mojplaywin.com",
        )
        assert response.status_code == 302
        invoice = MojCryptoInvoice.objects.get()
        assert invoice.order.customer == buyer
        assert invoice.status == "awaiting_payment"
        assert invoice.order.status == "pending"
        assert invoice.order.total == Decimal("9.00")
        assert str(invoice.merchant_address) == "0x" + "1" * 40
        assert int(invoice.atomic_amount) > int(offer.atomic_amount)
        assert PaymentIntent.objects.get(order=invoice.order).status == "gateway_pending"
        denied = client.get(
            f"/checkout/crypto/invoice/{invoice.token}/download/",
            HTTP_HOST="mojplaywin.com",
        )
        assert denied.status_code == 404


@pytest.mark.django_db
def test_forged_chain_event_does_not_credit_customer(client, buyer, priced_offer):
    offer, folder = priced_offer
    with override_settings(
        ALLOWED_HOSTS=["mojplaywin.com"], MOJPLAYWIN_CRYPTO_ENABLED=True,
        MOJPLAYWIN_PRIVATE_ASSET_ROOT=str(folder),
        MOJPLAYWIN_ETH_ADDRESS="0x" + "1" * 40,
        MOJPLAYWIN_ETH_RPC_URL="https://eth.example.org",
    ):
        client.force_login(buyer)
        client.post(f"/checkout/crypto/buy/{offer.pk}/", HTTP_HOST="mojplaywin.com")
        invoice = MojCryptoInvoice.objects.get()
        response = client.post(
            "/api/payment-webhooks/",
            {},
            content_type="application/json",
            HTTP_HOST="mojplaywin.com",
            HTTP_X_PAYMENT_PROVIDER="onchain-eth",
        )
        assert response.status_code == 403
        invoice.order.refresh_from_db()
        assert invoice.order.status == "pending"


@pytest.mark.django_db
def test_chain_verified_payment_unlocks_once_and_replay_is_safe(client, buyer, priced_offer):
    offer, folder = priced_offer
    with override_settings(
        ALLOWED_HOSTS=["mojplaywin.com"],
        MOJPLAYWIN_CRYPTO_ENABLED=True,
        MOJPLAYWIN_PRIVATE_ASSET_ROOT=str(folder),
        MOJPLAYWIN_ETH_ADDRESS="0x" + "1" * 40,
        MOJPLAYWIN_ETH_RPC_URL="https://eth.example.org",
        MOJPLAYWIN_ETH_CONFIRMATIONS=12,
    ):
        client.force_login(buyer)
        client.post(f"/checkout/crypto/buy/{offer.pk}/", HTTP_HOST="mojplaywin.com")
        invoice = MojCryptoInvoice.objects.get()
        tx = "0x" + "a" * 64
        with patch("core.mojplaywin_crypto_gateway._verify_invoice", return_value=Proof(123456, 20)):
            first = settle(invoice.pk, tx)
            second = settle(invoice.pk, tx)
        assert first.status == "paid" and second.status == "paid"
        invoice.order.refresh_from_db()
        assert invoice.order.status == "paid"
        assert LedgerEntry.objects.filter(order=invoice.order).count() == 1
        response = client.get(
            f"/checkout/crypto/invoice/{invoice.token}/download/",
            HTTP_HOST="mojplaywin.com",
        )
        assert response.status_code == 200


@pytest.mark.django_db
def test_invalid_payment_proof_never_unlocks(client, buyer, priced_offer):
    offer, folder = priced_offer
    with override_settings(
        ALLOWED_HOSTS=["mojplaywin.com"],
        MOJPLAYWIN_CRYPTO_ENABLED=True,
        MOJPLAYWIN_PRIVATE_ASSET_ROOT=str(folder),
        MOJPLAYWIN_ETH_ADDRESS="0x" + "1" * 40,
        MOJPLAYWIN_ETH_RPC_URL="https://eth.example.org",
    ):
        client.force_login(buyer)
        client.post(f"/checkout/crypto/buy/{offer.pk}/", HTTP_HOST="mojplaywin.com")
        invoice = MojCryptoInvoice.objects.get()
        with patch("core.mojplaywin_crypto_gateway._verify_invoice", side_effect=VerificationError("wrong recipient")):
            response = client.post(
                f"/checkout/crypto/invoice/{invoice.token}/verify/",
                {"tx_hash": "0x" + "b" * 64}, HTTP_HOST="mojplaywin.com",
            )
        assert response.status_code == 409
        invoice.refresh_from_db()
        assert invoice.status == "awaiting_payment"
        assert LedgerEntry.objects.count() == 0
