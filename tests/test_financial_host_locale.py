"""Financial/signal brand locale follows the verified merchant host only.

Raw forwarded/attacker-suffixed hosts must never change jurisdiction-facing
financial copy or the canonical mojtaba.bot.ai service identity.
"""
from unittest.mock import patch

from django.core.exceptions import DisallowedHost
from django.http import Http404
from django.test import RequestFactory, SimpleTestCase, override_settings

from core.financial_brand_pages import financial_brand_page


@override_settings(
    ALLOWED_HOSTS=[
        "mojplaywin.com", "www.mojplaywin.com", "zomorodmelal.ir",
        "www.zomorodmelal.ir", "attacker-zomorodmelal.ir",
        "zomorodmelal.ir.attacker.example", "saman.mojplaywin.com",
        "signals.zomorodmelal.ir",
    ],
    USE_X_FORWARDED_HOST=False,
)
class FinancialBrandHostLocaleTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def rendered(self, host, *, forwarded=None, locale="host", brand="saman"):
        request = self.factory.get("/saman/market-signals/",
                                   HTTP_HOST=host, secure=True)
        if forwarded is not None:
            request.META["HTTP_X_FORWARDED_HOST"] = forwarded
        with patch("core.financial_brand_pages.render") as render:
            financial_brand_page(request, brand, locale, "signals")
            self.assertEqual(render.call_count, 1)
            return render.call_args.args[2]

    def test_company_exact_host_is_persian(self):
        self.assertEqual(self.rendered("zomorodmelal.ir")["locale"], "fa")

    def test_company_www_host_is_persian(self):
        self.assertEqual(self.rendered("www.zomorodmelal.ir")["locale"], "fa")

    def test_mojplaywin_exact_host_is_english(self):
        self.assertEqual(self.rendered("mojplaywin.com")["locale"], "en")

    def test_mojplaywin_www_host_is_english(self):
        self.assertEqual(self.rendered("www.mojplaywin.com")["locale"], "en")

    def test_attacker_prefix_cannot_serve_financial_brand(self):
        with self.assertRaises(Http404):
            self.rendered("attacker-zomorodmelal.ir")

    def test_attacker_suffix_cannot_serve_financial_brand(self):
        with self.assertRaises(Http404):
            self.rendered("zomorodmelal.ir.attacker.example")

    def test_owned_saman_subdomain_keeps_english_financial_copy(self):
        self.assertEqual(self.rendered("saman.mojplaywin.com")["locale"], "en")

    def test_owned_company_subdomain_keeps_persian_financial_copy(self):
        self.assertEqual(
            self.rendered("signals.zomorodmelal.ir")["locale"], "fa")

    def test_explicit_arabic_locale_cannot_override_foreign_merchant_host(self):
        with self.assertRaises(Http404):
            self.rendered("attacker-zomorodmelal.ir", locale="ar")

    def test_forwarded_host_untrusted_header_cannot_override_real_host(self):
        got = self.rendered("mojplaywin.com",
                            forwarded="zomorodmelal.ir")
        self.assertEqual(got["locale"], "en")

    def test_forwarded_host_untrusted_header_cannot_demote_company_host(self):
        got = self.rendered("zomorodmelal.ir",
                            forwarded="mojplaywin.com")
        self.assertEqual(got["locale"], "fa")

    def test_disallowed_host_is_rejected_by_django_before_brand_rendering(self):
        request = self.factory.get(
            "/saman/market-signals/", HTTP_HOST="not-owned.example",
            secure=True)
        with patch("core.financial_brand_pages.render") as render:
            with self.assertRaises(DisallowedHost):
                financial_brand_page(request, "saman", "host", "signals")
            render.assert_not_called()

    def test_explicit_arabic_locale_still_works(self):
        context = self.rendered("mojplaywin.com", locale="ar")
        self.assertEqual(context["locale"], "ar")
        self.assertEqual(context["page_direction"], "rtl")

    def test_singular_bot_identity_across_merchant_hosts(self):
        for host in ("mojplaywin.com", "zomorodmelal.ir"):
            with self.subTest(host=host):
                context = self.rendered(host)
                self.assertEqual(
                    context["signal_offer"].agent_identity,
                    "mojtaba.bot.ai",
                )
