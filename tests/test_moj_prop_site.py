"""Moj Prop English-first, 20-language and MojPlayWin-only regression tests."""
import unittest
import unicodedata
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

    def test_fifty_trades_and_bots_are_disclosed_in_every_language(self):
        for code in SUPPORTED_CODES:
            with self.subTest(locale=code):
                context=page_context(code)
                self.assertEqual(context["minimum_closed_trades"],50)
                self.assertTrue(context["trader_bots_allowed"])
                self.assertEqual(set(context["trading"]),{"title","body","bots"})
                self.assertTrue(all(context["trading"].values()))
                # Unicode decimal numerals have local glyphs (e.g., فارسی ۵۰);
                # the rule must be verified without forcing English digits.
                body = "".join(
                    str(unicodedata.decimal(ch)) if ch.isdecimal() else ch
                    for ch in context["trading"]["body"]
                )
                self.assertIn("50", body)
                self.assertIn("28", body)
        self.assertIn("ربات",page_context("fa")["trading"]["bots"])
        self.assertIn("bots",page_context("en")["trading"]["bots"])

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
                self.assertEqual(context["social_posts_per_platform_per_challenge"], 1)
                self.assertEqual(context["challenge_days"], 28)
        self.assertIn("Instagram", page_context("en")["social"]["body"])
        self.assertIn("اینستاگرام", page_context("fa")["social"]["body"])

    def test_ten_distinct_plans_appear_in_all_twenty_languages(self):
        for code in SUPPORTED_CODES:
            with self.subTest(locale=code):
                context=page_context(code)
                self.assertEqual(context["number_of_plans"],10)
                self.assertEqual(len(context["challenge_plans"]),10)
                self.assertEqual(len({p["code"] for p in context["challenge_plans"]}),10)
                self.assertEqual(set(context["plans_copy"]),
                    {"title","body","starting","fee","maximum","notice"})
                self.assertTrue(all(context["plans_copy"].values()))
                self.assertEqual(context["challenge_plans"][0]["fee_trx_proposed"],"30")
                self.assertEqual(context["challenge_plans"][-1]["starting_capital_usd"],"35000")
                self.assertTrue(all(not item["checkout_enabled"]
                                    for item in context["challenge_plans"]))
        self.assertIn("پیشنهاد",page_context("fa")["plans_copy"]["notice"])

    def test_owner_active_plan_one_and_nine_funding_holds_in_all_locales(self):
        for code in SUPPORTED_CODES:
            with self.subTest(locale=code):
                context = page_context(code)
                statuses = context["plan_status_copy"]
                self.assertEqual(set(statuses),
                                 {"owner_active", "funding_hold", "owner_disclosure", "owner_fee"})
                self.assertTrue(all(statuses.values()))
                # The primary hero must not contradict the per-plan cards.
                self.assertEqual(context["hero"][4], statuses["owner_active"])
                self.assertIn(statuses["funding_hold"], context["hero"][5])
                self.assertIn(statuses["owner_disclosure"], context["hero"][5])
                self.assertEqual(context["owner_active_plans"], 1)
                self.assertEqual(context["temporary_funding_hold_plans"], 9)
                cards = context["challenge_plans"]
                self.assertTrue(cards[0]["business_active_owner_declared"])
                self.assertTrue(cards[0]["capital_funded_owner_declared"])
                self.assertTrue(cards[0]["entry_fee_owner_confirmed"])
                self.assertTrue(all(not card["entry_fee_owner_confirmed"]
                                    for card in cards[1:]))
                self.assertFalse(cards[0]["funding_independently_verified"])
                self.assertFalse(cards[0]["checkout_enabled"])
                for card in cards[1:]:
                    self.assertTrue(card["temporary_owner_hold"])
                    self.assertFalse(card["business_active_owner_declared"])
                    self.assertFalse(card["checkout_enabled"])

    def test_public_page_mentions_owner_status_without_offering_billing(self):
        from pathlib import Path
        text = (Path(__file__).resolve().parents[1] /
                "core/templates/mojplaywin/moj_prop.html").read_text(encoding="utf-8")
        self.assertIn("plan.business_active_owner_declared", text)
        self.assertIn("plan_status_copy.owner_active", text)
        self.assertIn("plan_status_copy.owner_fee", text)
        self.assertIn("plan_status_copy.funding_hold", text)
        self.assertIn("plan_status_copy.owner_disclosure", text)
        self.assertNotIn('name="wallet_private_key"', text)

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

    def test_public_interest_form_is_not_checkout_or_order_form(self):
        base = Path(__file__).resolve().parents[1]
        page = (base / "core/templates/mojplaywin/moj_prop.html").read_text(encoding="utf-8").lower()
        # A private prelaunch lead MUST allow an opt-in form.  The previous
        # `<form` blanket ban contradicted the POST-only, consent-gated
        # route and made the main prop CI fail after first-interest activation.
        self.assertEqual(page.count("<form "), 1)
        self.assertIn('<form method="post" action="/moj-prop-interest/"', page)
        self.assertIn("{% csrf_token %}", page)
        self.assertIn('name="plan_code" value="moj-prop-01"', page)
        self.assertIn('name="consent_version" value="moj-prop-interest-v1"', page)
        self.assertIn('name="contact_consent" value="yes" required', page)
        self.assertIn('name="email" type="email"', page)
        for forbidden in (
            'walletconnect', 'sendtransaction', 'order/submit',
            'claim-profit', 'name="txid"', 'name="private_key"',
            'name="bank_card"', 'name="amount_sun"',
            '<form method="get" action="/moj-prop-interest/"',
        ):
            self.assertNotIn(forbidden, page)
        self.assertIn('noindex,nofollow', page)
        self.assertIn('hreflang="{{ item.code }}"', page)
        self.assertIn('data-availability="preview-only"', page)
        self.assertIn("mp-social-requirement", page)
        self.assertIn("social.disclosure", page)
        self.assertIn("mp-plan-grid", page)
        self.assertIn("{% for plan in challenge_plans %}", page)
        self.assertIn("plans_copy.notice", page)



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

        def test_web_landing_shows_all_ten_nonpayable_plan_ids(self):
            response=self.client.get("/moj-prop/",HTTP_HOST="mojplaywin.com")
            self.assertEqual(response.status_code,200)
            for number in range(1,11):
                self.assertContains(response,f"MOJ-PROP-{number:02d}")
            self.assertNotContains(response,"Continue to checkout")

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
