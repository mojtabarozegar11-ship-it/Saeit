"""Filter known synthetic view requests, not proven payment/delivery facts.

No production data, request IP, email, wallet, cookie or raw user agent is
persisted. A browser-shaped user agent is never proof of a real human.
"""
from unittest.mock import patch

from django.test import RequestFactory, SimpleTestCase

from core.commerce_funnel import (
    _known_automated_observation,
    record_funnel_event,
)


class CommerceFunnelAutomationTests(SimpleTestCase):
    def setUp(self):
        self.requests = RequestFactory()
        self.browser = (
            "Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/128.0.0.0 Mobile Safari/537.36"
        )

    def test_known_scripts_and_site_monitoring_are_excluded_from_get_views(self):
        for user_agent in (
            "curl/8.18.0", "Python-urllib/3.9", "python-requests/2.31",
            "MojProp-Sitemap-Consistency-ReadOnly/1.0",
            "MPW-Protected-Attribution-Audit/1.0",
            "Mozilla/5.0 (compatible; AhrefsBot/7.0)",
            "facebookexternalhit/1.1", "HeadlessChrome/128.0.0.0",
        ):
            with self.subTest(user_agent=user_agent):
                request = self.requests.get(
                    "/mojprop-starter30-checkout/",
                    HTTP_USER_AGENT=user_agent,
                )
                with patch("core.commerce_funnel.CommerceFunnelEvent.objects.create") as create:
                    record_funnel_event(request, "begin_checkout")
                create.assert_not_called()
                self.assertTrue(_known_automated_observation(request, "begin_checkout"))

    def test_normal_browser_get_still_records_unverified_observation(self):
        request = self.requests.get(
            "/mojprop-starter30-checkout/?utm_source=facebook",
            HTTP_USER_AGENT=self.browser,
        )
        with patch("core.commerce_funnel.CommerceFunnelEvent.objects.create") as create:
            record_funnel_event(request, "begin_checkout")
        create.assert_called_once()
        self.assertEqual(create.call_args.kwargs["source"], "facebook")

    def test_unknown_user_agent_is_not_certified_human_or_suppressed(self):
        request = self.requests.get("/store/")
        self.assertFalse(_known_automated_observation(request, "view_store"))

    def test_validated_financial_events_are_not_lost_due_to_odd_user_agent(self):
        for event in ("invoice_created", "payment_confirmed",
                      "delivery_success", "delivery_failure"):
            with self.subTest(event=event):
                request = self.requests.post(
                    "/mojprop-starter30-checkout/",
                    HTTP_USER_AGENT="curl/8.18.0",
                )
                with patch("core.commerce_funnel.CommerceFunnelEvent.objects.create") as create:
                    record_funnel_event(request, event)
                create.assert_called_once()
                self.assertEqual(create.call_args.kwargs["event_name"], event)

    def test_unsupported_telemetry_never_persists(self):
        request = self.requests.get("/mojprop-starter30-checkout/",
                                    HTTP_USER_AGENT=self.browser)
        with patch("core.commerce_funnel.CommerceFunnelEvent.objects.create") as create:
            record_funnel_event(request, "invoice_created_unverified")
        create.assert_not_called()

    def test_known_automated_user_agent_cannot_suppress_unrelated_post_event(self):
        request = self.requests.post("/store/", HTTP_USER_AGENT="curl/8.18.0")
        with patch("core.commerce_funnel.CommerceFunnelEvent.objects.create") as create:
            record_funnel_event(request, "view_item")
        create.assert_called_once()
