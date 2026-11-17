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
POST = FORM


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
        self.assertIn("درخواست شما برای بررسی ثبت شد", result.content.decode("utf-8"))
        self.assertIn('id="private-receipt"', result.content.decode("utf-8"))
        self.assertIn("/moj-prop-status/?format=html", result.content.decode("utf-8"))
        self.assertIn("no-store", result["Cache-Control"])
        self.assertEqual(result["Referrer-Policy"], "no-referrer")
        self.assertEqual(result["Content-Language"], "fa")
        self.assertNotIn(form["email"], result.content.decode("utf-8"))
        self.assertNotIn(form["name"], result.content.decode("utf-8"))
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
        self.assertIn("درخواست قبلی بازیابی شد", duplicate.content.decode("utf-8"))
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
        self.assertIn("ثبت یا بررسی درخواست در دسترس نیست", result.content.decode("utf-8"))
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

    def test_new_leads_keep_customer_language_and_receipt_token_private(self):
        import re
        from core.mojprop_receipts import verify_receipt_token
        for code, email in (
            ("bn", "prospect-bn@example.org"),
            ("ar", "prospect-ar@example.org"),
            ("de", "prospect-de@example.org"),
        ):
            with self.subTest(locale=code):
                page = self.browser.get(
                    "/world/" + code + "/moj-prop-interest/",
                    secure=True, HTTP_HOST=HOST,
                )
                values = self._form_values(page)
                values["email"] = email
                response = self.browser.post(
                    "/world/" + code + "/moj-prop-interest/",
                    data=urlencode(values),
                    content_type="application/x-www-form-urlencoded",
                    secure=True, HTTP_HOST=HOST,
                    HTTP_REFERER="https://mojplaywin.com/world/" + code + "/moj-prop-interest/",
                )
                self.assertEqual(response.status_code, 201)
                self.assertEqual(response["Content-Language"], code)
                self.assertIn("no-store", response["Cache-Control"])
                rendered = response.content.decode("utf-8")
                self.assertIn('lang="' + code + '"', rendered)
                match = re.search(
                    r'<pre class="token" id="private-receipt">(.*?)</pre>',
                    rendered, re.S,
                )
                self.assertIsNotNone(match)
                receipt = match.group(1)
                ref = MojPropRequest.objects.get(email=email).request_id
                self.assertEqual(verify_receipt_token(receipt), ref)
                self.assertNotIn(email, rendered)
                self.assertIn("/moj-prop-status/?format=html", rendered)
        self.assertEqual(MojPropRequest.objects.count(), 3)
        self.assertEqual(MojPropOffer.objects.count(), 0)
