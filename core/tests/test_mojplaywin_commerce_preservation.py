"""MojPlayWin storefront render-only checks. No real payments, DB writes or wallet calls."""
from pathlib import Path
from unittest.mock import MagicMock, patch

from django.test import RequestFactory, SimpleTestCase, override_settings

from core.commerce_views import store_home
from core.models import Order, OrderItem, PaymentIntent, Product
from core.mojplaywin_views import PRODUCTS
from core.mojplaywin_views import store as mojplaywin_store


ROOT = Path(__file__).resolve().parents[2]
STORE = ROOT / "core/templates/mojplaywin/store.html"
SHARED_COMMERCE = ROOT / "core/commerce_views.py"


@override_settings(ALLOWED_HOSTS=["mojplaywin.com", "www.mojplaywin.com", "zomorodmelal.ir"])
class MojPlayWinCommercePreservationTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def test_live_store_dispatch_remains_main_host_only_and_read_only(self):
        # SimpleTestCase fails if the view unexpectedly queries the database.
        with patch("core.mojplaywin_views.render", side_effect=lambda request, template, context: (template, context)):
            for host in ("mojplaywin.com", "www.mojplaywin.com"):
                with self.subTest(host=host):
                    request = self.factory.get("/store/", HTTP_HOST=host)
                    template, context = store_home(request)
                    self.assertEqual(template, "mojplaywin/store.html")
                    self.assertIs(context["products"], PRODUCTS)
                    self.assertEqual(len(context["products"]), 6)

    def test_original_store_view_keeps_identity_of_editorial_cards(self):
        names = [(item["title"], item["url"]) for item in PRODUCTS]
        self.assertEqual(names, [
            ("The Science and Practice of Chess Improvement", "/store/"),
            ("Taniya and the Little Baker Worms", "/taniya/"),
            ("Farm Enterprise Economics Toolkit", "/ventures/agriculture/"),
            ("Applied AI Learning Path", "/knowledge/"),
            ("Original Browser Games", "/studio/"),
            ("Research & Digital Project Services", "/company/"),
        ])
        with patch("core.mojplaywin_views.render", side_effect=lambda request, template, context: (template, context)):
            template, context = mojplaywin_store(self.factory.get("/store/", HTTP_HOST="mojplaywin.com"))
            self.assertIs(context["products"], PRODUCTS)

    def test_six_featured_illustrations_are_unique_existing_static_assets(self):
        # Only editorial thumbnails: the actual database Product records are untouched.
        files = [item["image"] for item in PRODUCTS]
        self.assertEqual(len(files), 6)
        self.assertEqual(len(set(files)), 6, "No repeated featured thumbnails")
        for name in files:
            with self.subTest(image=name):
                self.assertTrue(name.startswith("site/heroes/"))
                self.assertTrue((ROOT / "core/static" / name).is_file())

    def test_original_non_main_host_store_keeps_database_product_query(self):
        fake_products = MagicMock()
        query = MagicMock()
        query.order_by.return_value = fake_products
        with patch("core.commerce_views.Product") as product_model:
            product_model.objects.filter.return_value = query
            with patch("core.commerce_views.render", side_effect=lambda request, template, context: (template, context)):
                template, context = store_home(self.factory.get("/store/", HTTP_HOST="zomorodmelal.ir"))
        product_model.objects.filter.assert_called_once_with(active=True)
        query.order_by.assert_called_once_with("-id")
        self.assertEqual(template, "core/store.html")
        self.assertIs(context["products"], fake_products)

    def test_store_has_no_new_payment_forms_or_fabricated_checkout(self):
        html = STORE.read_text(encoding="utf-8")
        for item in (
            "{% for product in products %}", "{% static product.image %}",
            "{{ product.title }}", "{{ product.category }}",
            "{{ product.text }}", 'href="{{ product.url }}"',
            "These featured collections are a discovery guide",
            "mw-store-grid", "mpw-store-help-title",
            '{% include "mojplaywin/footer.html" %}',
        ):
            self.assertIn(item, html)
        self.assertNotIn("<form", html.lower())
        self.assertNotIn("wallet_address", html.lower())
        self.assertNotIn('action="/api/payments/', html.lower())
        self.assertIn('id="mpw-catalog-title"', html)

    def test_existing_financial_models_remain_available(self):
        for model, fields in (
            (Product, ("title", "price", "currency", "active", "metadata")),
            (Order, ("customer", "status", "total", "currency")),
            (OrderItem, ("order", "product", "unit_price", "quantity")),
            (PaymentIntent, ("order", "amount", "currency", "idempotency_key", "provider", "status")),
        ):
            with self.subTest(model=model.__name__):
                for name in fields:
                    self.assertIsNotNone(model._meta.get_field(name))
        self.assertIn('Product.objects.filter(active=True).order_by("-id")', SHARED_COMMERCE.read_text(encoding="utf-8"))
