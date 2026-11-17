"""Real Django render acceptance: only synthetic GETs, never an intake POST.

The public site may still return 404. These tests assert source/router
integrity in an ephemeral CI process, not deployed site availability.
"""
from django.test import Client, SimpleTestCase, override_settings
from scripts.mojprop_c142_public_form_get_readonly import evaluate_page


@override_settings(ALLOWED_HOSTS=["testserver", "mojplaywin.com", "www.mojplaywin.com"])
class RenderedPlan1GetContract(SimpleTestCase):
    def setUp(self):
        self.client = Client(enforce_csrf_checks=True)

    def _request(self, url):
        return self.client.get(
            url, secure=True, HTTP_HOST="mojplaywin.com",
            HTTP_ACCEPT="text/html",
        )

    def test_actual_django_english_has_one_valid_nonpayable_post_form(self):
        response = self._request("/moj-prop-interest/form/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("no-store", response["Cache-Control"])
        self.assertIn("noindex", response["X-Robots-Tag"])
        self.assertEqual(
            evaluate_page(status=response.status_code, body=response.content, language="en"),
            "verified_get_form_no_payment_claim",
        )

    def test_actual_django_farsi_is_rtl_and_has_required_opt_in(self):
        response = self._request("/moj-prop-interest/form/?lang=fa")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            evaluate_page(status=response.status_code, body=response.content, language="fa"),
            "verified_get_form_no_payment_claim",
        )
        self.assertIn(b'name="contact_consent" value="yes" required', response.content)

    def test_wrong_host_and_insecure_http_cannot_serve_sensitive_form(self):
        denied_host = self.client.get(
            "/moj-prop-interest/form/", secure=True, HTTP_HOST="testserver"
        )
        denied_scheme = self.client.get(
            "/moj-prop-interest/form/", secure=False, HTTP_HOST="mojplaywin.com"
        )
        self.assertEqual(denied_host.status_code, 404)
        self.assertEqual(denied_scheme.status_code, 404)

    def test_query_injection_or_repeated_language_is_rejected_without_db(self):
        for url in (
            "/moj-prop-interest/form/?lang=fa&lang=en",
            "/moj-prop-interest/form/?email=buyer%40example.com",
            "/moj-prop-interest/form/?lang=unknown",
        ):
            with self.subTest(url=url):
                self.assertEqual(self._request(url).status_code, 400)
