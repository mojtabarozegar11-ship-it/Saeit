import json

from django.test import Client, TestCase

from .models import MojPropRequest


class MojPropIntakeTests(TestCase):
    def setUp(self):
        self.client = Client(enforce_csrf_checks=True)
        response = self.client.get("/moj-prop/intake/")
        self.assertEqual(response.status_code, 200)
        self.csrf_token = response.json()["csrf_token"]

    def payload(self, **overrides):
        value = {
            "name": "Moj Prop Client",
            "email": "client@example.com",
            "service": "brief",
            "horizon": "week",
            "notes": "Need a dated gold market brief for educational review.",
            "consent": True,
            "website": "",
        }
        value.update(overrides)
        return value

    def post(self, value):
        return self.client.post(
            "/moj-prop/intake/",
            data=json.dumps(value),
            content_type="application/json",
            HTTP_X_CSRFTOKEN=self.csrf_token,
            HTTP_X_REAL_IP="198.51.100.40",
        )

    def test_valid_request_is_stored_for_manual_review(self):
        response = self.post(self.payload())
        self.assertEqual(response.status_code, 201)
        body = response.json()
        self.assertTrue(body["ok"])
        self.assertTrue(body["request_id"].startswith("MOJPROP-"))
        record = MojPropRequest.objects.get(request_id=body["request_id"])
        self.assertEqual(record.status, "new")
        self.assertEqual(record.route, "brief")
        self.assertEqual(record.email, "client@example.com")

    def test_invalid_consent_is_rejected(self):
        response = self.post(self.payload(consent=False))
        self.assertEqual(response.status_code, 400)
        self.assertIn("consent", response.json()["fields"])
        self.assertEqual(MojPropRequest.objects.count(), 0)

    def test_honeypot_is_rejected(self):
        response = self.post(self.payload(website="bot-filled"))
        self.assertEqual(response.status_code, 400)
        self.assertEqual(MojPropRequest.objects.count(), 0)

    def test_invalid_email_is_rejected(self):
        response = self.post(self.payload(email="not-an-email"))
        self.assertEqual(response.status_code, 400)
        self.assertIn("email", response.json()["fields"])

    def test_rate_limit_returns_retry_after_header_and_does_not_create_sixth_lead(self):
        for index in range(5):
            response = self.post(self.payload(name=f"Manual Review Buyer {index}"))
            self.assertEqual(response.status_code, 201)
        rejected = self.post(self.payload(name="Manual Review Buyer Six"))
        self.assertEqual(rejected.status_code, 429)
        self.assertEqual(rejected.headers["Retry-After"], "600")
        self.assertEqual(rejected.json()["retry_after"], 600)
        self.assertEqual(rejected.headers["Cache-Control"], "no-store")
        self.assertEqual(MojPropRequest.objects.count(), 5)

