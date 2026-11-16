"""Moj Prop English Starter30: native secure no-JS request retains exact SKU.

This is an isolated Django test database: no public customer requests, TRX,
subscription, live broker operation, email, external network or deployment.
"""
from html import unescape
from pathlib import Path
from urllib.parse import urlencode
import re

from django.test import Client, TestCase

from core.models import MojPropRequest
from core.mojprop_offer_draft import _starter30_selection


FORM_URL = "/moj-prop-intake/?format=html"
STARTER_URL = FORM_URL + "&service=blueprint&package=starter-30-trx"
PREFIX = "Requested canonical product: MOJPROP-STARTER30 ("
ROOT = Path(__file__).resolve().parents[1]


class MojPropStarter30NativeAccessTests(TestCase):
    def setUp(self):
        self.browser = Client(enforce_csrf_checks=True)

    def fetch(self, url=FORM_URL):
        response = self.browser.get(url)
        self.assertEqual(response.status_code, 200)
        return response.content.decode("utf-8")

    def test_01_starter_product_is_explicitly_selected(self):
        html = self.fetch(STARTER_URL)
        self.assertIn('<option value="blueprint" selected>', html)
        self.assertIn(PREFIX, html)
        self.assertIn("verified lawful invoice required; NOT paid", html)
        self.assertIn("no payment, challenge or funded trading account", html)
        self.assertNotIn("name=\"product_id\"", html)

    def test_02_native_form_is_html_post_and_csrf_protected(self):
        html = self.fetch(STARTER_URL)
        self.assertIn('method="post"', html)
        self.assertIn('action="' + FORM_URL + '"', html)
        self.assertIn('name="csrfmiddlewaretoken"', html)
        self.assertIn('name="idempotency_key"', html)
        self.assertIn('name="consent"', html)

    def test_03_other_allowlisted_services_can_be_preselected(self):
        for route in ("blueprint", "signals", "brief", "audit"):
            with self.subTest(route=route):
                html = self.fetch(FORM_URL + "&service=" + route)
                self.assertIn('<option value="' + route + '" selected>', html)
                self.assertNotIn(PREFIX, html)

    def test_04_default_form_does_not_claim_starter30(self):
        html = self.fetch()
        self.assertNotIn(PREFIX, html)
        self.assertNotIn('value="blueprint" selected', html)

    def test_05_rejects_ambiguous_duplicate_service(self):
        html = self.fetch(STARTER_URL + "&service=signals")
        self.assertNotIn(PREFIX, html)
        self.assertNotIn('value="blueprint" selected', html)
        self.assertNotIn('value="signals" selected', html)

    def test_06_rejects_ambiguous_duplicate_package(self):
        html = self.fetch(STARTER_URL + "&package=starter-30-trx")
        self.assertNotIn(PREFIX, html)
        self.assertNotIn('value="blueprint" selected', html)

    def test_07_rejects_starter_package_on_signal_service(self):
        html = self.fetch(FORM_URL + "&service=signals&package=starter-30-trx")
        self.assertNotIn(PREFIX, html)
        self.assertNotIn('value="signals" selected', html)

    def test_08_requires_route_for_starter_package(self):
        html = self.fetch(FORM_URL + "&package=starter-30-trx")
        self.assertNotIn(PREFIX, html)

    def test_09_unknown_package_never_generates_sku_claim(self):
        html = self.fetch(FORM_URL + "&service=blueprint&package=another-product")
        self.assertNotIn(PREFIX, html)
        self.assertNotIn('value="blueprint" selected', html)

    def test_10_query_injection_is_not_reflected_or_selected(self):
        unsafe = '<img src=x onerror=alert(1)>'
        html = self.fetch(FORM_URL + "&" + urlencode({"service": unsafe, "notes": unsafe}))
        self.assertNotIn(unsafe, html)
        self.assertNotIn('onerror=alert', html)
        self.assertNotIn(' selected>', html)

    def test_11_digital_purchase_route_never_appears(self):
        html = self.fetch(FORM_URL + "&service=digital")
        self.assertNotIn('<option value="digital">', html)
        self.assertNotIn('value="digital" selected', html)

    def test_12_public_catalog_has_sku_bound_nojs_link(self):
        for relative in (
            "templates/moj-prop-v4/catalog/index.html",
            "templates/moj-prop-v4/starter-30-trx/index.html",
        ):
            with self.subTest(relative=relative):
                html = (ROOT / relative).read_text("utf-8")
                self.assertIn(
                    '/moj-prop-intake/?format=html&amp;service=blueprint'
                    '&amp;package=starter-30-trx', html,
                )

    def _submit_from_real_rendered_form(self):
        page = self.fetch(STARTER_URL)
        csrf = re.search(
            r'name="csrfmiddlewaretoken" value="([^"]+)"', page
        ).group(1)
        request_key = re.search(
            r'name="idempotency_key" value="([^"]+)"', page
        ).group(1)
        notes = unescape(re.search(
            r'<textarea name="notes"[^>]*>(.*?)</textarea>', page, re.S
        ).group(1))
        payload = {
            "csrfmiddlewaretoken": csrf,
            "idempotency_key": request_key,
            "name": "Review Buyer",
            "email": "nativebuyer@example.org",
            "service": "blueprint",
            "horizon": "review",
            "notes": notes,
            "website": "",
            "consent": "on",
        }
        return payload

    def test_13_real_django_post_creates_one_unpaid_sku_scoped_lead(self):
        payload = self._submit_from_real_rendered_form()
        response = self.browser.post(
            FORM_URL, data=urlencode(payload),
            content_type="application/x-www-form-urlencoded",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(MojPropRequest.objects.count(), 1)
        lead = MojPropRequest.objects.get()
        self.assertEqual(lead.route, "blueprint")
        self.assertEqual(_starter30_selection(lead), "buyer_claim")
        self.assertIsNone(lead.product_id)
        self.assertIn(b"No payment was taken", response.content)
        self.assertIn(b"private-receipt", response.content)

    def test_14_replay_with_same_key_cannot_create_duplicate_leads(self):
        payload = self._submit_from_real_rendered_form()
        encoded = urlencode(payload)
        first = self.browser.post(
            FORM_URL, data=encoded,
            content_type="application/x-www-form-urlencoded",
        )
        second = self.browser.post(
            FORM_URL, data=encoded,
            content_type="application/x-www-form-urlencoded",
        )
        self.assertEqual((first.status_code, second.status_code), (201, 200))
        self.assertEqual(MojPropRequest.objects.count(), 1)

    def test_15_changed_product_scope_with_same_key_is_conflict(self):
        payload = self._submit_from_real_rendered_form()
        first = self.browser.post(
            FORM_URL, data=urlencode(payload),
            content_type="application/x-www-form-urlencoded",
        )
        self.assertEqual(first.status_code, 201)
        payload["notes"] = "This is a different request for a generic trading blueprint."
        second = self.browser.post(
            FORM_URL, data=urlencode(payload),
            content_type="application/x-www-form-urlencoded",
        )
        self.assertEqual(second.status_code, 409)
        self.assertEqual(MojPropRequest.objects.count(), 1)

    def test_16_csrf_is_required_for_untrusted_post(self):
        payload = self._submit_from_real_rendered_form()
        other_browser = Client(enforce_csrf_checks=True)
        result = other_browser.post(
            FORM_URL, data=urlencode(payload),
            content_type="application/x-www-form-urlencoded",
        )
        self.assertEqual(result.status_code, 403)
        self.assertEqual(MojPropRequest.objects.count(), 0)

    def test_17_no_consent_means_no_starter30_lead(self):
        payload = self._submit_from_real_rendered_form()
        payload.pop("consent")
        result = self.browser.post(
            FORM_URL, data=urlencode(payload),
            content_type="application/x-www-form-urlencoded",
        )
        self.assertEqual(result.status_code, 400)
        self.assertEqual(MojPropRequest.objects.count(), 0)

    def test_18_private_headers_prevent_caching_or_embedding(self):
        response = self.browser.get(STARTER_URL)
        self.assertIn("no-store", response["Cache-Control"])
        self.assertEqual(response["Referrer-Policy"], "no-referrer")
        self.assertEqual(response["X-Frame-Options"], "DENY")
        self.assertEqual(response["X-Robots-Tag"], "noindex, nofollow")
