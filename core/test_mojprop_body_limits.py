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
        self.assertEqual(response.status_code, 400)
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
