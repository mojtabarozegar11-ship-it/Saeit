"""Regression for truthful zero-charge product enquiry on the existing public CRM."""
from django.test import RequestFactory, SimpleTestCase

from core.mojprop_accessible_intake import _safe_digital_product, request_form


class StoreProductEnquiryTests(SimpleTestCase):
    def setUp(self):
        self.rf = RequestFactory()

    def test_all_three_public_products_have_product_bound_csrf_forms(self):
        for product_id in ("72", "225", "879"):
            with self.subTest(product_id=product_id):
                req = self.rf.get(
                    "/moj-prop-intake/?format=html&service=digital&product_id=" + product_id
                )
                response = request_form(req)
                html = response.content.decode("utf-8")
                self.assertEqual(response.status_code, 200)
                self.assertEqual(_safe_digital_product(req), product_id)
                self.assertIn('name="csrfmiddlewaretoken"', html)
                self.assertIn('name="consent"', html)
                self.assertIn('name="service"', html)
                self.assertIn('value="digital" selected', html)
                self.assertIn('name="product_id" value="' + product_id + '"', html)
                self.assertIn(
                    'action="/moj-prop-intake/?format=html&amp;service=digital'
                    '&amp;product_id=' + product_id + '"',
                    html,
                )
                self.assertIn("no payment", html.lower())
                self.assertIn('/store/', html)
                self.assertNotIn('/mojprop-starter30-checkout/', html)

    def test_untrusted_or_duplicate_product_hints_never_expose_digital_option(self):
        bad_urls = (
            "/moj-prop-intake/?format=html&service=digital&product_id=999",
            "/moj-prop-intake/?format=html&service=digital&product_id=72&product_id=225",
            "/moj-prop-intake/?format=html&service=digital&service=digital&product_id=72",
            "/moj-prop-intake/?format=html&service=blueprint&product_id=72",
            "/moj-prop-intake/?format=html&service=digital&product_id=72&package=starter-30-trx",
            "/moj-prop-intake/?format=html&service=digital",
        )
        for url in bad_urls:
            with self.subTest(url=url):
                request = self.rf.get(url)
                self.assertIsNone(_safe_digital_product(request))
                html = request_form(request).content.decode("utf-8")
                self.assertNotIn('value="digital"', html)
                self.assertNotIn('name="product_id"', html)
                self.assertNotIn('service=digital&amp;product_id', html)

    def test_post_error_preserves_only_verified_bounded_product_without_pii(self):
        url = "/moj-prop-intake/?format=html&service=digital&product_id=72"
        req = self.rf.post(url, {
            "service": "digital", "product_id": "72",
            "name": "Sensitive Example", "email": "secret@nowhere.invalid",
            "notes": "untrusted-raw-notes-do-not-reflect",
        })
        html = request_form(req, error="Please correct the highlighted fields.",
                            status=400).content.decode("utf-8")
        self.assertIn('value="digital" selected', html)
        self.assertIn('name="product_id" value="72"', html)
        for secret in ("secret@nowhere.invalid", "Sensitive Example",
                       "untrusted-raw-notes-do-not-reflect"):
            self.assertNotIn(secret, html)
        self.assertEqual(request_form(req, error="Invalid", status=400).status_code, 400)
        mismatched = self.rf.post(url, {"service": "digital", "product_id": "225"})
        self.assertIsNone(_safe_digital_product(mismatched))
        html_bad = request_form(mismatched, error="Invalid", status=400).content.decode("utf-8")
        self.assertNotIn('name="product_id"', html_bad)
        self.assertNotIn('value="digital"', html_bad)

    def test_normal_signals_and_starter30_forms_are_not_changed_to_product_inquiries(self):
        for url in (
            "/moj-prop-intake/?format=html&service=signals",
            "/moj-prop-intake/?format=html&service=blueprint&package=starter-30-trx",
            "/moj-prop-intake/?format=html",
        ):
            req = self.rf.get(url)
            html = request_form(req).content.decode("utf-8")
            self.assertIsNone(_safe_digital_product(req))
            self.assertNotIn('name="product_id"', html)
            self.assertNotIn('value="digital"', html)
            self.assertIn('name="csrfmiddlewaretoken"', html)
            self.assertIn('name="consent"', html)
