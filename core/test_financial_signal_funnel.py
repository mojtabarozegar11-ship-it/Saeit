"""Every financial-brand signal subsite must feed the canonical Mojtaba.bot.ai intake."""
from django.test import SimpleTestCase

from core.financial_brand_pages import BRANDS, SIGNAL_INTAKE_PATH


class FinancialBrandSignalFunnelTests(SimpleTestCase):
    def test_catalog_and_signal_page_use_the_same_prefilled_route(self):
        catalog = self.client.get("/moj-prop/catalog/")
        self.assertEqual(catalog.status_code, 200)
        self.assertIn(
            'href="/moj-prop/?service=signals#request">Request a signal note',
            catalog.content.decode("utf-8"),
        )
        signal_page = self.client.get("/moj-prop/signals/")
        self.assertEqual(signal_page.status_code, 200)
        self.assertEqual(signal_page.content.decode("utf-8").count(SIGNAL_INTAKE_PATH), 2)

    def test_all_host_signal_subsites_use_the_canonical_signal_intake(self):
        for slug, *_ in BRANDS:
            with self.subTest(slug=slug):
                response = self.client.get(f"/{slug}/market-signals/")
                self.assertEqual(response.status_code, 200)
                html = response.content.decode("utf-8")
                self.assertEqual(html.count(SIGNAL_INTAKE_PATH), 2)
                self.assertIn("mojtaba.bot.ai", html)
                self.assertNotIn('href="/store/"', html)
                self.assertNotIn('href="/commerce/"', html)

    def test_all_arabic_signal_subsites_use_the_same_intake(self):
        for slug, *_ in BRANDS:
            with self.subTest(slug=slug):
                response = self.client.get(f"/ar/{slug}/market-signals/")
                self.assertEqual(response.status_code, 200)
                html = response.content.decode("utf-8")
                self.assertEqual(html.count(SIGNAL_INTAKE_PATH), 2)
                self.assertIn("mojtaba.bot.ai", html)

    def test_store_subsite_keeps_its_store_destination(self):
        response = self.client.get("/saman/digital-products/")
        self.assertEqual(response.status_code, 200)
        html = response.content.decode("utf-8")
        self.assertIn('href="/commerce/"', html)
        self.assertNotIn(SIGNAL_INTAKE_PATH, html)

    def test_each_catalog_offer_prefills_its_own_distinct_service(self):
        html = self.client.get("/moj-prop/catalog/").content.decode("utf-8")
        offers = {
            "blueprint": "Request a blueprint",
            "brief": "Request a market brief",
            "signals": "Request a signal note",
            "audit": "Request an audit",
        }
        for code, label in offers.items():
            with self.subTest(route=code):
                self.assertIn(
                    f'href="/moj-prop/?service={code}#request">{label}',
                    html,
                )
        # No named offer silently defaults to the first form option.
        for label in offers.values():
            self.assertNotIn(f'href="/moj-prop/#request">{label}', html)

    def test_signal_handoff_contract_is_never_a_checkout_or_auto_trade(self):
        html = self.client.get("/moj-prop/signals/").content.decode("utf-8")
        self.assertIn("live feed and automatic subscription are not active", html)
        self.assertIn("mojtaba.bot.ai", html)
        self.assertNotIn("guaranteed profit", html.lower())
