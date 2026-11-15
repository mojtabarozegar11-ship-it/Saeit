"""Freemium signal request funnel: free education and paid quote stay auditable."""
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase


ROOT = Path(settings.BASE_DIR)
SIGNALS = ROOT / "templates/moj-prop/signals/index.html"
FORMS = (
    ROOT / "templates/moj-prop/index.html",
    ROOT / "templates/moj-prop-v4/index.html",
)


class FreemiumSignalFunnelContractTests(SimpleTestCase):
    def test_free_example_is_public_and_clearly_not_a_live_signal(self):
        html = SIGNALS.read_text(encoding="utf-8")
        self.assertIn('id="free-preview"', html)
        self.assertIn("Read a free market-analysis example", html)
        self.assertIn("hypothetical learning example", html)
        self.assertIn("not a live signal", html)
        self.assertIn(
            "/moj-prop/?service=signals&amp;tier=free#request",
            html,
        )
        self.assertNotIn("Sign up for guaranteed", html)

    def test_existing_paid_plans_remain_quoted_not_fake_checkout(self):
        from services.mojtaba_signal_catalog import PLANS
        html = SIGNALS.read_text(encoding="utf-8")
        for identifier, plan in PLANS.items():
            with self.subTest(identifier=identifier):
                self.assertIn("plan="+identifier+"#request", html)
                self.assertIn("USD "+format(plan.price_usd, ".2f"), html)
        self.assertIn("not an active checkout", html)
        self.assertIn("payment and recurring subscription are not active", html)

    def test_both_forms_use_existing_real_intake_with_free_request_prefill(self):
        for path in FORMS:
            with self.subTest(path=path.name):
                content = path.read_text(encoding="utf-8")
                self.assertIn("const endpoint='/moj-prop-intake/';", content)
                self.assertIn("freeTierRequested", content)
                self.assertIn(".get('tier')==='free'", content)
                self.assertIn("One-off FREE educational market-brief example request", content)
                self.assertIn("not a live signal, a mailing-list subscription", content)
                self.assertIn("serviceSelect.value=requestedService", content)
                self.assertIn("signalPrefill='';", content)
                self.assertIn("notes.value===signalPrefill", content)
                self.assertIn("response.status!==201", content)

    def test_paid_plan_identifier_is_preserved_in_both_forms(self):
        for path in FORMS:
            with self.subTest(path=path.name):
                text = path.read_text(encoding="utf-8")
                for identifier in ("education-weekly", "education-monthly", "education-quarterly"):
                    self.assertIn(identifier, text)
                self.assertIn("requestedPlan+", text)
                self.assertIn("Object.prototype.hasOwnProperty.call(", text)
        v4 = FORMS[1].read_text(encoding="utf-8")
        self.assertIn("exact plan ID: '+requestedPlan+", v4)

    def test_no_new_entitlement_or_marketing_automation_claim(self):
        for path in FORMS:
            content = path.read_text(encoding="utf-8")
            self.assertNotIn("subscription_activated", content)
            self.assertNotIn("autoTrade(", content)
            self.assertNotIn("sendNewsletter(", content)
        from services.mojtaba_signal_catalog import build_manual_signal_offer
        offer = build_manual_signal_offer("education-weekly")
        self.assertIs(offer["payment_enabled"], False)
        self.assertIs(offer["delivery_confirmed"], False)


class BrandFreeEducationReferralTests(SimpleTestCase):
    def test_all_brands_offer_free_preview_without_changing_paid_referral(self):
        from core.financial_brand_pages import BRANDS, SIGNAL_FREE_PREVIEW_PATH, SIGNAL_INTAKE_PATH
        from django.test import override_settings
        self.assertEqual(
            SIGNAL_FREE_PREVIEW_PATH,
            "https://mojplaywin.com/moj-prop/signals/#free-preview",
        )
        with override_settings(ALLOWED_HOSTS=("testserver", "zomorodmelal.ir", "mojplaywin.com")):
            for slug, *_ in BRANDS:
                for path in (f"/{slug}/market-signals/", f"/ar/{slug}/market-signals/"):
                    with self.subTest(path=path):
                        result = self.client.get(path)
                        self.assertEqual(result.status_code, 200)
                        page = result.content.decode("utf-8")
                        self.assertEqual(page.count('href="'+SIGNAL_INTAKE_PATH+'"'), 2)
                        self.assertEqual(page.count('href="'+SIGNAL_FREE_PREVIEW_PATH+'"'), 1)
                        self.assertIn("mojtaba.bot.ai", page.casefold())

    def test_store_and_game_brands_do_not_receive_free_signal_links(self):
        from core.financial_brand_pages import SIGNAL_FREE_PREVIEW_PATH
        for route in ("/saman/digital-products/", "/saman/game/"):
            with self.subTest(route=route):
                response = self.client.get(route)
                self.assertEqual(response.status_code, 200)
                self.assertNotIn(SIGNAL_FREE_PREVIEW_PATH, response.content.decode("utf-8"))
