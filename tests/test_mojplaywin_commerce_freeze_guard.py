"""Unit tests for immutable crypto checkout & real-product preservation gate."""
from pathlib import Path
import unittest

from scripts import mojplaywin_commerce_freeze_guard as guard


class MojPlayWinCommerceFreezeTests(unittest.TestCase):
    def test_payment_orders_and_shared_deployment_files_are_protected(self):
        forbidden = (
            "config/urls.py", "core/commerce_views.py", "core/models.py",
            "core/admin.py", "core/migrations/0010_changed_products.py",
            "core/templates/core/store.html", "core/views.py",
            "core/templates/base.html", "scripts/deploy_mojplaywin_branding.py",
            "core/payment_gateway.py", "core/wallet_webhook.py",
            "core/checkout.py", "core/product_download.py",
            "payments/eth_checkout.py", "wallets/trx.json",
            "products/item-72.pdf", "orders/export.csv",
        )
        for filename in forbidden:
            with self.subTest(filename=filename):
                self.assertTrue(guard.forbidden_path(filename))

    def test_owned_design_assets_and_readonly_tests_can_change(self):
        permitted = (
            "core/templates/mojplaywin/store.html",
            "core/templates/mojplaywin/footer.html",
            "core/templates/brands/mojplaywin/base.html",
            "core/mojplaywin_views.py",
            "core/static/site/mojplaywin-atelier/digital-products.svg",
            "core/tests/test_mojplaywin_footer_2022.py",
            "scripts/mojplaywin_commerce_freeze_guard.py",
        )
        for filename in permitted:
            with self.subTest(filename=filename):
                self.assertFalse(guard.forbidden_path(filename))

    def test_product_catalog_must_match_exactly(self):
        existing = '''PRODUCTS = [
          {"title":"Book","price":7.5,"currency":"USD","url":"/store/book/","image":"a.webp"},
          {"title":"Game","price":3,"currency":"USD","url":"/games/","image":"b.webp"},
        ]
        '''
        self.assertEqual(guard.products_from_source(existing)[0]["price"], 7.5)
        changed_price = existing.replace('"price":7.5', '"price":8')
        changed_link = existing.replace('"/store/book/"', '"/new-checkout/"')
        self.assertNotEqual(guard.products_from_source(existing),
                            guard.products_from_source(changed_price))
        self.assertNotEqual(guard.products_from_source(existing),
                            guard.products_from_source(changed_link))

    def test_checkout_dispatch_must_be_exact(self):
        code1 = "def store(request):\n    return render(request, 'existing.html')\n"
        code2 = "def store(request):\n    return render(request, 'different.html')\n"
        self.assertNotEqual(guard.function_structure(code1, "store"),
                            guard.function_structure(code2, "store"))
        with self.assertRaises(ValueError):
            guard.function_structure(code1, "payment")

    def test_restyled_store_cannot_remove_real_product_field_bindings(self):
        good = " ".join(guard.PRODUCT_TEMPLATE_FIELDS)
        self.assertEqual(guard.test_template_bindings(good), [])
        removed = good.replace("{{ product.url }}", "/placeholder/")
        self.assertIn("{{ product.url }}", guard.test_template_bindings(removed))
        removed = good.replace("{{ product.title }}", "New Product")
        self.assertIn("{{ product.title }}", guard.test_template_bindings(removed))

    def test_immutable_policies_cover_entitlements_and_ledger(self):
        source = (Path(__file__).resolve().parents[1] / "core/models.py").read_text(encoding="utf-8")
        for model in ("class Product(", "class Order(", "class OrderItem(",
                      "class PaymentIntent(", "class PaymentWebhookEvent("):
            self.assertIn(model, source)


if __name__ == "__main__":
    unittest.main()
