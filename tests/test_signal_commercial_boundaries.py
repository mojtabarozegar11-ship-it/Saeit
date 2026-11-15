"""Public revenue-route integrity checks without creating invoices."""
from django.test import TestCase, override_settings
from core.signal_interest_policy import SIGNAL_BRANDS, SIGNAL_PLAN_CODES, CANONICAL_AGENT
from core.signal_interest_models import SignalInterest
from core.models import PaymentIntent, Order

@override_settings(ALLOWED_HOSTS=[
    "mojplaywin.com", "www.mojplaywin.com", "zomorodmelal.ir", "www.zomorodmelal.ir",
], USE_X_FORWARDED_HOST=False)
class SignalCommercialBoundariesTests(TestCase):
    def test_owner_identity_never_multiplies_by_brand(self):
        self.assertEqual(CANONICAL_AGENT, "mojtaba.bot.ai")
        self.assertEqual(len(SIGNAL_BRANDS),17)
        self.assertEqual(len(set(SIGNAL_BRANDS)),17)
        self.assertEqual(len(SIGNAL_PLAN_CODES),3)

    def test_forwarded_host_cannot_change_language(self):
        result=self.client.get("/saman/market-signals/",secure=True,
             HTTP_HOST="mojplaywin.com",HTTP_X_FORWARDED_HOST="zomorodmelal.ir")
        self.assertEqual(result.status_code,200)
        self.assertContains(result,'lang="en"')

    def test_public_pages_present_interest_without_paid_cta(self):
        result=self.client.get("/zahra/market-signals/",secure=True,
                               HTTP_HOST="mojplaywin.com")
        self.assertEqual(result.status_code,200)
        self.assertContains(result,'data-mojtaba-bot="mojtaba.bot.ai"')
        self.assertNotContains(result,'action="/commerce/trx-easy/start/"')
        self.assertEqual(PaymentIntent.objects.count(),0)
        self.assertEqual(Order.objects.count(),0)
        self.assertEqual(SignalInterest.objects.count(),0)

    def test_headless_page_does_not_issue_request_or_invoice(self):
        for brand in SIGNAL_BRANDS:
            result=self.client.get(f"/{brand}/market-signals/",
                                   HTTP_HOST="mojplaywin.com",secure=True)
            self.assertEqual(result.status_code,200)
        self.assertEqual(SignalInterest.objects.count(),0)
        self.assertEqual(PaymentIntent.objects.count(),0)

    def test_signal_cta_points_to_live_consent_form_in_each_locale(self):
        for path, language, host in (
            ("/saman/market-signals/", "en", "mojplaywin.com"),
            ("/saman/market-signals/", "fa", "zomorodmelal.ir"),
            ("/ar/saman/market-signals/", "ar", "mojplaywin.com"),
        ):
            with self.subTest(path=path, host=host):
                response = self.client.get(path, secure=True, HTTP_HOST=host)
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, 'href="#signal-interest"', count=2)
                self.assertContains(response, 'id="signal-interest"')
                self.assertContains(response, 'action="/market-signals/interest/"')
                self.assertContains(response, f'lang="{language}"')

    def test_store_cta_does_not_route_to_signal_contact_form(self):
        response = self.client.get("/saman/digital-products/",
                                   secure=True, HTTP_HOST="mojplaywin.com")
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'href="#signal-interest"')
        self.assertNotContains(response, 'id="signal-interest"')
