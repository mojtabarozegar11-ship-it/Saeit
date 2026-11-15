"""A real product-specific inquiry is recorded, not a forged paid order."""
import json
from decimal import Decimal
from django.test import Client, TestCase
from .models import MojPropOffer, MojPropRequest


class DigitalBuyerRequestTests(TestCase):
    def setUp(self):
        self.client = Client(enforce_csrf_checks=True)
        self.token = self.client.get("/moj-prop-intake/").json()["csrf_token"]
        self.payload = {
            "name": "Digital product buyer",
            "email": "buyer@example.org",
            "service": "digital",
            "product_id": 72,
            "horizon": "week",
            "notes": "Please confirm licensing, purchase terms and delivery of this digital book.",
            "consent": True,
            "website": "",
        }

    def submit(self, **changes):
        return self.client.post(
            "/moj-prop-intake/",
            json.dumps({**self.payload, **changes}),
            content_type="application/json",
            HTTP_X_CSRFTOKEN=self.token,
        )

    def test_real_product_inquiry_allocates_id_and_preserves_sku(self):
        for sku in (72, 225, 879):
            with self.subTest(sku=sku):
                response = self.submit(product_id=sku, email=f"buyer{sku}@example.org")
                self.assertEqual(response.status_code, 201)
                record = MojPropRequest.objects.get(request_id=response.json()["request_id"])
                self.assertEqual(record.product_id, sku)
                self.assertEqual(record.route, "digital")
                self.assertEqual(record.status, "new")
        self.assertEqual(MojPropRequest.objects.count(), 3)

    def test_unlisted_or_unsafe_product_never_enters_sales_crm(self):
        for invalid in (None, 0, -1, 999, 2**63, True, 72.0, "72", {}, []):
            with self.subTest(product=invalid):
                response = self.submit(product_id=invalid)
                self.assertEqual(response.status_code, 400)
                self.assertEqual(MojPropRequest.objects.count(), 0)
                self.assertIn("product_id", response.json()["fields"])

    def test_other_service_cannot_smuggle_a_product_id(self):
        for service in ("blueprint", "signals", "brief", "audit"):
            with self.subTest(service=service):
                response = self.submit(service=service, product_id=225)
                self.assertEqual(response.status_code, 400)
                self.assertEqual(MojPropRequest.objects.count(), 0)

    def test_digital_request_requires_sku_even_when_notes_look_legit(self):
        data = dict(self.payload)
        del data["product_id"]
        response = self.client.post(
            "/moj-prop-intake/", json.dumps(data),
            content_type="application/json", HTTP_X_CSRFTOKEN=self.token,
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(MojPropRequest.objects.count(), 0)

    def test_product_quote_does_not_produce_fake_paid_order(self):
        response = self.submit(product_id=225)
        lead = MojPropRequest.objects.get(request_id=response.json()["request_id"])
        offer = MojPropOffer(
            lead=lead,
            title="Taniya children's digital storybook",
            scope="Provide a licensed digital book download under agreed delivery terms, after independently recorded payment.",
            amount=Decimal("4.00"),
            currency="USD",
            delivery_days=2,
        )
        offer.full_clean()
        offer.save()
        self.assertIn("product ID: 225", offer.manual_quote_text)
        self.assertIn("No payment has been collected", offer.manual_quote_text)
        self.assertEqual(lead.status, "new")

    def test_digital_inquiry_requires_csrf_even_when_json_and_consent_valid(self):
        attacker = Client(enforce_csrf_checks=True)
        response = attacker.post(
            "/moj-prop-intake/", json.dumps(self.payload),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(MojPropRequest.objects.count(), 0)

    def test_digital_inquiry_receipt_does_not_leak_in_browser_referrers_or_caches(self):
        response = self.submit(product_id=879)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response["Cache-Control"], "no-store")
        self.assertEqual(response["Referrer-Policy"], "no-referrer")
        self.assertEqual(response["X-Content-Type-Options"], "nosniff")
        self.assertEqual(MojPropRequest.objects.count(), 1)


    def test_digital_buyer_receives_private_receipt_and_can_read_progress(self):
        response = self.submit(product_id=225)
        self.assertEqual(response.status_code, 201)
        token = response.json().get("receipt_token")
        self.assertTrue(token)
        status = self.client.get("/moj-prop-status/", {"receipt_token": token})
        self.assertEqual(status.status_code, 200)
        body = status.json()
        self.assertEqual(body["request_id"], response.json()["request_id"])
        self.assertEqual(body["status"], "new")
        self.assertEqual(body["payment_status"], "not_collected_by_this_service")
        self.assertNotIn("email", body)
        self.assertNotIn("notes", body)
        self.assertNotIn("product_id", body)
        self.assertEqual(status["Referrer-Policy"], "no-referrer")
        self.assertEqual(status["Cache-Control"], "no-store")

    def test_unsigned_or_modified_receipt_never_exposes_a_digital_lead(self):
        response = self.submit(product_id=879)
        token = response.json()["receipt_token"]
        for secret in ("", response.json()["request_id"], token + "x"):
            with self.subTest(secret_present=bool(secret)):
                lookup = self.client.get("/moj-prop-status/", {"receipt_token": secret})
                self.assertEqual(lookup.status_code, 404)
                self.assertNotIn("email", lookup.content.decode("utf-8"))
                self.assertNotIn("notes", lookup.content.decode("utf-8"))


    def test_duplicate_private_receipts_are_rejected_regardless_of_parameter_order(self):
        import urllib.parse
        receipt = self.submit(product_id=72).json()["receipt_token"]
        for values in (("invalid", receipt), (receipt, "invalid"), (receipt, receipt)):
            with self.subTest(order=values[0] == receipt):
                url = "/moj-prop-status/?" + urllib.parse.urlencode([
                    ("receipt_token", value) for value in values
                ])
                response = self.client.get(url)
                self.assertEqual(response.status_code, 404)
                self.assertEqual(response.headers["Cache-Control"], "no-store")
