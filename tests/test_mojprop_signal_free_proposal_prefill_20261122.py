"""Free Signal Desk enquiry prefill; never synthetic customers or payments.

Uses isolated RequestFactory and source-only response inspection. No POST is
sent to a live endpoint, and the test creates no rows, invoices or emails.
"""
from django.test import RequestFactory, SimpleTestCase

from core.mojprop_accessible_intake import _safe_service_prefill, request_form


class FreeSignalProposalPrefillTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def _get(self, query="format=html&service=signals"):
        return self.factory.get("/moj-prop-intake/?" + query, secure=True)

    def test_01_signal_request_prefills_editable_free_proposal(self):
        service, notes = _safe_service_prefill(self._get())
        self.assertEqual(service, "signals")
        self.assertGreaterEqual(len(notes), 20)
        self.assertIn("free written terms for the educational Signal Desk", notes)
        self.assertIn("market-scenario examples", notes)
        self.assertIn("not a paid subscription", notes)
        self.assertNotIn("MOJPROP-STARTER30", notes)
        self.assertNotIn("MOJ-PROP-01", notes)

    def test_02_real_html_keeps_csrf_and_required_opt_in(self):
        response = request_form(self._get())
        body = response.content.decode("utf-8")
        self.assertEqual(response.status_code, 200)
        self.assertIn('<option value="signals" selected>', body)
        self.assertIn("<textarea name=\"notes\"", body)
        self.assertIn("free written terms for the educational Signal Desk", body)
        for required in ('name="csrfmiddlewaretoken"', 'name="email"',
                         'name="horizon"', 'name="consent"',
                         'name="idempotency_key"', 'name="website"'):
            self.assertIn(required, body)
        self.assertIn('action="/moj-prop-intake/?format=html"', body)
        self.assertIn('required minlength="20"', body)
        self.assertNotIn("/mojprop-starter30-checkout/", body)
        self.assertNotIn("Create 30 TRX invoice", body)
        self.assertEqual(response["Cache-Control"], "private, no-store, max-age=0")
        self.assertIn("noindex", response["X-Robots-Tag"])

    def test_03_approved_organic_campaign_is_the_only_attribution(self):
        query = ("format=html&service=signals&"
                 "utm_source=moj_prop&utm_medium=onsite&"
                 "utm_campaign=signals_education_lead_20261121&"
                 "utm_content=signal_nav")
        valid = request_form(self._get(query)).content.decode()
        self.assertIn('name="utm_campaign" value="signals_education_lead_20261121"', valid)
        self.assertIn("free written terms for the educational Signal Desk", valid)
        invalid = request_form(self._get(query.replace("signal_nav", "customer-email%40example.invalid"))).content.decode()
        self.assertNotIn('name="utm_campaign"', invalid)
        self.assertNotIn("customer-email", invalid)

    def test_04_duplicate_service_or_unrelated_package_cannot_prefill(self):
        for query in ("format=html&service=signals&service=signals",
                      "format=html&service=signals&package=starter-30-trx",
                      "format=html&service=signals&package=moj-prop-01",
                      "format=html&service=digital"):
            with self.subTest(query=query):
                self.assertEqual(_safe_service_prefill(self._get(query)), (None, ""))

    def test_05_failed_post_does_not_echo_untrusted_customer_fields(self):
        req = self.factory.post(
            "/moj-prop-intake/?format=html&service=signals",
            data={"service": "signals", "name": "Sensitive Person",
                  "notes": "PRIVATE CUSTOMER CONTACT TEXT", "consent": "on"},
            secure=True,
        )
        self.assertEqual(_safe_service_prefill(req), (None, ""))
        text = request_form(req, error="Please review the submission.").content.decode()
        self.assertNotIn("Sensitive Person", text)
        self.assertNotIn("PRIVATE CUSTOMER CONTACT TEXT", text)
        self.assertNotIn("free written terms for the educational Signal Desk", text)

    def test_06_starter30_and_generic_blueprint_unchanged(self):
        starter_service, starter_notes = _safe_service_prefill(
            self._get("format=html&service=blueprint&package=starter-30-trx"))
        self.assertEqual(starter_service, "blueprint")
        self.assertIn("MOJPROP-STARTER30", starter_notes)
        self.assertNotIn("educational Signal Desk", starter_notes)
        self.assertEqual(_safe_service_prefill(
            self._get("format=html&service=blueprint")), ("blueprint", ""))


if __name__ == "__main__":
    import unittest
    unittest.main()
