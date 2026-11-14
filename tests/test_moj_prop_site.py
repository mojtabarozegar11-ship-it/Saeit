"""Moj Prop English-first, 20-language and MojPlayWin-only regression tests."""
import unittest
from pathlib import Path

from prop_firm.moj_prop_page import (
    EXPECTED_GROUPS, SUPPORTED_CODES, catalog, page_context,
)
from prop_firm.rules import LEVELS, POLICY


class MojPropCatalogTests(unittest.TestCase):
    def test_all_twenty_locales_have_all_forty_two_strings(self):
        self.assertEqual(len(SUPPORTED_CODES), 20)
        locales = catalog()
        self.assertEqual(len(locales), 20)
        total = 0
        for code, lang in locales.items():
            for name, length in EXPECTED_GROUPS.items():
                self.assertEqual(len(lang[name]), length, (code, name))
                total += len(lang[name])
        self.assertEqual(total, 840)

    def test_main_language_english_and_rtl_three_languages(self):
        self.assertEqual(SUPPORTED_CODES[0], "en")
        for code in SUPPORTED_CODES:
            item = page_context(code)
            self.assertEqual(item["code"], code)
            self.assertEqual(item["direction"], "rtl" if code in ("fa", "ar", "ur") else "ltr")
            self.assertTrue(item["hero"][5].strip())
            self.assertEqual(sum(path["active"] for path in item["locale_links"]), 1)

    def test_social_rule_disclosed_in_all_twenty_languages(self):
        for code in SUPPORTED_CODES:
            with self.subTest(locale=code):
                context = page_context(code)
                self.assertEqual(
                    set(context["social"]), {"title", "body", "disclosure"}
                )
                self.assertTrue(all(context["social"].values()))
                self.assertEqual(context["social_platforms"], ("instagram", "facebook"))
                self.assertEqual(context["social_daily_post_per_platform"], 1)
        self.assertIn("Instagram", page_context("en")["social"]["body"])
        self.assertIn("اینستاگرام", page_context("fa")["social"]["body"])

    def test_urls_and_breadcrumb_identity(self):
        self.assertEqual(page_context()["canonical_url"], "/moj-prop/")
        self.assertEqual(page_context("ar")["canonical_url"], "/moj-prop/ar/")
        self.assertEqual(page_context("ja")["brand"], "Moj Prop")
        self.assertEqual(page_context("ur")["parent_brand"], "MojPlayWin")
        self.assertEqual(page_context()["bot_id"], "mojtaba.bot.ai")
        self.assertEqual(page_context()["lang_name"], "English")

    def test_all_languages_get_same_canonical_numbers(self):
        for code in SUPPORTED_CODES:
            with self.subTest(code=code):
                page = page_context(code)
                self.assertEqual(len(page["levels"]), 14)
                self.assertEqual(page["levels"][0]["capital_number"], 100)
                self.assertEqual(page["levels"][10]["capital_number"], 50000)
                self.assertEqual(page["levels"][-1]["capital_number"], 100000)
                self.assertEqual(page["entry"], "30 TRX")
                self.assertEqual(page["share"], "70%")
                self.assertEqual([r["value"] for r in page["rules"]], [
                    "9.6%", "6%", "4%", "8%", "6", "32%",
                    "0.8%", "1.6%", "3.6%", "12"
                ])

    def test_source_of_truth_not_duplicate_constants(self):
        self.assertEqual(LEVELS[10], 50000)
        self.assertEqual(page_context()["entry"], str(POLICY.entry_trx) + " TRX")
        self.assertEqual(page_context()["share"], str(POLICY.trader_profit_share_pct) + "%")

    def test_unknown_language_fails_closed(self):
        for code in ("xx", "EN", "../fa", "fa%2f", ""):
            with self.subTest(code=code), self.assertRaises(ValueError):
                page_context(code)

    def test_templates_contain_no_checkout_or_order_form(self):
        base = Path(__file__).resolve().parents[1]
        page = (base / "core/templates/mojplaywin/moj_prop.html").read_text(encoding="utf-8").lower()
        for forbidden in ('<form', 'walletconnect', 'sendtransaction', 'order/submit', 'claim-profit'):
            self.assertNotIn(forbidden, page)
        self.assertIn('noindex,nofollow', page)
        self.assertIn('hreflang="{{ item.code }}"', page)
        self.assertIn('data-availability="preview-only"', page)
        self.assertIn("mp-social-requirement", page)
        self.assertIn("social.disclosure", page)


try:
    from django.test import TestCase, override_settings
except ImportError:
    TestCase = None
else:
    @override_settings(ALLOWED_HOSTS=["mojplaywin.com", "www.mojplaywin.com", "zomorodmelal.ir"])
    class MojPropDjangoViews(TestCase):
        def test_english_route_and_noindex(self):
            result = self.client.get("/moj-prop/", HTTP_HOST="mojplaywin.com")
            self.assertEqual(result.status_code, 200)
            self.assertEqual(result["X-Robots-Tag"], "noindex, nofollow")
            self.assertContains(result, "MOJ PROP")
            self.assertContains(result, 'lang="en"')

        def test_farsi_route_is_rtl_and_same_brand(self):
            result = self.client.get("/moj-prop/fa/", HTTP_HOST="www.mojplaywin.com")
            self.assertEqual(result.status_code, 200)
            self.assertContains(result, 'lang="fa" dir="rtl"')
            self.assertContains(result, "مج پراپ")
            self.assertContains(result, "mojtaba.bot.ai")

        def test_other_host_never_serves_prop_funding_offer(self):
            result = self.client.get("/moj-prop/", HTTP_HOST="zomorodmelal.ir")
            self.assertEqual(result.status_code, 404)

        def test_unknown_language_404(self):
            result = self.client.get("/moj-prop/xx/", HTTP_HOST="mojplaywin.com")
            self.assertEqual(result.status_code, 404)
