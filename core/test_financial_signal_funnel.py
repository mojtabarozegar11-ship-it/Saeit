"""Every financial-brand signal subsite must feed the canonical Mojtaba.bot.ai intake."""
from pathlib import Path
from urllib.parse import urlsplit

from django.test import SimpleTestCase, override_settings

from core.financial_brand_pages import BRANDS, SIGNAL_INTAKE_PATH

PUBLIC_STATIC_ROOT = Path(__file__).resolve().parents[1] / "templates"
CATALOG = PUBLIC_STATIC_ROOT / "moj-prop-v4/catalog/index.html"
SIGNAL_DESK = PUBLIC_STATIC_ROOT / "moj-prop/signals/index.html"
LOCAL_SIGNAL_INTAKE = "/moj-prop/?service=signals#request"


class FinancialBrandSignalFunnelTests(SimpleTestCase):
    def test_canonical_inquiry_is_absolute_on_cross_domain_subsites(self):
        # The branded pages are shared across many independently hosted
        # domains. A relative /moj-prop/ link would resolve to the wrong host.
        self.assertEqual(
            SIGNAL_INTAKE_PATH,
            "https://mojplaywin.com/moj-prop/?service=signals#request",
        )
        self.assertNotIn("checkout", SIGNAL_INTAKE_PATH)
        self.assertNotIn("mojtaba.bot.ai/", SIGNAL_INTAKE_PATH)

    @override_settings(ALLOWED_HOSTS=("testserver", "zomorodmelal.ir", "mojplaywin.com"))
    def test_cross_domain_brand_ctas_point_at_mojplaywin_not_local_subsite(self):
        for hostname in ("zomorodmelal.ir", "mojplaywin.com"):
            response = self.client.get(
                "/saman/market-signals/", HTTP_HOST=hostname,
            )
            with self.subTest(hostname=hostname):
                self.assertEqual(response.status_code, 200)
                html = response.content.decode("utf-8")
                self.assertEqual(html.count('href="' + SIGNAL_INTAKE_PATH + '"'), 2)
                self.assertNotIn('href="/moj-prop/?service=signals#request"', html)
                self.assertNotIn('href="/commerce/"', html)

    def test_catalog_and_signal_page_use_the_same_prefilled_route(self):
        # The catalog and signal desk are static release artifacts, NOT
        # Django urlpatterns. GET via Django test client correctly yields 404.
        catalog = CATALOG.read_text(encoding="utf-8")
        self.assertIn(
            'href="/moj-prop/?service=signals#request">Request a signal note',
            catalog,
        )
        signal_page = SIGNAL_DESK.read_text(encoding="utf-8")
        self.assertEqual(signal_page.count(LOCAL_SIGNAL_INTAKE), 2)
        target = urlsplit(SIGNAL_INTAKE_PATH)
        self.assertEqual(
            target.path + "?" + target.query + "#" + target.fragment,
            LOCAL_SIGNAL_INTAKE,
        )

    def test_all_host_signal_subsites_use_the_canonical_signal_intake(self):
        for slug, *_ in BRANDS:
            with self.subTest(slug=slug):
                response = self.client.get(f"/{slug}/market-signals/")
                self.assertEqual(response.status_code, 200)
                html = response.content.decode("utf-8")
                self.assertEqual(html.count(SIGNAL_INTAKE_PATH), 2)
                self.assertIn("mojtaba.bot.ai", html.casefold())
                self.assertNotIn('href="/store/"', html)
                self.assertNotIn('href="/commerce/"', html)

    def test_all_arabic_signal_subsites_use_the_same_intake(self):
        for slug, *_ in BRANDS:
            with self.subTest(slug=slug):
                response = self.client.get(f"/ar/{slug}/market-signals/")
                self.assertEqual(response.status_code, 200)
                html = response.content.decode("utf-8")
                self.assertEqual(html.count(SIGNAL_INTAKE_PATH), 2)
                self.assertIn("mojtaba.bot.ai", html.casefold())

    def test_store_subsite_keeps_its_store_destination(self):
        response = self.client.get("/saman/digital-products/")
        self.assertEqual(response.status_code, 200)
        html = response.content.decode("utf-8")
        self.assertIn('href="/commerce/"', html)
        self.assertNotIn(SIGNAL_INTAKE_PATH, html)

    def test_each_catalog_offer_prefills_its_own_distinct_service(self):
        html = CATALOG.read_text(encoding="utf-8")
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
        html = SIGNAL_DESK.read_text(encoding="utf-8")
        self.assertIn("live feed and automatic subscription are not active", html)
        self.assertIn("mojtaba.bot.ai", html)
        self.assertNotIn("guaranteed profit", html.lower())

    @override_settings(
        ALLOWED_HOSTS=("testserver", "mojplaywin.com", "zomorodmelal.ir", "reports.zomorodmelal.ir"),
        USE_X_FORWARDED_HOST=False,
    )
    def test_untrusted_forwarded_host_does_not_switch_mojplaywin_language(self):
        response = self.client.get(
            "/saman/market-signals/",
            HTTP_HOST="mojplaywin.com",
            HTTP_X_FORWARDED_HOST="zomorodmelal.ir",
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn('lang="en"', response.content.decode("utf-8"))

    @override_settings(
        ALLOWED_HOSTS=("testserver", "zomorodmelal.ir", "reports.zomorodmelal.ir"),
        USE_X_FORWARDED_HOST=False,
    )
    def test_exact_zomorod_host_and_subdomain_receive_persian_language(self):
        for host in ("zomorodmelal.ir", "reports.zomorodmelal.ir"):
            with self.subTest(host=host):
                response = self.client.get("/saman/market-signals/", HTTP_HOST=host)
                self.assertEqual(response.status_code, 200)
                self.assertIn('lang="fa"', response.content.decode("utf-8"))

    @override_settings(
        ALLOWED_HOSTS=("testserver", "fake-zomorodmelal.ir"),
        USE_X_FORWARDED_HOST=False,
    )
    def test_lookalike_host_cannot_force_persian_or_spoof_a_financial_brand(self):
        response = self.client.get("/saman/market-signals/", HTTP_HOST="fake-zomorodmelal.ir")
        self.assertEqual(response.status_code, 200)
        self.assertIn('lang="en"', response.content.decode("utf-8"))
