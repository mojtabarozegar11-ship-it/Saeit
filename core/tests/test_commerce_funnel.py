from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from command_center.commerce_funnel import commerce_funnel_api
from core.commerce_funnel import record_funnel_event
from core.models import CommerceFunnelEvent, Product


@override_settings(ALLOWED_HOSTS=["testserver", "mojplaywin.com"])
class CommerceFunnelTests(TestCase):
    def setUp(self):
        self.product = Product.objects.create(
            title="Test product", product_type="digital", price="4.00",
            currency="USD", active=True,
        )

    def test_event_is_bounded_and_contains_no_identity_fields(self):
        request = self.client.get(
            "/", {"utm_source": "newsletter", "utm_medium": "email", "utm_campaign": "spring"},
            HTTP_HOST="mojplaywin.com",
        ).wsgi_request
        record_funnel_event(request, "view_item", self.product)
        event = CommerceFunnelEvent.objects.get()
        self.assertEqual(event.source, "newsletter")
        self.assertFalse(hasattr(event, "email"))
        self.assertFalse(hasattr(event, "ip_address"))
        self.assertFalse(hasattr(event, "wallet_address"))

    def test_utm_email_and_full_url_are_rejected_before_storage(self):
        for candidate in ("customer@example.com", "https://example.com/?token=x",
                          "a b c", "<script>alert(1)</script>"):
            with self.subTest(candidate=candidate):
                request = self.client.get(
                    "/", {"utm_source": candidate}, HTTP_HOST="mojplaywin.com",
                ).wsgi_request
                record_funnel_event(request, "view_item", self.product)
                self.assertEqual(CommerceFunnelEvent.objects.order_by("-id").first().source, "")

    def test_oversized_campaign_value_is_not_silently_truncated(self):
        request = self.client.get(
            "/", {"utm_campaign": "x" * 81}, HTTP_HOST="mojplaywin.com",
        ).wsgi_request
        record_funnel_event(request, "view_item", self.product)
        self.assertEqual(CommerceFunnelEvent.objects.last().campaign, "")

    def test_normal_campaign_code_remains_trackable(self):
        request = self.client.get(
            "/", {"utm_source": "email_newsletter-2026", "utm_campaign": "book_v2"},
            HTTP_HOST="mojplaywin.com",
        ).wsgi_request
        record_funnel_event(request, "view_item", self.product)
        row = CommerceFunnelEvent.objects.last()
        self.assertEqual(row.source, "email_newsletter-2026")
        self.assertEqual(row.campaign, "book_v2")

    def test_store_page_does_not_depend_on_optional_funnel_module(self):
        """Missing live analytics must not turn the product store into HTTP 500."""
        from unittest.mock import patch
        from django.http import HttpResponse
        from django.test import RequestFactory
        from core.mojplaywin_views import store

        req = RequestFactory().get("/store/", HTTP_HOST="mojplaywin.com")
        with patch.dict("sys.modules", {"core.commerce_funnel": None}):
            with patch(
                "core.mojplaywin_views.render",
                return_value=HttpResponse("store available", status=200),
            ) as render_view:
                response = store(req)
        self.assertEqual(response.status_code, 200)
        render_view.assert_called_once()

    def test_store_page_survives_noncritical_telemetry_error(self):
        from unittest.mock import patch
        from django.http import HttpResponse
        from django.test import RequestFactory
        from core.mojplaywin_views import store

        req = RequestFactory().get("/store/", HTTP_HOST="mojplaywin.com")
        with patch(
            "core.commerce_funnel.record_funnel_event",
            side_effect=RuntimeError("optional metrics unavailable"),
        ):
            with patch(
                "core.mojplaywin_views.render",
                return_value=HttpResponse("store available", status=200),
            ) as render_view:
                response = store(req)
        self.assertEqual(response.status_code, 200)
        render_view.assert_called_once()

    def test_staff_summary_is_read_only_and_requires_staff(self):
        record_funnel_event(self.client.get("/", HTTP_HOST="mojplaywin.com").wsgi_request, "view_item", self.product)
        self.assertNotEqual(self.client.get("/staff/command-center/api/commerce-funnel/").status_code, 200)
        user = get_user_model().objects.create_superuser("owner", "owner@example.com", "safe-test-password")
        self.client.force_login(user)
        response = self.client.get("/staff/command-center/api/commerce-funnel/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["events"]["view_item"], 1)
