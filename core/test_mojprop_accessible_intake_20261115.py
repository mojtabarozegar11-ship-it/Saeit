"""End-to-end Django TestCase for the native no-JS Moj Prop intake fallback.

No real customer, production DB, email, payment, trading, RPC or deployment.
These tests exercise the same actual CRM model and existing CSRF-protected view.
"""
import json
import re
from html import unescape
from pathlib import Path
from urllib.parse import urlencode

from django.test import Client, TestCase, override_settings

from core.models import MojPropRequest
from core.mojprop_receipts import verify_receipt_token

FORM_URL = "/moj-prop-intake/?format=html"


@override_settings(ALLOWED_HOSTS=["testserver", "mojplaywin.com"])
class MojPropNoJavascriptIntakeTests(TestCase):
    def setUp(self):
        self.client = Client(enforce_csrf_checks=True)
        self.get_response = self.client.get(FORM_URL)
        html = self.get_response.content.decode("utf-8")
        match = re.search(
            r'name="csrfmiddlewaretoken" value="([^"]+)"', html
        )
        self.assertIsNotNone(match, "Native form must contain Django CSRF")
        self.csrf = unescape(match.group(1))
        self.form = {
            "csrfmiddlewaretoken": self.csrf,
            "name": "Commercial buyer",
            "email": "buyer@example.org",
            "service": "brief",
            "horizon": "week",
            "notes": "Please scope a dated agricultural economics research brief.",
            "consent": "on",
            "website": "",
        }

    def submit(self, form=None, query=FORM_URL, **extra):
        data = self.form if form is None else form
        return self.client.post(
            query, data=urlencode(data, doseq=True),
            content_type="application/x-www-form-urlencoded", **extra
        )

    def no_write(self, response, status=400):
        self.assertEqual(response.status_code, status)
        self.assertEqual(MojPropRequest.objects.count(), 0)

    def test_01_native_get_is_html(self):
        self.assertEqual(self.get_response.status_code, 200)
        self.assertIn("text/html", self.get_response["Content-Type"])

    def test_02_native_form_has_no_script_or_remote_asset(self):
        body = self.get_response.content.decode()
        self.assertNotIn("<script", body)
        self.assertNotIn('src="http', body)
        self.assertNotIn('<link rel="stylesheet"', body)

    def test_03_native_form_post_action_is_on_origin(self):
        self.assertIn(b'method="post"', self.get_response.content)
        self.assertIn(b'action="/moj-prop-intake/?format=html"', self.get_response.content)

    def test_04_csrf_cookie_is_present(self):
        self.assertIn("csrftoken", self.client.cookies)

    def test_05_native_response_no_store(self):
        self.assertIn("no-store", self.get_response["Cache-Control"])

    def test_06_native_response_no_referrer(self):
        self.assertEqual(self.get_response["Referrer-Policy"], "no-referrer")

    def test_07_native_response_nosniff(self):
        self.assertEqual(self.get_response["X-Content-Type-Options"], "nosniff")

    def test_08_native_response_clickjacking_denied(self):
        self.assertEqual(self.get_response["X-Frame-Options"], "DENY")

    def test_09_native_response_inline_scripts_denied(self):
        csp = self.get_response["Content-Security-Policy"]
        self.assertIn("default-src 'none'", csp)
        self.assertIn("form-action 'self'", csp)

    def test_10_native_response_not_indexable(self):
        self.assertEqual(self.get_response["X-Robots-Tag"], "noindex, nofollow")

    def test_11_original_json_api_get_unmodified(self):
        response = self.client.get("/moj-prop-intake/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["service"], "moj-prop-intake")
        self.assertIn("csrf_token", response.json())

    def test_12_legacy_json_get_route_unmodified(self):
        response = self.client.get("/moj-prop/intake/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["service"], "moj-prop-intake")

    def test_13_valid_native_post_creates_real_crm_lead(self):
        response = self.submit()
        self.assertEqual(response.status_code, 201, response.content[:400])
        self.assertEqual(MojPropRequest.objects.count(), 1)
        lead = MojPropRequest.objects.get()
        self.assertEqual(lead.email, "buyer@example.org")
        self.assertEqual(lead.route, "brief")
        self.assertEqual(lead.status, "new")
        self.assertTrue(lead.consent)

    def test_14_native_receipt_is_html_not_payment_invoice(self):
        response = self.submit()
        self.assertIn("text/html", response["Content-Type"])
        self.assertIn(b"No payment was taken.", response.content)
        self.assertNotIn(b"PAYMENT CONFIRMED", response.content)

    def test_15_native_receipt_does_not_echo_customer_pii(self):
        response = self.submit()
        self.assertNotIn(b"buyer@example.org", response.content)
        self.assertNotIn(b"Commercial buyer", response.content)
        self.assertNotIn(b"agricultural economics research brief", response.content)

    def test_16_native_receipt_contains_the_actual_allocated_id(self):
        response = self.submit()
        lead = MojPropRequest.objects.get()
        self.assertIn(lead.request_id.encode(), response.content)

    def test_17_native_receipt_has_a_verifiable_signed_token(self):
        response = self.submit()
        match = re.search(rb'<pre id="private-receipt">([^<]+)</pre>', response.content)
        self.assertIsNotNone(match)
        token = unescape(match.group(1).decode())
        self.assertEqual(verify_receipt_token(token), MojPropRequest.objects.get().request_id)

    def test_18_native_receipt_cannot_be_cached_by_shared_proxy(self):
        response = self.submit()
        self.assertIn("no-store", response["Cache-Control"])
        self.assertIn("private", response["Cache-Control"])
        self.assertEqual(response["Referrer-Policy"], "no-referrer")

    def test_19_missing_csrf_rejected_before_creating_lead(self):
        outsider = Client(enforce_csrf_checks=True)
        payload = {k: v for k, v in self.form.items() if k != "csrfmiddlewaretoken"}
        response = outsider.post(FORM_URL, data=urlencode(payload),
                                content_type="application/x-www-form-urlencoded")
        self.no_write(response, status=403)

    def test_20_invalid_email_does_not_create_lead(self):
        result = self.submit({**self.form, "email": "bad-address"})
        self.no_write(result)
        self.assertNotIn(b"bad-address", result.content)

    def test_21_missing_buyer_consent_rejected(self):
        self.no_write(self.submit({k: v for k, v in self.form.items() if k != "consent"}))

    def test_22_invalid_route_rejected(self):
        self.no_write(self.submit({**self.form, "service": "funded-trading"}))

    def test_23_underspecified_scope_rejected(self):
        self.no_write(self.submit({**self.form, "notes": "short"}))

    def test_24_honeypot_prevents_bot_lead_creation(self):
        self.no_write(self.submit({**self.form, "website": "spam"}))

    def test_25_duplicate_email_is_rejected_without_write(self):
        self.no_write(self.submit({**self.form, "email": [
            "buyer@example.org", "attacker@example.org"]}))

    def test_26_duplicate_consent_rejected(self):
        self.no_write(self.submit({**self.form, "consent": ["on", "off"]}))

    def test_27_unknown_financial_fields_cannot_create_trx_order(self):
        self.no_write(self.submit({**self.form, "payment": "paid", "wallet": "Tfake"}))

    def test_28_oversize_body_rejected(self):
        # Body-limit breaches use HTTP 413, not a field-validation 400.
        # Preserve the no-write database assertion for oversized POSTs.
        self.no_write(self.submit({**self.form, "notes": "x" * 17000}), status=413)

    def test_29_native_rate_limit_stops_sixth_lead(self):
        for ix in range(5):
            result = self.submit({**self.form, "email": f"buyer{ix}@example.org"})
            self.assertEqual(result.status_code, 201)
        last = self.submit({**self.form, "email": "sixth@example.org"})
        self.assertEqual(last.status_code, 429)
        self.assertEqual(last["Retry-After"], "600")
        self.assertEqual(MojPropRequest.objects.count(), 5)

    def test_30_duplicate_format_mode_denied_without_write(self):
        self.no_write(self.submit(query="/moj-prop-intake/?format=html&format=html"))

    def test_31_unexpected_format_mode_denied(self):
        self.no_write(self.submit(query="/moj-prop-intake/?format=paid"))

    def test_32_native_missing_name_no_pii_echo(self):
        response = self.submit({**self.form, "name": ""})
        self.no_write(response)
        self.assertIn(b'role="alert"', response.content)

    def test_33_persian_name_native_form_stores_valid_contact(self):
        response = self.submit({**self.form, "name": "مدیر تولید"})
        self.assertEqual(response.status_code, 201)
        self.assertEqual(MojPropRequest.objects.get().name, "مدیر تولید")

    def test_34_form_has_contact_and_horizon_choices(self):
        body = self.get_response.content.decode()
        for item in ('name="email"', 'name="service"', 'name="horizon"',
                     'name="notes"', 'name="consent"'):
            self.assertIn(item, body)

    def test_35_original_js_form_never_falls_back_to_get_with_pii(self):
        source = (Path(__file__).resolve().parents[1] /
                  "templates/moj-prop-v4/index.html").read_text(encoding="utf-8")
        self.assertIn('method="post" action="/moj-prop-intake/?format=html"', source)
        self.assertIn('href="/moj-prop-intake/?format=html"', source)
        self.assertIn('type="submit" disabled', source)
        self.assertIn('submit.disabled=false', source)




    def create_lead_and_token(self):
        from core.mojprop_receipts import make_receipt_token
        result = self.submit()
        self.assertEqual(result.status_code, 201)
        lead = MojPropRequest.objects.get()
        return lead, make_receipt_token(lead.request_id)

    def status_post(self, token, *, form=None, path="/moj-prop-status/?format=html"):
        data = form if form is not None else {
            "csrfmiddlewaretoken": self.csrf,
            "receipt_token": token,
        }
        return self.client.post(path, data=urlencode(data, doseq=True),
            content_type="application/x-www-form-urlencoded")

    def test_36_native_status_form_renders_without_javascript(self):
        result = self.client.get("/moj-prop-status/?format=html")
        self.assertEqual(result.status_code, 200)
        self.assertIn(b'action="/moj-prop-status/?format=html"', result.content)
        self.assertNotIn(b"<script", result.content)

    def test_37_status_form_receipt_token_never_goes_in_query_string(self):
        result = self.client.get("/moj-prop-status/?format=html")
        self.assertIn(b'method="post"', result.content)
        self.assertNotIn(b"?receipt_token=", result.content)

    def test_38_native_status_form_contains_csrf(self):
        result = self.client.get("/moj-prop-status/?format=html")
        self.assertIn(b'name="csrfmiddlewaretoken"', result.content)

    def test_39_valid_buyer_can_read_own_review_stage(self):
        lead, token = self.create_lead_and_token()
        result = self.status_post(token)
        self.assertEqual(result.status_code, 200)
        self.assertIn(lead.request_id.encode(), result.content)
        self.assertIn(b"Received for manual review", result.content)

    def test_40_status_lookup_does_not_echo_secret_token(self):
        _, token = self.create_lead_and_token()
        result = self.status_post(token)
        self.assertNotIn(token.encode(), result.content)

    def test_41_status_lookup_does_not_echo_email_or_name(self):
        _, token = self.create_lead_and_token()
        result = self.status_post(token)
        self.assertNotIn(b"buyer@example.org", result.content)
        self.assertNotIn(b"Commercial buyer", result.content)

    def test_42_status_lookup_reports_no_payment_entitlement(self):
        _, token = self.create_lead_and_token()
        result = self.status_post(token)
        self.assertIn(b"not a paid invoice", result.content)
        self.assertIn(b"not", result.content)

    def test_43_status_lookup_denies_unrecognised_secret(self):
        result = self.status_post("not-a-valid-token")
        self.assertEqual(result.status_code, 404)
        self.assertNotIn(b"not-a-valid-token", result.content)

    def test_44_status_lookup_denies_duplicate_bearer_tokens(self):
        _, token = self.create_lead_and_token()
        result = self.status_post(token, form={
            "csrfmiddlewaretoken": self.csrf,
            "receipt_token": [token, token],
        })
        self.assertEqual(result.status_code, 400)

    def test_45_status_lookup_rejects_extra_financial_fields(self):
        _, token = self.create_lead_and_token()
        result = self.status_post(token, form={
            "csrfmiddlewaretoken": self.csrf,
            "receipt_token": token,
            "paid": "true",
        })
        self.assertEqual(result.status_code, 400)

    def test_46_status_lookup_rejects_overlong_token(self):
        result = self.status_post("a" * 257)
        self.assertEqual(result.status_code, 404)

    def test_47_status_lookup_does_not_allow_uncertified_post(self):
        another_client = Client(enforce_csrf_checks=True)
        result = another_client.post("/moj-prop-status/?format=html",
            data=urlencode({"receipt_token": "a"}),
            content_type="application/x-www-form-urlencoded")
        self.assertEqual(result.status_code, 403)

    def test_48_original_json_get_status_remains_supported(self):
        lead, token = self.create_lead_and_token()
        result = self.client.get("/moj-prop-status/", {"receipt_token": token})
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json()["request_id"], lead.request_id)

    def test_49_json_endpoint_denies_form_post_without_html_mode(self):
        _, token = self.create_lead_and_token()
        result = self.status_post(token, path="/moj-prop-status/")
        self.assertEqual(result.status_code, 400)

    def test_50_status_form_refuses_duplicate_format_mode(self):
        result = self.client.get("/moj-prop-status/?format=html&format=html")
        self.assertEqual(result.status_code, 400)

    def test_51_status_result_is_private_no_store_no_referrer(self):
        _, token = self.create_lead_and_token()
        result = self.status_post(token)
        self.assertIn("no-store", result["Cache-Control"])
        self.assertEqual(result["Referrer-Policy"], "no-referrer")
        self.assertIn("default-src 'none'", result["Content-Security-Policy"])

    def test_52_public_intake_receipt_links_to_secure_status_form(self):
        result = self.submit()
        self.assertEqual(result.status_code, 201)
        self.assertIn(b'href="/moj-prop-status/?format=html"', result.content)
        self.assertNotIn(b"?receipt_token=", result.content)


    def _native_key(self):
        match = re.search(rb'name="idempotency_key" value="([^"]+)"',
                          self.get_response.content)
        self.assertIsNotNone(match)
        return match.group(1).decode("ascii")

    def test_54_native_form_contains_secure_server_generated_uuidv4(self):
        from uuid import UUID
        self.assertEqual(UUID(self._native_key()).version, 4)
        self.assertNotIn("name=\"product_id\"", self.get_response.content.decode())
        self.assertNotIn('<option value="digital">', self.get_response.content.decode())

    def test_55_native_lost_response_recovery_returns_same_signed_receipt(self):
        payload = dict(self.form, idempotency_key=self._native_key())
        first = self.submit(payload)
        second = self.submit(payload)
        self.assertEqual((first.status_code, second.status_code), (201, 200))
        self.assertEqual(MojPropRequest.objects.count(), 1)
        self.assertIn(b"recovered without creating a second lead", second.content)
        first_id = MojPropRequest.objects.get().request_id
        self.assertIn(first_id.encode(), first.content)
        self.assertIn(first_id.encode(), second.content)

    def test_56_native_changed_buyer_cannot_reuse_receipt_key(self):
        payload = dict(self.form, idempotency_key=self._native_key())
        first = self.submit(payload)
        different = self.submit({**payload, "email": "other@example.org"})
        self.assertEqual(first.status_code, 201)
        self.assertEqual(different.status_code, 409)
        self.assertNotIn(b'id="private-receipt"', different.content)
        self.assertEqual(MojPropRequest.objects.count(), 1)

    def test_57_native_only_get_mode_cannot_take_paid_fields(self):
        result = self.submit({**self.form, "paid": "true"})
        self.no_write(result)
        self.assertNotIn(b"paid\": true", result.content)

    def test_58_csrf_query_cannot_bypass_same_origin(self):
        client = Client(enforce_csrf_checks=True)
        result = client.post(FORM_URL, data=urlencode({
            **self.form, "csrfmiddlewaretoken": "",
        }), content_type="application/x-www-form-urlencoded")
        self.assertEqual(result.status_code, 403)
        self.assertEqual(MojPropRequest.objects.count(), 0)

    def test_59_recovered_html_receipt_does_not_echo_buyer_data(self):
        payload = dict(self.form, idempotency_key=self._native_key())
        self.submit(payload)
        result = self.submit(payload)
        self.assertNotIn(b"buyer@example.org", result.content)
        self.assertNotIn(b"Commercial buyer", result.content)
        self.assertNotIn(payload["idempotency_key"].encode(), result.content)

    def test_53_repeated_status_check_does_not_modify_request(self):
        lead, token = self.create_lead_and_token()
        self.assertEqual(self.status_post(token).status_code, 200)
        self.assertEqual(self.status_post(token).status_code, 200)
        lead.refresh_from_db()
        self.assertEqual(lead.status, "new")
        self.assertEqual(MojPropRequest.objects.count(), 1)

