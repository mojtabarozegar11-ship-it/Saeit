"""Moj Prop genuine funded Plan1 no-JS prelaunch identity, not checkout.

This suite is read-only: request factory only, no database rows, no invoices,
no authentication or email, no actual customer contact and no cryptocurrency.
"""
from django.test import RequestFactory, SimpleTestCase
from core.mojprop_accessible_intake import _safe_service_prefill, request_form


class MojPropPlanOneNoJsPrelaunchTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def _request(self, suffix="format=html&service=blueprint&package=moj-prop-01"):
        return self.factory.get("/moj-prop-intake/?" + suffix, secure=True)

    def test_01_correct_funded_plan1_code_and_not_educational_report(self):
        service, notes = _safe_service_prefill(self._request())
        self.assertEqual(service, "blueprint")
        self.assertIn("MOJ-PROP-01", notes)
        self.assertIn("funded-trading CHALLENGE", notes)
        self.assertNotIn("MOJPROP-STARTER30", notes)

    def test_02_prelaunch_does_not_imply_paid_order(self):
        _, notes = _safe_service_prefill(self._request())
        for term in ("NOT payable", "no payment", "no return is promised"):
            self.assertIn(term, notes)

    def test_03_no_capital_guarantee(self):
        _, notes = _safe_service_prefill(self._request())
        self.assertIn("USD 100 account after passing", notes)
        self.assertIn("independent capital, broker agreement", notes)

    def test_04_actual_newline_for_readability(self):
        _, notes = _safe_service_prefill(self._request())
        self.assertIn("time).\nPlease send", notes)
        self.assertNotIn("time).\\nPlease send", notes)

    def test_05_html_get_provides_real_plan1_and_csrf(self):
        response = request_form(self._request())
        html = response.content.decode("utf-8")
        self.assertEqual(response.status_code, 200)
        self.assertIn("MOJ-PROP-01 funded-trading challenge", html)
        self.assertIn('name="csrfmiddlewaretoken"', html)
        self.assertIn('action="/moj-prop-intake/?format=html"', html)
        self.assertIn('name="consent"', html)
        self.assertIn("This form takes no payment", html)

    def test_06_html_excludes_old_educational_offer_when_plan1_selected(self):
        html = request_form(self._request()).content.decode("utf-8")
        self.assertNotIn("Starter30 is a", html)
        self.assertNotIn("ten-session simulated journal", html)
        self.assertIn("two evaluation stages are simulated", html)

    def test_07_private_no_store_and_no_index(self):
        response = request_form(self._request())
        self.assertIn("no-store", response["Cache-Control"])
        self.assertIn("noindex", response["X-Robots-Tag"])
        self.assertEqual(response["X-Frame-Options"], "DENY")

    def test_08_duplicate_package_rejected(self):
        service, notes = _safe_service_prefill(self._request(
            "service=blueprint&package=moj-prop-01&package=moj-prop-01"))
        self.assertIsNone(service)
        self.assertEqual(notes, "")

    def test_09_duplicate_service_rejected(self):
        service, notes = _safe_service_prefill(self._request(
            "service=blueprint&service=signals&package=moj-prop-01"))
        self.assertIsNone(service)
        self.assertEqual(notes, "")

    def test_10_package_only_works_with_correct_route(self):
        for route in ("signals", "gold-brief", "digital"):
            with self.subTest(route=route):
                service, notes = _safe_service_prefill(self._request(
                    "service=" + route + "&package=moj-prop-01"))
                self.assertIsNone(service)
                self.assertEqual(notes, "")

    def test_11_wrong_sku_and_case_fail_closed(self):
        for product in ("moj-prop-02", "MOJ-PROP-01", "moj_prop_01",
                        "starter30", "moj-prop-01%0A"):
            with self.subTest(product=product):
                service, notes = _safe_service_prefill(self._request(
                    "service=blueprint&package=" + product))
                self.assertIsNone(service)
                self.assertEqual(notes, "")

    def test_12_post_never_uses_querystring_to_create_entitlement(self):
        req = self.factory.post(
            "/moj-prop-intake/?format=html&service=blueprint&package=moj-prop-01",
            data={"service": "blueprint"}, secure=True,
        )
        self.assertEqual(_safe_service_prefill(req), (None, ""))

    def test_13_other_general_manual_requests_not_mislabeled(self):
        response = request_form(self._request("format=html&service=blueprint"))
        html = response.content.decode("utf-8")
        self.assertNotIn("MOJ-PROP-01 funded-trading challenge", html)

    def test_14_starter_educational_query_never_becomes_plan1(self):
        service, notes = _safe_service_prefill(
            self._request("service=blueprint&package=starter-30-trx"))
        self.assertEqual(service, "blueprint")
        self.assertIn("MOJPROP-STARTER30", notes)
        self.assertNotIn("Prelaunch interest only: MOJ-PROP-01", notes)
