"""Django regression for the same CRM endpoint with an accessible HTML fallback.

No live payments, customer communications, trading or production migration.
"""
import json
import re
from html import unescape
from pathlib import Path
from urllib.parse import urlencode
from uuid import UUID
from unittest.mock import patch

from django.test import Client, TestCase, override_settings

from core.models import MojPropRequest


URL = "/moj-prop-intake/?format=html"


@override_settings(ALLOWED_HOSTS=["testserver", "mojplaywin.com"])
class AccessibleCurrentMainLeadTests(TestCase):
    def setUp(self):
        self.client = Client(enforce_csrf_checks=True)
        self.first = self.client.get(URL)
        html = self.first.content.decode("utf-8")
        self.csrf = unescape(re.search(
            r'name="csrfmiddlewaretoken" value="([^"]+)"', html
        ).group(1))
        self.idempotency_key = re.search(
            r'name="idempotency_key" value="([^"]+)"', html
        ).group(1)
        self.data = {
            "csrfmiddlewaretoken": self.csrf,
            "idempotency_key": self.idempotency_key,
            "name": "Current Main Customer",
            "email": "buyer@example.org",
            "service": "brief",
            "horizon": "week",
            "notes": "I need a written research brief on production economics.",
            "consent": "on",
            "website": "",
        }

    def post(self, fields=None, url=URL):
        data = self.data if fields is None else fields
        return self.client.post(url, data=urlencode(data, doseq=True),
                                content_type="application/x-www-form-urlencoded")

    def test_01_html_get_returns_native_form(self):
        self.assertEqual(self.first.status_code, 200)
        self.assertTrue(self.first["Content-Type"].startswith("text/html"))
        self.assertIn(b'method="post"', self.first.content)
        self.assertIn(b'name="email"', self.first.content)

    def test_02_form_is_no_script_and_no_external_assets(self):
        html = self.first.content.decode()
        self.assertNotIn("<script", html)
        self.assertNotIn('<link rel="stylesheet"', html)
        self.assertNotIn('src="https:', html)

    def test_03_native_csrf_session_is_present(self):
        self.assertIn("csrftoken", self.client.cookies)
        self.assertIn(b'name="csrfmiddlewaretoken"', self.first.content)

    def test_04_idempotency_key_is_canonical_uuid4(self):
        self.assertEqual(UUID(self.idempotency_key).version, 4)
        self.assertEqual(str(UUID(self.idempotency_key)), self.idempotency_key)

    def test_04b_browser_receives_exactly_one_idempotency_key(self):
        # Previous source rendered TWO different hidden keys. The HTML
        # POST rejected both, although hand-built unit-test payloads passed.
        html = self.first.content.decode("utf-8")
        hidden_keys = re.findall(
            r'<input[^>]*type="hidden"[^>]*name="idempotency_key"'
            r'[^>]*value="([^"]+)"', html,
        )
        self.assertEqual(len(hidden_keys), 1)
        self.assertEqual(hidden_keys[0], self.idempotency_key)
        self.assertEqual(UUID(hidden_keys[0]).version, 4)

    def test_04c_duplicate_browser_idempotency_keys_fail_closed(self):
        values = dict(self.data, idempotency_key=[
            self.idempotency_key, str(UUID("c71bfce2-1f2a-4cf8-81d7-8b9445194f2e")),
        ])
        response = self.post(values)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(MojPropRequest.objects.count(), 0)

    def test_04d_actual_rendered_form_submits_one_crm_lead(self):
        # Rendered HTML, not self.data constructed by the test suite: this
        # catches duplicate or missing hidden inputs before release.
        pairs = re.findall(
            r'<input type="hidden" name="([^"]+)" value="([^"]*)">',
            self.first.content.decode("utf-8"),
        )
        pairs += [
            ("name", self.data["name"]),
            ("email", self.data["email"]),
            ("service", self.data["service"]),
            ("horizon", self.data["horizon"]),
            ("notes", self.data["notes"]),
            ("consent", self.data["consent"]),
        ]
        response = self.client.post(
            URL, data=urlencode(pairs),
            content_type="application/x-www-form-urlencoded",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(MojPropRequest.objects.count(), 1)
        self.assertIn(b'private-receipt', response.content)

    def test_05_sensitive_response_headers(self):
        self.assertIn("no-store", self.first["Cache-Control"])
        self.assertEqual(self.first["Referrer-Policy"], "no-referrer")
        self.assertEqual(self.first["X-Frame-Options"], "DENY")
        self.assertEqual(self.first["X-Robots-Tag"], "noindex, nofollow")

    def test_06_success_persists_one_real_crm_request(self):
        result = self.post()
        self.assertEqual(result.status_code, 201)
        self.assertIn(b"Request received", result.content)
        self.assertIn(b"private-receipt", result.content)
        self.assertEqual(MojPropRequest.objects.count(), 1)
        self.assertEqual(MojPropRequest.objects.first().email, "buyer@example.org")

    def test_07_repeated_post_same_key_is_one_request(self):
        first = self.post()
        second = self.post()
        self.assertEqual((first.status_code, second.status_code), (201, 200))
        self.assertEqual(MojPropRequest.objects.count(), 1)

    def test_08_reuse_key_with_changed_identity_is_denied(self):
        self.assertEqual(self.post().status_code, 201)
        changed = dict(self.data, email="different@example.org")
        response = self.post(changed)
        self.assertEqual(response.status_code, 409)
        self.assertEqual(MojPropRequest.objects.count(), 1)

    def test_09_missing_consent_denies_lead(self):
        data = dict(self.data)
        data.pop("consent")
        result = self.post(data)
        self.assertEqual(result.status_code, 400)
        self.assertEqual(MojPropRequest.objects.count(), 0)

    def test_10_malformed_email_is_never_echoed(self):
        bad = dict(self.data, email="invalid@email<unsafe>")
        response = self.post(bad)
        self.assertEqual(response.status_code, 400)
        self.assertNotIn(b"invalid@email", response.content)
        self.assertEqual(MojPropRequest.objects.count(), 0)

    def test_11_duplicate_email_fields_fail_closed(self):
        data = dict(self.data, email=["first@example.org", "second@example.org"])
        response = self.post(data)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(MojPropRequest.objects.count(), 0)

    def test_12_invalid_format_never_writes(self):
        result = self.post(url="/moj-prop-intake/?format=html&format=html")
        self.assertEqual(result.status_code, 400)
        self.assertEqual(MojPropRequest.objects.count(), 0)

    def test_13_json_get_api_unchanged(self):
        result = self.client.get("/moj-prop-intake/")
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json()["service"], "moj-prop-intake")

    def test_14_html_disallows_json_body(self):
        result = self.client.post(URL, data=json.dumps(self.data),
                                  content_type="application/json",
                                  HTTP_X_CSRFTOKEN=self.csrf)
        self.assertEqual(result.status_code, 400)
        self.assertEqual(MojPropRequest.objects.count(), 0)

    def test_15_missing_csrf_is_denied(self):
        fresh = Client(enforce_csrf_checks=True)
        result = fresh.post(URL, self.data)
        self.assertEqual(result.status_code, 403)
        self.assertEqual(MojPropRequest.objects.count(), 0)

    def test_16_native_fallback_link_is_on_public_moj_prop_page(self):
        html = (Path(__file__).resolve().parents[1] /
                "templates/moj-prop-v4/index.html").read_text(encoding="utf-8")
        # The real paid-challenge prospect must use dedicated consent intake.
        # Historical general-service GET remains separately tested above.
        self.assertIn('href="/moj-prop-interest/form/"', html)
        self.assertIn('href="/moj-prop-interest/form/?lang=fa"', html)
        self.assertIn("<noscript>", html)
        self.assertNotIn('href="/moj-prop-intake/?format=html"', html)

    def test_17_unfulfillable_digital_product_option_is_hidden(self):
        html = self.first.content.decode()
        self.assertNotIn('<option value="digital">', html)

    def test_18_response_is_not_a_purchase_or_payment(self):
        receipt = self.post().content.decode()
        self.assertIn("No payment was taken", receipt)
        self.assertNotIn("Send TRX", receipt)
        self.assertNotIn("Guaranteed return", receipt)

    def test_19_unknown_field_does_not_create_lead(self):
        result = self.post(dict(self.data, admin_override="1"))
        self.assertEqual(result.status_code, 400)
        self.assertEqual(MojPropRequest.objects.count(), 0)

    def test_20_landing_page_no_javascript_message_exists(self):
        html = (Path(__file__).resolve().parents[1] /
                "templates/moj-prop-v4/index.html").read_text(encoding="utf-8")
        self.assertIn("<noscript>", html)


    def _status_token(self):
        receipt = self.post()
        self.assertEqual(receipt.status_code, 201)
        return unescape(re.search(
            r'<pre id="private-receipt">([^<]+)</pre>',
            receipt.content.decode()
        ).group(1))

    def test_21_status_form_is_native_html(self):
        response = self.client.get("/moj-prop-status/?format=html")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'method="post"', response.content)
        self.assertIn(b'name="receipt_token"', response.content)
        self.assertIn("no-store", response["Cache-Control"])

    def test_22_private_status_post_returns_only_stage(self):
        token = self._status_token()
        response = self.client.post(
            "/moj-prop-status/?format=html",
            data=urlencode({"receipt_token": token, "csrfmiddlewaretoken": self.csrf}),
            content_type="application/x-www-form-urlencoded",
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Review status", response.content)
        self.assertNotIn(b"buyer@example.org", response.content)
        self.assertNotIn(token.encode(), response.content)

    def test_23_invalid_status_token_does_not_disclose_identity(self):
        response = self.client.post(
            "/moj-prop-status/?format=html",
            data=urlencode({"receipt_token": "invalid", "csrfmiddlewaretoken": self.csrf}),
            content_type="application/x-www-form-urlencoded",
        )
        self.assertEqual(response.status_code, 404)
        self.assertNotIn(b"buyer@example.org", response.content)

    def test_24_bearer_token_in_html_get_is_never_accepted(self):
        token = self._status_token()
        response = self.client.get("/moj-prop-status/?format=html&receipt_token=" + token)
        self.assertEqual(response.status_code, 400)
        self.assertNotIn(token.encode(), response.content)

    def test_24b_html_post_with_query_bearer_is_denied_before_crm(self):
        token = self._status_token()
        with patch.object(MojPropRequest.objects, "filter",
                          side_effect=AssertionError("HTML bearer query reached CRM")):
            response = self.client.post(
                "/moj-prop-status/?format=html&receipt_token=" + token,
                data=urlencode({"receipt_token": token, "csrfmiddlewaretoken": self.csrf}),
                content_type="application/x-www-form-urlencoded",
            )
        self.assertEqual(response.status_code, 400)
        self.assertNotIn(token.encode(), response.content)
        self.assertNotIn(b"buyer@example.org", response.content)
        self.assertEqual(response["Referrer-Policy"], "no-referrer")
        self.assertIn("no-store", response["Cache-Control"])

    def test_24c_legacy_token_from_old_url_still_works_in_secure_form(self):
        token = self._status_token()
        denied = self.client.get("/moj-prop-status/?format=html&receipt_token=" + token)
        self.assertEqual(denied.status_code, 400)
        checked = self.client.post(
            "/moj-prop-status/?format=html",
            data=urlencode({"receipt_token": token, "csrfmiddlewaretoken": self.csrf}),
            content_type="application/x-www-form-urlencoded",
        )
        self.assertEqual(checked.status_code, 200)
        self.assertNotIn(token.encode(), checked.content)
        self.assertIn(b"Review status", checked.content)

    def test_25_private_status_requires_csrf(self):
        fresh = Client(enforce_csrf_checks=True)
        response = fresh.post(
            "/moj-prop-status/?format=html", {"receipt_token": "invalid"}
        )
        self.assertEqual(response.status_code, 403)

    def test_26_ambiguous_duplicate_status_tokens_are_denied(self):
        response = self.client.post(
            "/moj-prop-status/?format=html",
            data=urlencode({
                "csrfmiddlewaretoken": self.csrf,
                "receipt_token": ["a", "b"],
            }, doseq=True),
            content_type="application/x-www-form-urlencoded",
        )
        self.assertEqual(response.status_code, 400)

    def test_27_duplicated_format_parameters_do_not_bypass_validation(self):
        response = self.client.get("/moj-prop-status/?format=html&format=html")
        self.assertEqual(response.status_code, 400)

    def test_28_original_json_receipt_lookup_remains_functional(self):
        token = self._status_token()
        response = self.client.post(
            "/moj-prop-status/",
            data=json.dumps({"receipt_token": token}),
            content_type="application/json", HTTP_X_CSRFTOKEN=self.csrf,
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["payment_status"], "not_collected_by_this_service")

    def test_29_json_post_to_html_status_form_is_rejected(self):
        response = self.client.post(
            "/moj-prop-status/?format=html",
            data=json.dumps({"receipt_token": "wrong"}),
            content_type="application/json", HTTP_X_CSRFTOKEN=self.csrf,
        )
        self.assertEqual(response.status_code, 400)

    def test_30_status_html_never_has_external_asset_or_script(self):
        html = self.client.get("/moj-prop-status/?format=html").content.decode()
        self.assertNotIn("<script", html)
        self.assertNotIn('src="https:', html)

    def test_31_multipart_status_submission_is_rejected_without_status_disclosure(self):
        # Browser status form uses urlencoded: never broaden to accept multipart.
        token = self._status_token()
        response = self.client.post(
            "/moj-prop-status/?format=html",
            {"receipt_token": token, "csrfmiddlewaretoken": self.csrf},
        )
        self.assertEqual(response.status_code, 400)
        self.assertNotIn(token.encode(), response.content)
        self.assertNotIn(b"buyer@example.org", response.content)
