"""MojPlayWin native store launch safety: read-only, host-only and fail-closed."""
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch, MagicMock

from django.test import SimpleTestCase, RequestFactory, override_settings

from core.mojplaywin_catalog_readiness import (
    CRYPTO_RELEASE_FLAGS, existing_crypto_checkout_path,
    public_product_card, read_main_store_catalog, safe_main_path,
)


def product(**overrides):
    values = {
        "metadata": {"brand": "mojplaywin", "public_description": "Digital research guide",
                     "public_detail_path": "/products/guide/"},
        "title": "Research guide", "product_type": "ebook", "active": True,
        "knowledge_article": SimpleNamespace(published=True),
        "price": Decimal("14.00"), "currency": "USD",
        "pk": 23, "owner_id": 1, "knowledge_article_id": 1,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


class MojPlayWinSalesReadinessTests(SimpleTestCase):
    def test_main_site_path_validation_blocks_external_or_child_links(self):
        self.assertEqual(safe_main_path("/products/guide/", "/products/"), "/products/guide/")
        for path in ("https://other.example/pay", "//other.example", "/saman/",
                     "/mojtaba.roozegar/", "/products/../saman/",
                     "/products//admin/", "/products/buy/?token=private"):
            with self.subTest(path=path):
                self.assertEqual(safe_main_path(path, "/products/"), "")

    def test_paid_product_without_verified_provider_cannot_sell(self):
        card = public_product_card(product(), paid_enabled=True)
        self.assertEqual(card["price"], Decimal("14.00"))
        self.assertFalse(card["for_sale"])
        self.assertEqual(card["checkout_path"], "")

    def test_existing_eth_trx_gateway_requires_all_eight_existing_flags(self):
        meta = {
            "brand": "mojplaywin", "public_detail_path": "/products/guide/",
            "owner_sales_release": True, "factory_publication_permission": True,
            "asset_verified": True, "quality_approved": True,
            "license_verified": True,
            "mpw_commerce": {"enabled": True, "fulfillment": "digital",
                             "private_file": "private/approved.pdf"},
        }
        sale = product(metadata=meta, product_type="digital_book")
        self.assertFalse(public_product_card(sale, paid_enabled=False)["for_sale"])
        self.assertFalse(public_product_card(sale, paid_enabled=True)["for_sale"])
        flags = {name: True for name in CRYPTO_RELEASE_FLAGS}
        for key in CRYPTO_RELEASE_FLAGS:
            with self.subTest(missing_flag=key):
                missing = dict(flags)
                missing[key] = False
                with override_settings(**missing):
                    self.assertEqual(existing_crypto_checkout_path(sale), "")
        # Merely claiming the flags are ready cannot revive an unmerged
        # checkout app, unverified private asset or wallet proof.
        with override_settings(**flags):
            self.assertEqual(existing_crypto_checkout_path(sale), "")
            for key in ("owner_sales_release", "asset_verified",
                        "quality_approved", "license_verified"):
                m = dict(meta)
                m[key] = False
                self.assertEqual(existing_crypto_checkout_path(
                    product(metadata=m, product_type="digital_book")), "")

    def test_stripe_and_untrusted_payment_links_are_not_accepted(self):
        meta = {"brand": "mojplaywin", "public_checkout_path":
                "https://checkout.stripe.com/unverified",
                "gateway_merchant_verified": True, "owner_sales_release": True}
        item = public_product_card(product(metadata=meta), paid_enabled=True)
        self.assertFalse(item["for_sale"])
        self.assertEqual(item["checkout_path"], "")

    def test_no_unapproved_or_other_brand_data_appears(self):
        for item in (
            product(active=False), product(metadata={"brand": "zomorodmelal"}),
            product(knowledge_article=SimpleNamespace(published=False)),
            product(price=Decimal("-3")), product(currency="XYZ"),
        ):
            self.assertIsNone(public_product_card(item))

    @override_settings(MOJPLAYWIN_NATIVE_CATALOG_ENABLED=False)
    def test_default_catalog_mode_has_no_db_access(self):
        with patch("core.models.Product") as model:
            self.assertEqual(read_main_store_catalog(), [])
            model.objects.filter.assert_not_called()

    @override_settings(MOJPLAYWIN_NATIVE_CATALOG_ENABLED=True,
                       MOJPLAYWIN_NATIVE_CRYPTO_CHECKOUT_ENABLED=False)
    def test_enabled_catalog_is_select_only_and_tenant_scoped(self):
        prod = product()
        manager = MagicMock()
        manager.filter.return_value.select_related.return_value.order_by.return_value.__getitem__.return_value = [prod]
        with patch("core.models.Product.objects", manager):
            listing = read_main_store_catalog()
        self.assertEqual(len(listing), 1)
        self.assertFalse(listing[0]["for_sale"])
        manager.filter.assert_called_once_with(active=True,
                                                knowledge_article__published=True,
                                                metadata__brand="mojplaywin")

    def test_existing_homepage_and_other_sites_not_touched(self):
        from pathlib import Path
        root = Path(__file__).resolve().parents[2]
        module = (root / "core/mojplaywin_catalog_readiness.py").read_text()
        self.assertNotIn(".save(", module)
        self.assertNotIn(".update(", module)
        self.assertNotIn(".create(", module)
        self.assertNotIn("PaymentIntent", module)
        self.assertNotIn("OrderItem", module)
