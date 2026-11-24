"""Ensure accessible research enquiries preserve canonical plan and quote scope."""
from django.test import RequestFactory, SimpleTestCase

from core.mojprop_accessible_intake import _safe_service_prefill, request_form
from services.mojtaba_signal_catalog import PLANS


class SignalAccessiblePlanIntakeTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def test_all_plans_use_server_catalog_prices(self):
        for code, plan in PLANS.items():
            with self.subTest(code=code):
                request = self.factory.get(
                    "/moj-prop-intake/", {"service": "signals", "plan": code, "price": "0.01"}
                )
                selected, notes = _safe_service_prefill(request)
                self.assertEqual(selected, "signals")
                self.assertEqual(
                    notes.splitlines()[0],
                    f"Requested educational plan: {code} (indicative USD {plan.price_usd:.2f}; written quote required)",
                )
                self.assertNotIn("0.01", notes)
                self.assertIn("unpaid request", notes)

    def test_unknown_duplicate_and_free_hint_never_quote_paid_plan(self):
        for suffix in ("plan=bad", "plan=education-weekly&plan=education-monthly",
                       "plan=education-weekly&tier=free"):
            request = self.factory.get("/moj-prop-intake/?service=signals&" + suffix)
            selected, notes = _safe_service_prefill(request)
            self.assertEqual(selected, "signals")
            self.assertNotIn("Requested educational plan:", notes)

    def test_direct_form_has_plan_links_and_one_time_purchase_link(self):
        request = self.factory.get("/moj-prop-intake/?service=signals")
        response = request_form(request)
        html = response.content.decode()
        for code in PLANS:
            self.assertIn("service=signals&amp;plan=" + code, html)
        self.assertIn("/commerce/book/1467/", html)
        self.assertIn("csrfmiddlewaretoken", html)
        self.assertIn("no charge", html)
        self.assertNotIn("/commerce/trx-easy/start/", html)

    def test_other_service_does_not_gain_signal_checkout_link(self):
        request = self.factory.get("/moj-prop-intake/?service=brief&plan=education-weekly")
        self.assertNotIn("/commerce/book/1467/", request_form(request).content.decode())
