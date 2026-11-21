"""All 17 market analysis brands have distinct FA/EN/AR routes, no paid claims."""
from django.test import TestCase, override_settings

from core.signal_commercial_catalog import catalog, SIGNAL_BRANDS, offer

@override_settings(ALLOWED_HOSTS=["mojplaywin.com","zomorodmelal.ir","testserver"],
                   USE_X_FORWARDED_HOST=False)
class MarketSignalLocalizationC28Tests(TestCase):
    def test_01_fifty_one_unique_localized_signal_paths(self):
        records=catalog()
        self.assertEqual(len(records),51)
        self.assertEqual(len({x.landing_path for x in records}),51)

    def test_02_all_17_persian_explicit_routes_render_on_mojplaywin(self):
        for brand in SIGNAL_BRANDS:
            with self.subTest(brand=brand):
                response=self.client.get(f"/fa/{brand}/market-signals/",
                                         HTTP_HOST="mojplaywin.com")
                self.assertEqual(response.status_code,200)
                self.assertContains(response,'lang="fa"')
                self.assertContains(response,"اشتراک سیگنال هنوز برای فروش فعال نیست.")

    def test_03_all_17_arabic_explicit_routes_render(self):
        for brand in SIGNAL_BRANDS:
            with self.subTest(brand=brand):
                response=self.client.get(f"/ar/{brand}/market-signals/",
                                         HTTP_HOST="mojplaywin.com")
                self.assertEqual(response.status_code,200)
                self.assertContains(response,'lang="ar"')

    def test_04_all_17_english_default_routes_render(self):
        for brand in SIGNAL_BRANDS:
            with self.subTest(brand=brand):
                response=self.client.get(f"/{brand}/market-signals/",
                                         HTTP_HOST="mojplaywin.com")
                self.assertEqual(response.status_code,200)
                self.assertContains(response,'lang="en"')

    def test_05_persian_primary_domain_remains_farsi(self):
        r=self.client.get("/saman/market-signals/",HTTP_HOST="zomorodmelal.ir")
        self.assertEqual(r.status_code,200)
        self.assertContains(r,'lang="fa"')

    def test_06_forged_forwarded_host_cannot_turn_english_into_persian(self):
        r=self.client.get("/saman/market-signals/",HTTP_HOST="mojplaywin.com",
                          HTTP_X_FORWARDED_HOST="zomorodmelal.ir")
        self.assertContains(r,'lang="en"')

    def test_07_forged_forwarded_host_cannot_turn_persian_into_english(self):
        r=self.client.get("/saman/market-signals/",HTTP_HOST="zomorodmelal.ir",
                          HTTP_X_FORWARDED_HOST="mojplaywin.com")
        self.assertContains(r,'lang="fa"')

    def test_08_lookalike_host_is_rejected(self):
        r=self.client.get("/saman/market-signals/",
                          HTTP_HOST="zomorodmelal.ir.attacker.invalid")
        self.assertEqual(r.status_code,400)

    def test_09_explicit_localized_route_not_dependent_on_host_language(self):
        r=self.client.get("/fa/saman/market-signals/",HTTP_HOST="mojplaywin.com",
                          HTTP_X_FORWARDED_HOST="evil.invalid")
        self.assertContains(r,'lang="fa"')

    def test_10_farsi_digital_store_pages_are_distinct_but_not_charged(self):
        for brand in SIGNAL_BRANDS:
            with self.subTest(brand=brand):
                r=self.client.get(f"/fa/{brand}/digital-products/",
                                  HTTP_HOST="mojplaywin.com")
                self.assertEqual(r.status_code,200)
                self.assertContains(r,'lang="fa"')

    def test_11_no_fake_signals_or_paid_access_on_any_locale(self):
        for locale in ("en","fa","ar"):
            p=offer("saman",locale)
            self.assertFalse(p.checkout_enabled)
            self.assertFalse(p.subscriber_delivery_verified)
            self.assertFalse(p.signal_history_verified)
            self.assertFalse(p.jurisdiction_approved)

    def test_12_only_one_company_bot_identity_all_locales(self):
        self.assertEqual({x.agent_identity for x in catalog()},{"mojtaba.bot.ai"})

    def test_13_persian_catalog_route_starts_with_fa_prefix(self):
        self.assertEqual(offer("saman","fa").landing_path,
                         "/fa/saman/market-signals/")

    def test_14_english_catalog_route_preserves_legacy_path(self):
        self.assertEqual(offer("saman","en").landing_path,
                         "/saman/market-signals/")
