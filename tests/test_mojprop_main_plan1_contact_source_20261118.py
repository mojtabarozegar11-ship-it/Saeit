"""Offline production-entrypoint guards for the REAL MOJ-PROP-01, not Starter30.

Only source/template validation. These checks never send a prospect, mutate
production, invoice anybody or treat GitHub CI as a live buyer.
"""
from html.parser import HTMLParser
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "templates" / "moj-prop-v4" / "index.html"


class PageElements(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []
        self.forms = {}
        self.sections = set()
        self._section_depth = 0

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "a":
            self.links.append(a.get("href", ""))
        elif tag == "form":
            self.forms[a.get("id", "")] = a
        elif tag == "section" and "id" in a:
            self.sections.add(a["id"])


class MainlinePlanOneContactGuards(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = PAGE.read_text("utf-8")
        cls.doc = PageElements()
        cls.doc.feed(cls.text)
        cls.doc.close()
        cls.start = cls.text.index('id="mojprop01"')
        cls.end = cls.text.index('</section>', cls.start)
        cls.plan = cls.text[cls.start:cls.end]

    def test_01_section_is_present_and_prioritized(self):
        self.assertIn("mojprop01", self.doc.sections)
        self.assertLess(self.start, self.text.index('<section class="hero">'))

    def test_02_correct_challenge_sku(self):
        self.assertIn("MOJ-PROP-01", self.plan)
        self.assertIn("not MOJPROP-STARTER30", self.plan)

    def test_03_challenge_is_not_a_claimed_live_sale(self):
        self.assertIn("Prelaunch only", self.plan)
        self.assertIn("No paid enrollment", self.plan)

    def test_04_exact_proposed_fee_is_not_payable(self):
        self.assertIn("30 native TRX", self.plan)
        self.assertIn("30,000,000 SUN", self.plan)
        self.assertIn("Do not send money today", self.plan)

    def test_05_contract_is_single_global_28d(self):
        self.assertIn("One global 28-calendar-day", self.plan)
        self.assertIn("both phases", self.plan)
        self.assertIn("not 28 days separately", self.plan)

    def test_06_two_stage_target_not_inflated(self):
        self.assertIn("9.6%", self.plan)
        self.assertIn("6% in stage two", self.plan)

    def test_07_fifty_trades_across_both_stages(self):
        self.assertIn("50 authenticated closed trades total across both phases", self.plan)

    def test_08_six_days_per_phase(self):
        self.assertIn("at least 6 independent eligible trading days per phase", self.plan)

    def test_09_risk_limits_visible(self):
        self.assertIn("4% per day / 8% overall", self.plan)
        self.assertIn("32%", self.plan)

    def test_10_broker_consent_and_reserves_not_assumed(self):
        self.assertIn("separate written broker authorization", self.plan)
        self.assertIn("independently verified company reserves", self.plan)

    def test_11_first_contact_is_live_known_page(self):
        self.assertGreaterEqual(self.plan.count('href="/moj-prop/contact/"'), 1)
        self.assertIn("Contact MOJ PROP about Plan 1 (free)", self.plan)

    def test_12_mojplaywin_page_is_english_only(self):
        self.assertNotIn('lang="fa" dir="rtl"', self.text)
        self.assertNotIn("درخواست رایگان شرایط کتبی", self.text)
        self.assertFalse(any(0x0600 <= ord(char) <= 0x06FF for char in self.text))

    def test_13_no_dead_new_form_link(self):
        self.assertNotIn("/moj-prop-interest/form/", self.text)
        self.assertNotIn("/moj-prop/plan1/", self.plan)

    def test_14_nojs_request_fallback_survives_mainline_migration(self):
        # The Django GET route is covered by existing CSRF/no-JS regression
        # tests; retain discoverability and a separate support fallback.
        self.assertIn("/moj-prop-intake/?format=html", self.doc.links)
        self.assertIn(
            "/moj-prop-intake/?format=html&service=blueprint&package=starter-30-trx",
            self.doc.links,
        )
        self.assertIn("/moj-prop/contact/", self.doc.links)
        # Plan1 free information must still use the published support route,
        # never silently turn a generic service inquiry into paid enrollment.
        self.assertNotIn("/moj-prop-intake/?format=html", self.plan)

    def test_15_status_form_hidden_until_actual_api_release(self):
        attrs = self.doc.forms["status-form"]
        self.assertIn("hidden", attrs)
        self.assertEqual(attrs.get("aria-hidden"), "true")
        self.assertEqual(attrs.get("style"), "display:none")

    def test_16_private_receipt_never_sent_via_mail(self):
        self.assertIn("do not send the bearer token by email", self.text)

    def test_17_generic_service_intake_maintained(self):
        self.assertIn("const endpoint='/moj-prop-intake/';", self.text)
        self.assertIn("JSON.stringify(", self.text)
        self.assertIn("credentials:'same-origin'", self.text)

    def test_18_landing_is_a_source_file_not_backend_payment(self):
        self.assertNotIn("tronWeb.trx.sendTransaction(", self.text)
        self.assertNotIn("eth_sendTransaction", self.text)

    def test_19_canonical_domain_is_correct(self):
        self.assertIn('href="https://mojplaywin.com/moj-prop/"', self.text)

    def test_20_no_client_pii_in_plan1_url(self):
        self.assertNotRegex(self.plan, r'href="[^"]+[?&](?:email|token|receipt|name)=')

    def test_21_never_infers_broker_capital_allocation(self):
        self.assertIn("is not available or promised", self.plan)

    def test_22_do_not_send_sensitive_identity_or_wallet_values(self):
        self.assertIn("Do not email passwords, identity scans, wallet keys", self.plan)

    def test_23_classification_cannot_be_education_report(self):
        self.assertIn("not MOJPROP-STARTER30", self.plan)
        self.assertIn("two-stage trading evaluation", self.text.lower())

    def test_24_primary_hero_sales_cta_is_real_plan1_contact(self):
        self.assertIn('class="btn primary" href="/moj-prop/contact/">Ask about real Plan 1', self.text)
        self.assertIn("MOJPLAYWIN / MOJ-PROP-01 / PRELAUNCH", self.text)

    def test_25_old_catalog_is_secondary_not_first_sales_cta(self):
        hero = self.text[self.text.index('<section class="hero">'):self.text.index('</section>', self.text.index('<section class="hero">'))]
        self.assertLess(hero.index('href="/moj-prop/contact/"'), hero.index('href="/moj-prop/catalog/"'))

    def test_26_no_unearned_100_percent_risk_or_payment_bars(self):
        hero = self.text[self.text.index('<section class="hero">'):self.text.index('</section>', self.text.index('<section class="hero">'))]
        self.assertNotIn("<b>100%</b>", hero)
        self.assertNotIn('--w:28%', hero)
        self.assertIn("UNDER REVIEW", hero)

    def test_27_educational_sku_is_separate_and_clearly_labeled(self):
        self.assertIn("SEPARATE EDUCATIONAL SKU · NOT MOJ-PROP-01", self.text)

    def test_24_html_parses_and_main_stays(self):
        self.assertIn("<main", self.text)
        self.assertIn("</main>", self.text)
        self.assertGreater(self.text.count("<section"), 3)


if __name__ == "__main__":
    unittest.main()
