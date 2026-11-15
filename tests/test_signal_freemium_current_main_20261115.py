"""Production-shaped source contracts for free education intake and paid-plan routing.

No external traffic, payment, email, live market prices, or trading is generated.
"""
import json
from pathlib import Path

from django.conf import settings
from django.test import Client, SimpleTestCase, TestCase, override_settings

from core.financial_brand_pages import BRANDS, SIGNAL_FREE_PREVIEW_PATH, SIGNAL_INTAKE_PATH
from core.models import MojPropRequest


ROOT = Path(settings.BASE_DIR)
SIGNALS = ROOT / "templates/moj-prop/signals/index.html"
LEGACY = ROOT / "templates/moj-prop/index.html"
V4 = ROOT / "templates/moj-prop-v4/index.html"


class FreeSignalPageContracts(SimpleTestCase):
    def test_public_free_methodology_example_requires_no_customer_identity(self):
        html = SIGNALS.read_text("utf-8")
        self.assertIn('id="free-preview"', html)
        self.assertIn("Read a free market-analysis example", html)
        self.assertIn("hypothetical learning example", html)
        self.assertIn("not a live signal", html)
        self.assertIn("/moj-prop/?service=signals&amp;tier=free#request", html)

    def test_payment_status_is_honest_and_existing_prices_stay_intact(self):
        from services.mojtaba_signal_catalog import PLANS, build_manual_signal_offer
        html = SIGNALS.read_text("utf-8")
        for code, plan in PLANS.items():
            with self.subTest(plan=code):
                self.assertIn("plan="+code+"#request", html)
                self.assertIn("USD "+format(plan.price_usd, ".2f"), html)
                offer = build_manual_signal_offer(code)
                self.assertIs(offer["payment_enabled"], False)
                self.assertIs(offer["delivery_confirmed"], False)
        self.assertIn("not an active checkout", html)
        self.assertIn("payment and recurring subscription are not active", html)

    def test_both_forms_use_same_csrf_protected_persistent_backend(self):
        for path in (LEGACY, V4):
            with self.subTest(path=str(path)):
                source = path.read_text("utf-8")
                self.assertIn("const endpoint='/moj-prop-intake/';", source)
                self.assertIn(".get('tier')==='free'", source)
                self.assertIn("freeTierRequested", source)
                self.assertIn("response.status!==201", source)
                self.assertIn("X-CSRFToken", source)
                self.assertIn("mojtaba.bot.ai", source)

    @override_settings(ALLOWED_HOSTS=("testserver", "mojplaywin.com", "zomorodmelal.ir"))
    def test_17_brands_and_arabic_routes_preserve_paid_and_free_destinations(self):
        self.assertEqual(SIGNAL_FREE_PREVIEW_PATH, "https://mojplaywin.com/moj-prop/signals/#free-preview")
        for slug, *_ in BRANDS:
            for path in (f"/{slug}/market-signals/", f"/ar/{slug}/market-signals/"):
                with self.subTest(path=path):
                    response = self.client.get(path)
                    self.assertEqual(response.status_code, 200)
                    html = response.content.decode("utf-8")
                    self.assertEqual(html.count('href="'+SIGNAL_INTAKE_PATH+'"'), 2)
                    self.assertEqual(html.count('href="'+SIGNAL_FREE_PREVIEW_PATH+'"'), 1)
                    self.assertIn("mojtaba.bot.ai", html.casefold())

    def test_non_signal_pages_do_not_receive_financial_free_preview(self):
        for path in ("/saman/digital-products/", "/saman/game/"):
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 200)
                self.assertNotIn(SIGNAL_FREE_PREVIEW_PATH, response.content.decode("utf-8"))


class FreeSignalIntakePersistenceTests(TestCase):
    def setUp(self):
        self.client = Client(enforce_csrf_checks=True)
        token_get = self.client.get("/moj-prop-intake/")
        self.assertEqual(token_get.status_code, 200)
        self.token = token_get.json()["csrf_token"]

    def post(self, **overrides):
        payload = {
            "name": "Research Request Buyer",
            "email": "free-request@example.com",
            "service": "signals",
            "horizon": "review",
            "notes": (
                "Requested free educational example: one-off manual review; no subscription "
                "or live trade. Gold research methodology only, no payment."
            ),
            "website": "",
            "consent": True,
        }
        payload.update(overrides)
        return self.client.post(
            "/moj-prop-intake/",
            data=json.dumps(payload),
            content_type="application/json",
            HTTP_X_CSRFTOKEN=self.token,
            HTTP_X_REAL_IP="198.51.100.42",
        )

    def test_real_backend_creates_persistent_free_research_request_not_entitlement(self):
        response = self.post()
        self.assertEqual(response.status_code, 201)
        body = response.json()
        self.assertTrue(body["ok"])
        self.assertTrue(body["request_id"].startswith("MOJPROP-"))
        self.assertEqual(body["next_step"], "manual_review")
        record = MojPropRequest.objects.get(request_id=body["request_id"])
        self.assertEqual(record.route, "signals")
        self.assertIn("Requested free educational example", record.notes)
        self.assertTrue(record.consent)
        self.assertEqual(record.status, "new")
        self.assertNotIn("payment_verified", body)
        self.assertNotIn("subscription_active", body)

    def test_missing_consent_rejects_free_contact_record(self):
        response = self.post(consent=False)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(MojPropRequest.objects.count(), 0)
