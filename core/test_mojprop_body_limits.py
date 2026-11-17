"""No duplicate, oversized or arbitrary customer-intake fields may enter CRM."""
import json
from django.test import Client, TestCase
from core.models import MojPropRequest


class MojPropBodyBoundaryTests(TestCase):
    def setUp(self):
        self.client = Client(enforce_csrf_checks=True)
        self.token = self.client.get("/moj-prop-intake/").json()["csrf_token"]
        self.valid = {
            "name": "Review Client", "email": "client@example.org",
            "service": "audit", "horizon": "week",
            "notes": "Please quote an independent commercial readiness audit.",
            "consent": True, "website": "",
        }

    def post(self, data, ctype="application/json"):
        return self.client.post("/moj-prop-intake/", data=data, content_type=ctype,
                                HTTP_X_CSRFTOKEN=self.token)

    def test_unrecognized_json_field_does_not_create_customer_record(self):
        payload = dict(self.valid, payment_receiver="attacker")
        response = self.post(json.dumps(payload))
        self.assertEqual(response.status_code, 400)
        self.assertEqual(MojPropRequest.objects.count(), 0)

    def test_oversized_notes_do_not_consume_database_or_accept_lead(self):
        payload = dict(self.valid, notes="a" * 18000)
        response = self.post(json.dumps(payload))
        # A >16KiB request is rejected before field processing with HTTP 413.
        self.assertEqual(response.status_code, 413)
        self.assertFalse(MojPropRequest.objects.exists())

    def test_unsupported_content_type_is_rejected(self):
        response = self.post("<req>unsafe</req>", ctype="application/xml")
        self.assertEqual(response.status_code, 400)

    def test_form_duplicate_email_fields_cannot_swap_customer_identity(self):
        response = self.post(
            "name=Review+Client&email=a%40valid.test&email=b%40valid.test"
            "&service=brief&horizon=week&notes=Please+scope+an+educational+brief"
            "&consent=on&website=",
            ctype="application/x-www-form-urlencoded",
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(MojPropRequest.objects.count(), 0)

    def test_duplicate_json_email_or_consent_key_is_rejected(self):
        for field in ("email", "consent", "service"):
            with self.subTest(field=field):
                body = json.dumps(self.valid)
                duplicated = body[:-1] + f', "{field}": "false"}}'
                self.assertEqual(self.post(duplicated).status_code, 400)
        self.assertEqual(MojPropRequest.objects.count(), 0)

    def test_malformed_json_customer_types_are_rejected_without_crm_write(self):
        for key, value in (
            ("name", {"admin": True}),
            ("email", ["a@example.org", "b@example.org"]),
            ("service", 5),
            ("notes", None),
            ("website", False),
            ("consent", "yes"),
            ("consent", 1),
        ):
            with self.subTest(key=key, value=value):
                response = self.post(json.dumps(dict(self.valid, **{key: value})))
                self.assertEqual(response.status_code, 400)
        self.assertEqual(MojPropRequest.objects.count(), 0)

    def test_reserved_non_deliverable_email_addresses_cannot_open_sales_leads(self):
        for email in ("customer@example.invalid", "buyer@localhost",
                      "sales@company.local", "buyer@mock.test"):
            with self.subTest(email=email):
                response = self.post(json.dumps(dict(self.valid, email=email)))
                self.assertEqual(response.status_code, 400)
                self.assertIn("email", response.json()["fields"])
        self.assertFalse(MojPropRequest.objects.exists())

    def test_valid_bounded_json_still_creates_actual_manual_review_lead(self):
        response = self.post(json.dumps(self.valid))
        self.assertEqual(response.status_code, 201)
        lead = MojPropRequest.objects.get(request_id=response.json()["request_id"])
        self.assertEqual(lead.route, "audit")
        self.assertEqual(lead.status, "new")

    def test_oversized_buyer_fields_are_rejected_not_silently_truncated(self):
        cases = (
            ("name", "N" * 201),
            ("email", "a" * 245 + "@example.org"),
            ("service", "audit" + "x" * 30),
            ("horizon", "week" + "x" * 20),
            ("notes", "Scope " + "x" * 5000),
            ("website", " " * 121),
        )
        for field, value in cases:
            with self.subTest(field=field):
                response = self.post(json.dumps(dict(self.valid, **{field: value})))
                self.assertEqual(response.status_code, 400)
                self.assertIn(field, response.json()["fields"])
        self.assertEqual(MojPropRequest.objects.count(), 0)

    def test_exact_notes_limit_is_preserved_in_crm(self):
        notes = "x" * 5000
        response = self.post(json.dumps(dict(self.valid, notes=notes)))
        self.assertEqual(response.status_code, 201)
        lead = MojPropRequest.objects.get(request_id=response.json()["request_id"])
        self.assertEqual(lead.notes, notes)

    def test_standard_csrf_html_form_creates_one_consent_record(self):
        from urllib.parse import urlencode
        form = dict(self.valid, consent="on", csrfmiddlewaretoken=self.token)
        response = self.client.post(
            "/moj-prop-intake/", data=urlencode(form),
            content_type="application/x-www-form-urlencoded",
        )
        self.assertEqual(response.status_code, 201, response.content)
        lead = MojPropRequest.objects.get(request_id=response.json()["request_id"])
        self.assertEqual(lead.email, self.valid["email"])
        self.assertTrue(lead.consent)
        self.assertEqual(lead.route, self.valid["service"])

    def test_html_form_with_csrf_header_and_no_hidden_field_is_valid(self):
        from urllib.parse import urlencode
        form = dict(self.valid, consent="1")
        response = self.post(urlencode(form), ctype="application/x-www-form-urlencoded")
        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(MojPropRequest.objects.count(), 1)

    def test_html_form_rejects_missing_or_false_consent(self):
        from urllib.parse import urlencode
        for consent in ("false", "0", ""):
            with self.subTest(consent=consent):
                form = dict(self.valid, consent=consent)
                response = self.post(urlencode(form), ctype="application/x-www-form-urlencoded")
                self.assertEqual(response.status_code, 400)
                self.assertIn("consent", response.json()["fields"])
        self.assertEqual(MojPropRequest.objects.count(), 0)

    def test_html_form_rejects_duplicate_csrf_hidden_fields(self):
        from urllib.parse import urlencode
        form = dict(self.valid, consent="on", csrfmiddlewaretoken=self.token)
        body = urlencode(form) + "&csrfmiddlewaretoken=" + self.token
        response = self.post(body, ctype="application/x-www-form-urlencoded")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(MojPropRequest.objects.count(), 0)

    def test_html_form_rejects_unrecognized_payment_fields(self):
        from urllib.parse import urlencode
        form = dict(self.valid, consent="on", payment_receiver="attacker")
        response = self.post(urlencode(form), ctype="application/x-www-form-urlencoded")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(MojPropRequest.objects.count(), 0)
