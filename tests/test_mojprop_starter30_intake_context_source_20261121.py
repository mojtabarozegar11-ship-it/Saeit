"""Keep the free Starter30 written-terms lead path recognizable on form errors.

No payment, invoice, CRM insert, email, or production service is exercised.
"""
from django.test import RequestFactory, SimpleTestCase

from core.mojprop_accessible_intake import request_form


class Starter30TermsFormContextTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.starter_url = (
            "/moj-prop-intake/?format=html&service=blueprint"
            "&package=starter-30-trx&utm_campaign=campaign_external_untrusted"
        )
        self.expected_action = (
            'action="/moj-prop-intake/?format=html&amp;service=blueprint'
            '&amp;package=starter-30-trx"'
        )

    def render(self, request, *, error=None):
        response = request_form(request, error=error, status=400 if error else 200)
        return response.content.decode("utf-8"), response

    def test_starter30_get_retains_fixed_product_action_without_tracking_query(self):
        html, response = self.render(self.factory.get(self.starter_url))
        self.assertEqual(response.status_code, 200)
        self.assertIn(self.expected_action, html)
        self.assertIn("Requested canonical product: MOJPROP-STARTER30", html)
        self.assertIn("free request for written terms only", html)
        self.assertIn('name="csrfmiddlewaretoken"', html)
        self.assertNotIn("campaign_external_untrusted", html)
        self.assertNotIn("guaranteed trading profit", html)

    def test_invalid_post_keeps_starter30_context_for_retry_without_pii_echo(self):
        request = self.factory.post(self.starter_url, data={
            "name": "Private Person", "email": "private@example.org"
        })
        html, response = self.render(request, error="Please correct the form.")
        self.assertEqual(response.status_code, 400)
        self.assertIn(self.expected_action, html)
        self.assertIn("Requested canonical product: MOJPROP-STARTER30", html)
        self.assertIn("Please correct the form.", html)
        self.assertNotIn("private@example.org", html)
        self.assertNotIn("Private Person", html)

    def test_generic_form_keeps_original_action_and_no_payment_language(self):
        html, _ = self.render(self.factory.get("/moj-prop-intake/?format=html"))
        self.assertIn('action="/moj-prop-intake/?format=html"', html)
        self.assertNotIn(self.expected_action, html)
        self.assertNotIn("Requested canonical product: MOJPROP-STARTER30", html)

    def test_unrecognized_package_does_not_inject_starter30_action(self):
        html, _ = self.render(self.factory.get(
            "/moj-prop-intake/?format=html&service=blueprint"
            "&package=attacker-supplied-value&utm_campaign=evil"
        ))
        self.assertIn('action="/moj-prop-intake/?format=html"', html)
        self.assertNotIn("starter-30-trx", html)
        self.assertNotIn("attacker-supplied-value", html)
        self.assertNotIn("utm_campaign=evil", html)
