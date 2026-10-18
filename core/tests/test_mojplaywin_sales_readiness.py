"""MojPlayWin native store launch safety: read-only, host-only and fail-closed."""
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch, MagicMock

from django.test import SimpleTestCase, RequestFactory, override_settings

from core.mojplaywin_catalog_readiness import public_product_card, read_main_store_catalog, safe_main_path


def product(**overrides):
    values = {
        "metadata": {"brand": "mojplaywin", "public_description": "Digital research guide",
                     "public_detail_path": "/products/guide/"},
        "title": "Research guide", "product_type": "ebook", "active": True,
        "knowledge_article": SimpleNamespace(published=True),
        "price": Decimal("14.00"), "currency": "USD",
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

    def test_both_global_gate_and_four_product_attestations_are_required(self):
        meta = {
            "brand": "mojplaywin", "public_detail_path": "/products/guide/",
            "public_checkout_path": "/store/checkout/guide/",
            "gateway_merchant_verified": True, "payment_e2e_verified": True,
            "delivery_e2e_verified": True, "owner_sales_release": True,
        }
        sale = product(metadata=meta)
        self.assertFalse(public_product_card(sale, paid_enabled=False)["for_sale"])
        for field in ("gateway_merchant_verified", "payment_e2e_verified",
                      "delivery_e2e_verified", "owner_sales_release"):
            modified = dict(meta)
            modified[field] = False
            self.assertFalse(public_product_card(
                product(metadata=modified), paid_enabled=True)["for_sale"])
        allowed = public_product_card(sale, paid_enabled=True)
        self.assertTrue(allowed["for_sale"])
        self.assertEqual(allowed["checkout_path"], "/store/checkout/guide/")

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
                       MOJPLAYWIN_PAID_CHECKOUT_ENABLED=False)
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
