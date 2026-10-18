"""Customer-facing sale and checkout must match the two exact approved files."""
import pytest
from django.test import override_settings

from core.models import Product
from core.mojplaywin_crypto_models import MojCryptoOffer
from core.mojplaywin_discount_books import DISCOUNT_BOOKS


@pytest.mark.django_db
@pytest.mark.parametrize("which", [0, 1])
def test_book_sale_checkout_is_only_visible_with_exact_sale_price_and_private_pdf(
    client, django_user_model, tmp_path, which
):
    book = DISCOUNT_BOOKS[which]
    owner = django_user_model.objects.create_user(username=f"seller-{which}", password="test-password")
    buyer = django_user_model.objects.create_user(username=f"buyer-{which}", password="test-password")
    pdf = tmp_path / book["private_pdf"]
    pdf.parent.mkdir(parents=True, exist_ok=True)
    pdf.write_bytes(b"%PDF-1.7\nA testable private finished book")
    product = Product.objects.create(
        title=book["title"], price=book["sale_usd"], currency="USD",
        product_type="ebook", owner=owner, active=True,
    )
    offer = MojCryptoOffer.objects.create(
        product=product, asset="TRX", atomic_amount="10000000",
        fulfillment_mode="download", private_file=book["private_pdf"], active=True,
    )
    with override_settings(
        ALLOWED_HOSTS=["mojplaywin.com"], MOJPLAYWIN_CRYPTO_ENABLED=True,
        MOJPLAYWIN_PRIVATE_ASSET_ROOT=str(tmp_path),
        MOJPLAYWIN_TRX_ADDRESS="THFNU1iEXHd71WjEgjqUksd2UnMg2pUi73",
    ):
        response = client.get("/store/", HTTP_HOST="mojplaywin.com")
        assert response.status_code == 200
        promo = next(x for x in response.context["products"] if x["title"] == book["title"])
        assert len(promo["payments"]) == 1
        assert promo["payments"][0]["id"] == offer.pk
        assert f"/checkout/crypto/buy/{offer.pk}/".encode() in response.content
        client.force_login(buyer)
        assert client.post(f"/checkout/crypto/buy/{offer.pk}/", HTTP_HOST="mojplaywin.com").status_code == 302

        product.price = book["sale_usd"] + 1
        product.save(update_fields=["price"])
        response = client.get("/store/", HTTP_HOST="mojplaywin.com")
        promo = next(x for x in response.context["products"] if x["title"] == book["title"])
        assert not promo.get("payments")
        assert client.post(f"/checkout/crypto/buy/{offer.pk}/", HTTP_HOST="mojplaywin.com").status_code == 404

        product.price = book["sale_usd"]
        product.save(update_fields=["price"])
        offer.private_file = "unapproved-ebook.pdf"
        offer.save(update_fields=["private_file"])
        assert client.post(f"/checkout/crypto/buy/{offer.pk}/", HTTP_HOST="mojplaywin.com").status_code == 404
