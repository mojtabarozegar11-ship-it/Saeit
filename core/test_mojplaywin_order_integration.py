"""Database-backed checkout regressions; no real payments or publication."""
from decimal import Decimal
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIRequestFactory, force_authenticate
from core.api import OrderViewSet
from core.models import KnowledgeArticle, Order, OrderItem, Product


class OrderCreationIntegrationTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="mpw_checkout_staff", password="test-only-password", is_staff=True
        )
        self.article = KnowledgeArticle.objects.create(
            title="Released product information",
            slug="mpw-checkout-integration-product",
            content="Verified description for the test product.",
            published=True,
        )
        self.product = Product.objects.create(
            title="Test digital product", product_type="software",
            price=Decimal("12.50"), currency="USD", active=True,
            knowledge_article=self.article, metadata={"brand_code": "mojplaywin"},
        )
        self.factory = APIRequestFactory()
        self.view = OrderViewSet.as_view({"post": "create"})

    def request(self, payload):
        req = self.factory.post("/api/orders/", payload, format="json")
        force_authenticate(req, user=self.user)
        return self.view(req)

    def test_creates_order_and_item_atomically(self):
        response = self.request({"product_id": self.product.pk, "quantity": 2})
        self.assertEqual(response.status_code, 201)
        order = Order.objects.get()
        item = OrderItem.objects.get()
        self.assertEqual(order.total, Decimal("25.00"))
        self.assertEqual(order.currency, "USD")
        self.assertEqual(order.customer_id, self.user.pk)
        self.assertEqual(item.quantity, 2)
        self.assertEqual(item.product_id, self.product.pk)

    def test_invalid_quantities_never_create_order(self):
        for quantity in (0, -1, 101, "abc"):
            with self.subTest(quantity=quantity):
                self.assertEqual(
                    self.request({"product_id": self.product.pk, "quantity": quantity}).status_code,
                    400,
                )
        self.assertFalse(Order.objects.exists())

    def test_inactive_or_unpublished_products_cannot_be_ordered(self):
        self.product.active = False
        self.product.save()
        self.assertEqual(self.request({"product_id": self.product.pk}).status_code, 404)
        self.product.active = True
        self.product.save()
        self.article.published = False
        self.article.save()
        self.assertEqual(self.request({"product_id": self.product.pk}).status_code, 404)
        self.assertFalse(Order.objects.exists())
