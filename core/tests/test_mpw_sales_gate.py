from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase, override_settings

from core.models import Product
from core.mpw_sales import eligible_for_checkout, verified_sales_offers


@override_settings(ALLOWED_HOSTS=["testserver", "mojplaywin.com", "zomorodmelal.ir"])
class MojPlayWinPaymentSalesGuardTests(TestCase):
    def make_product(self, *, meta=None, active=True, price="14.00"):
        if meta is None:
            meta = {
                "tenant":"mojplaywin-main",
                "payment_live":True,
                "rights_cleared":True,
                "publication_approved":True,
                "auto_settlement_verified":True,
            }
        return Product.objects.create(
            title="Digital test product", product_type="digital",
            currency="USD", price=Decimal(price), active=active, metadata=meta,
        )

    def test_product_requires_all_real_commercial_gates(self):
        product = self.make_product()
        self.assertTrue(eligible_for_checkout(product, lambda _: True))
        self.assertFalse(eligible_for_checkout(product, lambda _: {"ready":True}))
        for key in ("payment_live","rights_cleared","publication_approved",
                    "auto_settlement_verified","tenant"):
            with self.subTest(key=key):
                old=product.metadata
                product.metadata={k:v for k,v in old.items() if k!=key}
                self.assertFalse(eligible_for_checkout(product, lambda _:True))
                product.metadata=old
        product.active=False
        self.assertFalse(eligible_for_checkout(product, lambda _:True))
        product.active=True
        product.price=Decimal("0")
        self.assertFalse(eligible_for_checkout(product, lambda _:True))

    def test_untagged_or_other_site_product_never_listed(self):
        allowed=self.make_product()
        self.make_product(meta={"site":"zomorodmelal.ir","payment_live":True,
                                "rights_cleared":True,"publication_approved":True,
                                "auto_settlement_verified":True})
        self.make_product(active=False)
        with patch("core.mpw_sales._production_payment_verifier", return_value=lambda _:True), \
             patch("core.mpw_sales._checkout_url", side_effect=lambda pk:f"/store/product/{pk}/checkout/"):
            offers=verified_sales_offers()
        self.assertEqual([x["id"] for x in offers],[allowed.id])

    def test_missing_gateway_or_checkout_route_fails_closed(self):
        self.make_product()
        with patch("core.mpw_sales._production_payment_verifier",return_value=None):
            self.assertEqual(verified_sales_offers(),[])
        with patch("core.mpw_sales._production_payment_verifier",return_value=lambda _:True), \
             patch("core.mpw_sales._checkout_url",return_value=None):
            self.assertEqual(verified_sales_offers(),[])

    def test_public_store_keeps_existing_catalog_when_no_payment_is_verified(self):
        with patch("core.mpw_sales._production_payment_verifier",return_value=None):
            response=self.client.get("/store/",HTTP_HOST="mojplaywin.com")
        self.assertEqual(response.status_code,200)
        self.assertIn(b"INITIAL COLLECTION",response.content)
        self.assertNotIn(b'id="verified-sales"',response.content)
