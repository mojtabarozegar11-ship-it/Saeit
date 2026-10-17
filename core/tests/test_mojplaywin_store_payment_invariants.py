"""Main-site redesign is strictly read-only with respect to financial records.

This runs only against Django's isolated temporary TEST database; no real
wallet, order, checkout, customer or product is accessed or modified.
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from core.models import Order, OrderItem, PaymentIntent, Product


@override_settings(ALLOWED_HOSTS=["testserver", "mojplaywin.com", "www.mojplaywin.com", "zomorodmelal.ir"])
class MojPlayWinStorePaymentInvariants(TestCase):
    @classmethod
    def setUpTestData(cls):
        user = get_user_model().objects.create_user(
            username="mpw_store_guard_fictional_customer",
            password="TEST_ONLY_RANDOM_NOT_A_REAL_CREDENTIAL",
        )
        cls.product = Product.objects.create(
            title="Original Protected Digital Product",
            product_type="digital",
            price=Decimal("7.50"),
            currency="USD",
            active=True,
            metadata={
                "sku": "TEST_PRODUCT_UNCHANGED",
                "download_policy": "test-only",
                "license": "FICTIONAL_TEST_RECORD",
            },
        )
        cls.order = Order.objects.create(
            customer=user,
            status="paid",
            total=Decimal("7.50"),
            currency="USD",
        )
        cls.order_item = OrderItem.objects.create(
            order=cls.order,
            product=cls.product,
            quantity=1,
            unit_price=Decimal("7.50"),
            currency="USD",
        )
        cls.payment_intent = PaymentIntent.objects.create(
            order=cls.order,
            amount=Decimal("7.50"),
            currency="USD",
            idempotency_key="mpw_test_payment_no_actual_transaction",
            status="confirmed",
            provider="ETH_TEST_FIXTURE",
            provider_reference="test-only-not-a-transaction",
        )

    def financial_snapshot(self):
        return {
            "products": list(Product.objects.order_by("id").values(
                "id", "title", "product_type", "price", "currency",
                "active", "owner_id", "knowledge_article_id", "metadata")),
            "orders": list(Order.objects.order_by("id").values(
                "id", "customer_id", "status", "total", "currency")),
            "order_items": list(OrderItem.objects.order_by("id").values(
                "id", "order_id", "product_id", "quantity", "unit_price", "currency")),
            "payment_intents": list(PaymentIntent.objects.order_by("id").values(
                "id", "order_id", "amount", "currency", "idempotency_key",
                "status", "provider", "provider_reference")),
        }

    def test_public_mojplaywin_pages_cannot_mutate_or_remove_products_or_payment_records(self):
        before = self.financial_snapshot()
        for path in ("/store/", "/", "/research/", "/ventures/ecommerce/"):
            with self.subTest(path=path):
                response = self.client.get(path, HTTP_HOST="mojplaywin.com")
                self.assertEqual(response.status_code, 200)
                self.assertEqual(self.financial_snapshot(), before)

    def test_existing_store_card_bindings_are_still_present(self):
        # Existing static featured products are design cards, not a replacement
        # for the protected Django Product inventory.
        from pathlib import Path
        path = Path(__file__).resolve().parents[1] / "templates" / "mojplaywin" / "store.html"
        source = path.read_text(encoding="utf-8")
        for token in ("{% for product in products %}", "{{ product.title }}",
                      "{{ product.url }}", "{{ product.text }}",
                      "{% static product.image %}"):
            self.assertIn(token, source)
