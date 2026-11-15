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
        self.assertEqual(
            signal_page.content.decode("utf-8").count(SIGNAL_INTAKE_PATH), 2
        )

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
