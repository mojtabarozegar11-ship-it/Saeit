"""Real CRM transaction/CSRF integration for 21-language MOJ PROP prospect intake.

Uses only Django's disposable test database. No external API, email, TRX
transfer, brokerage order, invoice or paid enrollment is attempted.
"""
from html import unescape
import re
from urllib.parse import urlencode

from django.test import Client, TestCase, override_settings

from core.models import MojPropOffer, MojPropRequest

HOST = "mojplaywin.com"
FORM = "/world/fa/moj-prop-interest/"
POST = "/moj-prop-intake/?format=html"


@override_settings(ALLOWED_HOSTS=["mojplaywin.com", "www.mojplaywin.com", "testserver"])
class World20MojPropRealCRMTests(TestCase):
    def setUp(self):
        self.browser = Client(enforce_csrf_checks=True)

    def _page(self):
        page = self.browser.get(FORM, secure=True, HTTP_HOST=HOST)
        self.assertEqual(page.status_code, 200)
        return page

    def _form_values(self, page):
        text = page.content.decode("utf-8")
        def one(name):
            regex = r'<input[^>]*name="' + re.escape(name) + r'"[^>]*value="([^"]*)"'
            found = re.findall(regex, text)
            self.assertEqual(len(found), 1, name)
            return unescape(found[0])
        note = re.search(r'<textarea[^>]*name="notes"[^>]*>(.*?)</textarea>', text, re.S)
        self.assertIsNotNone(note)
        return {
            "csrfmiddlewaretoken": one("csrfmiddlewaretoken"),
            "name": "A Real Prospect",
            "email": "consenting-prospect@example.org",
            "service": one("service"),
            "horizon": one("horizon"),
            "notes": unescape(note.group(1)),
            "consent": "on",
            "website": "",
            "idempotency_key": one("idempotency_key"),
        }

    def _post(self, data):
        return self.browser.post(
            POST, data=urlencode(data),
            content_type="application/x-www-form-urlencoded",
            secure=True, HTTP_HOST=HOST,
            HTTP_REFERER="https://mojplaywin.com" + FORM,
        )

    def test_actual_browser_form_reaches_real_crm_once_and_never_charges(self):
        page = self._page()
        form = self._form_values(page)
        self.assertEqual(form["service"], "blueprint")
        self.assertEqual(form["horizon"], "review")
        self.assertTrue(form["notes"].startswith("Prelaunch interest only: MOJ-PROP-01"))
        result = self._post(form)
        self.assertEqual(result.status_code, 201)
        self.assertIn(b"No payment", result.content)
        self.assertEqual(MojPropRequest.objects.count(), 1)
        lead = MojPropRequest.objects.get()
        self.assertEqual(lead.source, "moj-prop-public")
        self.assertEqual(lead.route, "blueprint")
        self.assertEqual(lead.horizon, "review")
        self.assertEqual(lead.name, form["name"])
        self.assertEqual(lead.email, form["email"])
        self.assertTrue(lead.consent)
        self.assertEqual(MojPropOffer.objects.count(), 0)
        duplicate = self._post(form)
        self.assertEqual(duplicate.status_code, 200)
        self.assertEqual(MojPropRequest.objects.count(), 1)
        self.assertEqual(MojPropOffer.objects.count(), 0)

    def test_invalid_csrf_or_missing_consent_creates_no_lead(self):
        without_csrf = {
            "name": "A Real Prospect",
            "email": "consenting-prospect@example.org",
            "service": "blueprint",
            "horizon": "review",
            "notes": "Prelaunch interest only: MOJ-PROP-01, no purchase.",
            "consent": "on",
        }
        self.assertEqual(self._post(without_csrf).status_code, 403)
        self.assertEqual(MojPropRequest.objects.count(), 0)
        form = self._form_values(self._page())
        form.pop("consent")
        result = self._post(form)
        self.assertEqual(result.status_code, 400)
        self.assertEqual(MojPropRequest.objects.count(), 0)

    def test_locale_selection_is_not_acceptance_of_contract_or_payment(self):
        page = self.browser.get(
            "/world/bn/moj-prop-interest/", secure=True, HTTP_HOST=HOST)
        self.assertEqual(page.status_code, 200)
        body = page.content.decode("utf-8")
        self.assertIn('lang="bn"', body)
        self.assertNotIn('name="payment"', body)
        self.assertNotIn('name="wallet"', body)
        self.assertEqual(MojPropRequest.objects.count(), 0)
        self.assertEqual(MojPropOffer.objects.count(), 0)
