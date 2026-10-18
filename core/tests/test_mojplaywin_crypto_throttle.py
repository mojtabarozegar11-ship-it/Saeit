"""Limits are persistent, isolated to MojPlayWin and do not trust client IP headers."""
import pytest
from django.test import override_settings
from core.models import Order, Product, KnowledgeArticle
from core.mojplaywin_crypto_models import MojCryptoOffer, MojCryptoThrottle


@pytest.mark.django_db
def test_untrusted_forwarded_for_cannot_bypass_signup_throttle(client):
    with override_settings(ALLOWED_HOSTS=["mojplaywin.com"], MOJPLAYWIN_CRYPTO_ENABLED=True):
        for attempt in range(3):
            response = client.post(
                "/checkout/crypto/register/", {"username": "abc", "password1": "not-good"},
                HTTP_HOST="mojplaywin.com", REMOTE_ADDR="198.51.100.33",
                HTTP_X_FORWARDED_FOR=f"1.2.3.{attempt + 1}",
            )
            assert response.status_code == 200
        response = client.post(
            "/checkout/crypto/register/", {"username": "abc", "password1": "bad"},
            HTTP_HOST="mojplaywin.com", REMOTE_ADDR="198.51.100.33",
            HTTP_X_FORWARDED_FOR="9.9.9.9",
        )
        assert response.status_code == 429
        assert "Retry-After" in response
        assert "198.51.100.33" not in str(list(MojCryptoThrottle.objects.values()))


@pytest.mark.django_db
def test_checkout_fifth_per_user_allowed_sixth_blocked(client, django_user_model, tmp_path):
    merchant = django_user_model.objects.create_user("merchant-anti-abuse", password="testing123")
    buyer = django_user_model.objects.create_user("buyer-anti-abuse", password="testing123")
    article = KnowledgeArticle.objects.create(
        title="Approved digital file", slug="anti-abuse-download", content="content", published=True,
    )
    product = Product.objects.create(
        title="Digital file", owner=merchant, active=True, knowledge_article=article,
        product_type="ebook", currency="USD", price="2",
    )
    (tmp_path / "small.pdf").write_bytes(b"%PDF test")
    offer = MojCryptoOffer.objects.create(
        product=product, asset="ETH", active=True, atomic_amount="10000000000000000", private_file="small.pdf",
    )
    with override_settings(
        ALLOWED_HOSTS=["mojplaywin.com"], MOJPLAYWIN_CRYPTO_ENABLED=True,
        MOJPLAYWIN_PRIVATE_ASSET_ROOT=str(tmp_path),
        MOJPLAYWIN_ETH_ADDRESS="0x" + "1" * 40,
        MOJPLAYWIN_ETH_RPC_URL="https://eth.example.org",
    ):
        client.force_login(buyer)
        for _ in range(5):
            response = client.post(f"/checkout/crypto/buy/{offer.pk}/", HTTP_HOST="mojplaywin.com")
            assert response.status_code == 302
        response = client.post(f"/checkout/crypto/buy/{offer.pk}/", HTTP_HOST="mojplaywin.com")
        assert response.status_code == 429
        assert Order.objects.filter(customer=buyer).count() == 5


@pytest.mark.django_db
def test_crypto_abuse_limiting_not_exposed_to_other_domains(client):
    with override_settings(ALLOWED_HOSTS=["mojplaywin.com", "zomorodmelal.ir"], MOJPLAYWIN_CRYPTO_ENABLED=True):
        response = client.post(
            "/checkout/crypto/register/", {}, HTTP_HOST="zomorodmelal.ir",
        )
        assert response.status_code == 404
        assert MojCryptoThrottle.objects.count() == 0
