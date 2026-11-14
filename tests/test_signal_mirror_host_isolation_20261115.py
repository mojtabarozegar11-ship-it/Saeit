"""Tenant/locale isolation for all 17 signal mirrors and the single bot identity."""
from unittest.mock import patch

from django.test import SimpleTestCase, RequestFactory, override_settings
from django.http import Http404
from core.financial_brand_pages import BRANDS, financial_brand_page


@override_settings(
    ALLOWED_HOSTS=["mojplaywin.com", "www.mojplaywin.com",
                   "zomorodmelal.ir", ".zomorodmelal.ir",
                   "fakezomorodmelal.ir", "zomorodmelal.ir.example.invalid"],
    USE_X_FORWARDED_HOST=False,
)
class SignalMirrorHostIsolationTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def context(self, brand="saman", host="mojplaywin.com", **meta):
        req = self.factory.get("/saman/market-signals/", HTTP_HOST=host, **meta)
        with patch("core.financial_brand_pages.render",
                   side_effect=lambda request, template, context: context):
            return financial_brand_page(req, brand, "host", "signals")

    def test_all_17_brands_on_english_root_use_one_bot(self):
        self.assertEqual(len(BRANDS), 17)
        for brand, *_ in BRANDS:
            with self.subTest(brand=brand):
                c = self.context(brand=brand)
                self.assertEqual(c["locale"], "en")
                self.assertEqual(c["signal_offer"].agent_identity, "mojtaba.bot.ai")
                self.assertFalse(c["signal_offer"].checkout_enabled)

    def test_all_17_brands_on_farsi_root_use_one_bot(self):
        for brand, *_ in BRANDS:
            with self.subTest(brand=brand):
                c = self.context(brand=brand, host="zomorodmelal.ir")
                self.assertEqual(c["locale"], "fa")
                self.assertEqual(c["signal_offer"].agent_identity, "mojtaba.bot.ai")
                self.assertFalse(c["signal_offer"].checkout_enabled)

    def test_verified_subdomain_uses_farsi_canonical_store(self):
        c = self.context(host="signals.zomorodmelal.ir")
        self.assertEqual(c["locale"], "fa")
        self.assertEqual(c["shop_url"], "/store/")

    def test_www_farsi_host_is_not_treated_as_external(self):
        self.assertEqual(
            self.context(host="www.zomorodmelal.ir")["locale"], "fa"
        )

    def test_similar_unowned_host_does_not_inherit_farsi_landing(self):
        for host in ("fakezomorodmelal.ir",
                     "zomorodmelal.ir.example.invalid"):
            with self.subTest(host=host):
                self.assertEqual(self.context(host=host)["locale"], "en")

    def test_raw_untrusted_forwarded_host_does_not_override_valid_host(self):
        c = self.context(
            host="mojplaywin.com",
            HTTP_X_FORWARDED_HOST="zomorodmelal.ir",
        )
        self.assertEqual(c["locale"], "en")

    def test_signal_mirror_never_grants_payment_based_on_domain(self):
        c = self.context(host="signals.zomorodmelal.ir")
        self.assertFalse(c["signal_offer"].checkout_enabled)
        self.assertIsNone(c["signal_offer"].price_usd)
        self.assertFalse(c["signal_offer"].signal_history_verified)

    def test_unregistered_brand_has_no_signal_landing(self):
        req = self.factory.get("/", HTTP_HOST="mojplaywin.com")
        with self.assertRaises(Http404):
            financial_brand_page(req, "made-up-brand", "host", "signals")
