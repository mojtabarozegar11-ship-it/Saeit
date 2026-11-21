"""Free organic Facebook qualified-terms form campaign POST continuity.

All tests run with an in-memory RequestFactory; no DB, SMTP, invoices,
actual customer messages, post publication or TRX network requests.
"""
from django.test import RequestFactory, SimpleTestCase

from core.mojprop_accessible_intake import request_form


BASE = (
    "/moj-prop-intake/?format=html&service=blueprint"
    "&package=starter-30-trx"
)
QUALIFIED = (
    "&utm_source=facebook&utm_medium=organic_social"
    "&utm_campaign=starter30_qualified_enquiry_20261121"
)
POST_FRAGMENT = (
    'action="/moj-prop-intake/?format=html&amp;service=blueprint'
    '&amp;package=starter-30-trx&amp;utm_source=facebook'
    '&amp;utm_medium=organic_social'
    '&amp;utm_campaign=starter30_qualified_enquiry_20261121"'
)


class Starter30FreeFacebookCampaignTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def html(self, request, *, error=None):
        response = request_form(request, error=error, status=400 if error else 200)
        return response.content.decode("utf-8"), response

    def test_verified_public_facebook_campaign_visible_in_post_action(self):
        html, response = self.html(self.factory.get(BASE + QUALIFIED))
        self.assertIn(POST_FRAGMENT, html)
        self.assertIn('name="csrfmiddlewaretoken"', html)
        self.assertIn("free request for written terms only", html)
        self.assertIn("Requested canonical product: MOJPROP-STARTER30", html)
        self.assertEqual(response.status_code, 200)
        self.assertIn("no-store", response["Cache-Control"])
        self.assertIn("noindex", response["X-Robots-Tag"])

    def test_failed_post_preserves_only_campaign_not_private_contact_details(self):
        req = self.factory.post(
            BASE + QUALIFIED,
            data={
                "name": "Private Name", "email": "private@example.invalid",
                "notes": "never-echo-my-private-note",
            },
        )
        html, response = self.html(req, error="Choose a valid horizon.")
        self.assertEqual(response.status_code, 400)
        self.assertIn(POST_FRAGMENT, html)
        self.assertIn("Choose a valid horizon.", html)
        self.assertNotIn("Private Name", html)
        self.assertNotIn("private@example.invalid", html)
        self.assertNotIn("never-echo-my-private-note", html)

    def test_untrusted_campaign_never_reflected_in_action_or_html(self):
        bad = BASE + (
            "&utm_source=facebook&utm_medium=organic_social"
            "&utm_campaign=evil-campaign"
            "&email=person@example.invalid&receipt_token=secret-not-for-url"
        )
        html, _ = self.html(self.factory.get(bad))
        self.assertIn(
            'action="/moj-prop-intake/?format=html&amp;service=blueprint'
            '&amp;package=starter-30-trx"',
            html,
        )
        for forbidden in (
            "evil-campaign", "person@example.invalid",
            "secret-not-for-url", "&amp;utm_", "utm_campaign=",
        ):
            self.assertNotIn(forbidden, html)

    def test_duplicate_campaign_key_drops_campaign_even_if_one_value_valid(self):
        html, _ = self.html(
            self.factory.get(BASE + QUALIFIED + "&utm_source=facebook")
        )
        self.assertNotIn("utm_campaign=", html)
        self.assertNotIn("utm_source=", html)

    def test_extra_unrecognized_tracking_field_is_not_echoed(self):
        html, _ = self.html(self.factory.get(
            BASE + QUALIFIED + "&utm_content=PII-email%40example.com"
        ))
        self.assertNotIn("utm_campaign=", html)
        self.assertNotIn("utm_content=", html)
        self.assertNotIn("PII-email", html)

    def test_canonical_product_required_for_any_campaign_echo(self):
        html, _ = self.html(self.factory.get(
            "/moj-prop-intake/?format=html" + QUALIFIED
        ))
        self.assertIn('action="/moj-prop-intake/?format=html"', html)
        self.assertNotIn("utm_campaign=", html)
        self.assertNotIn("starter-30-trx", html)

    def test_missing_utm_parameter_or_wrong_medium_cannot_assert_campaign(self):
        for query in (
            BASE + "&utm_source=facebook"
            "&utm_campaign=starter30_qualified_enquiry_20261121",
            BASE + QUALIFIED.replace("organic_social", "paid_social"),
        ):
            with self.subTest(query=query):
                html, _ = self.html(self.factory.get(query))
                self.assertNotIn("utm_campaign=", html)

    def test_no_ledger_or_public_paid_receipt_is_created_by_owning_module(self):
        import inspect
        from core import mojprop_accessible_intake as intake

        source = inspect.getsource(intake._verified_public_campaign_suffix)
        self.assertNotIn("send_mail", source)
        self.assertNotIn(".save(", source)
        self.assertNotIn("issue_invoice(", source)
        self.assertNotIn("transfer(", source)
        self.assertNotIn("recipient", source)
