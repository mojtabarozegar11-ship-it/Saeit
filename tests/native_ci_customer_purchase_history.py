"""Isolated, no-money tests for customer download recovery."""
from decimal import Decimal
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from core.models import KnowledgeArticle, Order, OrderItem, Product


@override_settings(
    MPW_COMMERCE_DOWNLOADS_ENABLED=True,
    ALLOWED_HOSTS=["mojplaywin.com", "www.mojplaywin.com", "testserver"],
)
class PurchaseHistoryTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.buyer = User.objects.create_user(username="buyer-recovery")
        self.other = User.objects.create_user(username="other-recovery")
        self.seller = User.objects.create_user(username="seller-recovery")
        self.article = KnowledgeArticle.objects.create(
            title="Chess sample", slug="chess-recovery-test",
            content="Isolated test only", published=True,
        )
        self.book = Product.objects.create(
            title="Private Chess Book", product_type="digital_book",
            price=Decimal("7.50"), currency="USD", owner=self.seller,
            active=True, knowledge_article=self.article,
        )
        self.order = Order.objects.create(
            customer=self.buyer, status="paid",
            total=Decimal("7.50"), currency="USD",
        )
        self.item = OrderItem.objects.create(
            order=self.order, product=self.book, quantity=1,
            unit_price=Decimal("7.50"), currency="USD",
        )
        self.url = reverse("mpw_commerce:purchases")
        self.client = Client()
        self.client.force_login(self.buyer)

    def get(self, *, host="mojplaywin.com", secure=True):
        return self.client.get(self.url, secure=secure, HTTP_HOST=host)

    def test_entitled_owner_gets_private_download_link(self):
        with patch(
            "mpw_commerce.purchase_history.can_access_purchased_digital_item",
            return_value=True,
        ) as permission:
            response = self.get()
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Private Chess Book")
        self.assertContains(
            response,
            reverse("mpw_commerce:download", kwargs={"item_id": self.item.pk}),
        )
        self.assertEqual(response["Cache-Control"], "private, no-store, max-age=0")
        permission.assert_called_once_with(self.item.pk, self.buyer.pk)

    def test_paid_row_alone_does_not_authorize_download(self):
        with patch(
            "mpw_commerce.purchase_history.can_access_purchased_digital_item",
            return_value=False,
        ):
            response = self.get()
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Download purchased file")
        self.assertNotContains(response, "Private Chess Book")

    def test_cannot_enumerate_another_buyers_items(self):
        self.client.force_login(self.other)
        with patch(
            "mpw_commerce.purchase_history.can_access_purchased_digital_item",
            return_value=True,
        ) as permission:
            response = self.get()
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Private Chess Book")
        permission.assert_not_called()

    def test_domain_tls_auth_and_switch_enforced(self):
        self.assertEqual(self.get(host="zomorodmelal.ir").status_code, 404)
        self.assertEqual(self.get(secure=False).status_code, 404)
        with override_settings(MPW_COMMERCE_DOWNLOADS_ENABLED=False):
            self.assertEqual(self.get().status_code, 404)
        self.client.logout()
        self.assertEqual(self.get().status_code, 302)

    def test_no_purchases_returns_safe_empty_state(self):
        self.order.status = "pending"
        self.order.save(update_fields=["status"])
        with patch(
            "mpw_commerce.purchase_history.can_access_purchased_digital_item",
            return_value=True,
        ) as permission:
            response = self.get()
        self.assertContains(response, "No verified downloadable purchases")
        permission.assert_not_called()
