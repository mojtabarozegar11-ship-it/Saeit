from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import DatabaseError
from django.test import TestCase, override_settings
from django.urls import reverse

from core.models import Order, PaymentIntent, Product


@override_settings(ALLOWED_HOSTS=["mojplaywin.com", "www.mojplaywin.com", "zomorodmelal.ir", "testserver"])
class StoreControlTests(TestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_user(
            username="mpw-store-owner", password="irrelevant-test-only", is_staff=True, is_superuser=True
        )
        self.staff = get_user_model().objects.create_user(
            username="mpw-store-staff", password="irrelevant-test-only", is_staff=True
        )
        self.api = reverse("mpw_store_control_api")
        self.page = reverse("mpw_store_control")

    def test_host_and_owner_isolation(self):
        self.client.force_login(self.owner)
        self.assertEqual(self.client.get(self.api, HTTP_HOST="zomorodmelal.ir").status_code, 404)
        self.assertEqual(self.client.get(self.page, HTTP_HOST="zomorodmelal.ir").status_code, 404)
        self.client.force_login(self.staff)
        self.assertEqual(self.client.get(self.api, HTTP_HOST="mojplaywin.com").status_code, 403)
        self.client.logout()
        self.assertEqual(self.client.get(self.api, HTTP_HOST="mojplaywin.com").status_code, 403)

    def test_counts_are_read_only_and_site_scoped(self):
        Product.objects.create(title="Tagged item", product_type="digital",
            price=Decimal("19.00"), currency="USD", active=True,
            metadata={"tenant": "mojplaywin-main", "payment_live": True})
        Product.objects.create(title="Another site", product_type="digital",
            price=Decimal("0.00"), currency="IRR", active=False, metadata={})
        self.client.force_login(self.owner)
        response = self.client.get(self.api, HTTP_HOST="mojplaywin.com")
        self.assertEqual(response.status_code, 200)
        counts = response.json()["counts"]
        self.assertEqual(counts["shared_products"], 2)
        self.assertEqual(counts["mpw_explicitly_tagged"], 1)
        self.assertEqual(counts["mpw_checkout_candidates_unverified"], 1)
        self.assertEqual(counts["products_without_explicit_mpw_scope"], 1)
        self.assertEqual(response.json()["checkout_confirmed"], False)
        self.assertEqual(Product.objects.count(), 2)
        self.assertEqual(Order.objects.count(), 0)
        self.assertEqual(PaymentIntent.objects.count(), 0)
        self.assertIn("no-store", response["Cache-Control"])
        self.assertEqual(response["X-Robots-Tag"], "noindex, nofollow")
        html = self.client.get(self.page, HTTP_HOST="mojplaywin.com")
        self.assertEqual(html.status_code, 200)
        self.assertContains(html, "مرکز وضعیت فروشگاه")

    def test_post_rejected_and_database_failure_not_reported_as_zero(self):
        self.client.force_login(self.owner)
        self.assertEqual(self.client.post(self.api, HTTP_HOST="mojplaywin.com").status_code, 405)
        with patch("command_center.mpw_store_views.store_snapshot", side_effect=DatabaseError):
            response = self.client.get(self.api, HTTP_HOST="mojplaywin.com")
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["status"], "unavailable")
