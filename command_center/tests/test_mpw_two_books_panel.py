"""Two-book dashboard is factual, read-only and main-site staff protected."""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings

from core.models import KnowledgeArticle, Order, OrderItem, PaymentIntent, Product
from command_center.mpw_two_books_panel import _status_dict


@override_settings(ALLOWED_HOSTS=["mojplaywin.com", "zomorodmelal.ir", "testserver"])
class BookPanelTests(TestCase):
    def setUp(self):
        self.staff = get_user_model().objects.create_superuser(
            username="two_books_staff", email="admin@example.test", password="example-only")
        self.client = Client(HTTP_HOST="mojplaywin.com")
        self.client.force_login(self.staff)

    def test_missing_books_no_false_sales(self):
        data = _status_dict()
        self.assertEqual([row["id"] for row in data["books"]], [72, 225])
        self.assertFalse(any(row["sale_ready"] for row in data["books"]))
        self.assertEqual(data["orders_total"], 0)
        self.assertFalse(data["can_enable_payments"])
        self.assertIsNone(data["verified_customer_downloads"])
        self.assertFalse(data["real_settlement_test_verified"])

    def test_panel_access_is_main_site_only_and_is_private(self):
        response = self.client.get("/staff/command-center/mpw-two-books/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["X-Robots-Tag"], "noindex, nofollow")
        self.assertIn("no-store", response["Cache-Control"])
        self.assertContains(response, "The Science and Practice of Chess Improvement")
        other = Client(HTTP_HOST="zomorodmelal.ir")
        other.force_login(self.staff)
        self.assertEqual(other.get("/staff/command-center/mpw-two-books/").status_code, 404)
        anon = Client(HTTP_HOST="mojplaywin.com")
        self.assertNotEqual(anon.get("/staff/command-center/mpw-two-books/").status_code, 200)

    def test_existing_paid_order_is_counted_not_invented(self):
        article = KnowledgeArticle.objects.create(title="Book details", slug="chess-book-panel",
                                                  content="Verified only in test", published=True)
        book = Product.objects.create(id=72, title="The Science and Practice of Chess Improvement",
                                      product_type="book", price=Decimal("7.50"),
                                      currency="USD", active=False, owner=self.staff,
                                      knowledge_article=article, metadata={"asset_verified": True})
        order = Order.objects.create(customer=self.staff, total=Decimal("7.50"),
                                     currency="USD", status="paid")
        OrderItem.objects.create(order=order, product=book, quantity=1,
                                 unit_price=Decimal("7.50"), currency="USD")
        PaymentIntent.objects.create(order=order, amount=Decimal("7.50"), currency="USD",
                                     idempotency_key="test-unique-intent-72", status="paid",
                                     provider="test-only")
        data = _status_dict()
        self.assertEqual(data["orders_total"], 1)
        self.assertEqual(data["intents_total"], 1)
        self.assertEqual(data["books"][0]["paid_orders"], 1)
        self.assertFalse(data["books"][0]["sale_ready"])
        self.assertEqual(data["books"][0]["permissions"]["asset_verified"], True)
        self.assertFalse(data["real_settlement_test_verified"])
        self.assertIsNone(data["books"][0]["verified_downloads"])
