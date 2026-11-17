"""Production-safe source review of the NEW nonpayable v1.4.1 landing page.

No deployment, network, account creation, billing or financial activity.
This is deliberately separate from the pinned historical sidecar installer.
"""
from __future__ import annotations

import re
import unittest
from html.parser import HTMLParser
from pathlib import Path

from prop_firm.plan1_v14_social_or_50_terms import (
    VERSION, review_prospective_terms,
)

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "templates/moj-prop-plan1-v141-prelaunch/index.html"


class PageInspector(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tags = []
        self.meta = []
        self.extras = []

    def handle_starttag(self, tag, attrs):
        attr = dict(attrs)
        self.tags.append(tag)
        if tag == "meta":
            self.meta.append(attr)
        for field in ("href", "src", "action"):
            if field in attr:
                self.extras.append((tag, field, attr[field]))


class V141NonPayableLandingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = PAGE.read_text("utf-8")
        cls.parsed = PageInspector()
        cls.parsed.feed(cls.html)
        cls.terms = review_prospective_terms()

    def test_page_is_new_independent_path(self):
        self.assertEqual(PAGE.name, "index.html")
        self.assertEqual(PAGE.parent.name, "moj-prop-plan1-v141-prelaunch")

    def test_version_exactly_current_new_proposal(self):
        self.assertEqual(self.terms.version, VERSION)
        self.assertIn("v1.4.1-50-OR-28D-DRAFT", self.html)

    def test_no_checkout_or_customer_forms(self):
        self.assertNotIn("form", self.parsed.tags)
        self.assertNotIn("input", self.parsed.tags)
        self.assertNotIn("button", self.parsed.tags)
        self.assertNotIn("select", self.parsed.tags)

    def test_no_network_executing_scripts(self):
        self.assertNotIn("script", self.parsed.tags)
        self.assertNotIn("iframe", self.parsed.tags)
        self.assertNotIn("object", self.parsed.tags)

    def test_no_trackers_or_remotes(self):
        allowed = {\n            ("a", "href", "mailto:mojplaywin@gmail.com?subject=MOJ-PROP-01%20v1.4.1%20Information%20request"),\n            ("a", "href", "mailto:mojplaywin@gmail.com?subject=MOJ-PROP-01%20v1.4.1%20FA%20Information%20request"),\n        }\n        self.assertEqual(set(self.parsed.extras), allowed)\n        self.assertEqual(len(self.parsed.extras), 2)

    def test_csp_blocks_connections_and_forms(self):
        csp = [m.get("content") for m in self.parsed.meta
               if m.get("http-equiv", "").lower() == "content-security-policy"]
        self.assertEqual(len(csp), 1)
        self.assertIn("default-src 'none'", csp[0])
        self.assertIn("connect-src 'none'", csp[0])
        self.assertIn("form-action 'none'", csp[0])

    def test_page_not_indexable_before_legal_review(self):
        robots = [m.get("content") for m in self.parsed.meta if m.get("name") == "robots"]
        self.assertEqual(robots, ["noindex,nofollow,noarchive"])

    def test_30_trx_proposal_no_payment_directions(self):
        self.assertIn("30 TRX", self.html)
        self.assertIn("payment disabled", self.html)
        self.assertIn("۳۰ TRX بومی", self.html)
        self.assertIn("NO PAYMENT", self.html)

    def test_no_wallet_address_or_payment_uri(self):
        self.assertNotRegex(self.html, r"\bT[A-HJ-NP-Za-km-z1-9]{33}\b")
        self.assertNotRegex(self.html, r"tron:(?://|[A-Za-z0-9])")
        self.assertNotIn("checkout/", self.html.lower())

    def test_fifty_total_both_phases(self):
        self.assertEqual(self.terms.closed_trades_total, 50)
        self.assertIn("50 independently reconciled unique CLOSED positions", self.html)
        self.assertIn("not 50 per phase", self.html.lower())
        self.assertIn("در مجموع دو مرحله", self.html)

    def test_six_days_each_sequential_demo_phase(self):
        self.assertIn("Two sequential simulated/demo phases", self.html)
        self.assertIn("SIX verified trading days IN EACH phase", self.html)
        self.assertIn("۶ روز معاملاتی", self.html)

    def test_profit_targets_match_signed_by_code_draft(self):
        self.assertIn("9.6% and 6%", self.html)
        self.assertIn("۹٫۶٪ و ۶٪", self.html)

    def test_best_day_32_pct_visible_to_buyer(self):
        self.assertIn("32% of independently verified net profit", self.html)
        self.assertIn("۳۲٪", self.html)

    def test_drawdown_4_8_percent_visible(self):
        self.assertIn("4% daily and 8% total drawdown", self.html)
        self.assertIn("افت روزانه ۴٪ و افت کل ۸٪", self.html)

    def test_gold_risk_limits_clearly_proposed(self):
        self.assertIn("XAUUSD real-risk framework", self.html)
        self.assertIn("3% nominal risk per order and 8% open aggregate", self.html)
        self.assertIn("سقف اسمی ریسک معامله ۳٪", self.html)

    def test_one_either_instagram_or_facebook(self):
        self.assertIn("At least ONE qualifying original post on EITHER Instagram OR Facebook", self.html)
        self.assertIn("One platform is sufficient; both platforms are NOT required", self.html)
        self.assertIn("اینستاگرام یا فیس‌بوک", self.html)

    def test_28_day_visibility_independent(self):
        self.assertEqual(self.terms.public_post_hours, 672)
        self.assertIn("28 consecutive days (672 hours)", self.html)
        self.assertIn("SEPARATE CLOCKS", self.html)
        self.assertIn("دو ساعت‌شمار مستقل", self.html)

    def test_no_misleading_financial_advertising(self):
        self.assertIn("No fabricated positive endorsement, promise of profits", self.html)
        self.assertIn("افشای اطلاعات شخصی مجاز نیست", self.html)

    def test_lawful_social_review_not_claimed(self):
        self.assertIn("Mandatory financial promotions depend on jurisdiction", self.html)
        self.assertIn("paid enrollment remains ON HOLD", self.html)
        self.assertFalse(self.terms.legal_social_advertising_clearance)

    def test_real_funds_and_broker_access_not_promised(self):
        self.assertIn("There is no proof here of allocated capital", self.html)
        self.assertIn("USD 100", self.html)
        self.assertIn("مجوز کتبی کارگزار", self.html)

    def test_refund_and_kyc_are_unverified(self):
        self.assertIn("refund rights", self.html)
        self.assertIn("KYC/AML", self.html)
        self.assertIn("اطلاعات حقوق مشتری و استرداد وجه هنوز نهایی نشده‌اند", self.html)

    def test_legacy_agreements_unchanged(self):
        self.assertIn("historical v1.2 and draft v1.3 terms are not silently changed", self.html.lower())

    def test_fa_text_has_correct_language_direction(self):
        self.assertIn('id="fa" lang="fa" dir="rtl"', self.html)

    def test_no_deceptive_active_offer_or_email_collection(self):
        self.assertIn("NOT OPEN FOR PAID ENROLLMENT", self.html)
        self.assertIn("cannot accept customer information", self.html)
        self.assertEqual(self.html.lower().count("mailto:"), 2)
        self.assertNotIn("Pay now", self.html)\n        self.assertIn("An email request is", self.html)\n        self.assertIn("NOT", self.html)\n        self.assertIn("اجازه بازاریابی", self.html)

    def test_not_the_educational_product(self):
        self.assertIn("NOT MOJPROP-STARTER30 educational content", self.html)


    def test_interest_link_purpose_is_email_only_nonpayable(self):
        self.assertEqual(self.html.count('href="mailto:'), 2)
        self.assertNotIn("body=", self.html.lower())
        self.assertIn("Optional contact only", self.html)
        self.assertIn("not a purchase", self.html.lower())

    def test_prospect_never_promised_eligibility_or_funding(self):
        self.assertIn("Eligibility, local law, broker approval", self.html)
        self.assertIn("not an active offer", self.html.lower())
        self.assertIn("no automated marketing consent", self.html)

    def test_personal_document_and_secret_warning_is_bilingual(self):
        self.assertIn("Never include identity documents", self.html)
        self.assertIn("مدارک هویتی", self.html)
        self.assertIn("کلید کیف پول", self.html)

    def test_contact_does_not_create_legacy_v12_contract_acceptance(self):
        self.assertIn("v1.4.1%20Information%20request", self.html)
        self.assertIn("v1.4.1%20FA%20Information%20request", self.html)
        self.assertIn("ثبت‌نام، پذیرش قرارداد", self.html)

    def test_page_has_no_http_post_webhook_or_remote_exfiltration(self):
        self.assertNotRegex(self.html, r'https?://')
        self.assertNotIn("fetch(", self.html)
        self.assertNotIn("<form", self.html)
        self.assertNotIn("<input", self.html)
        self.assertNotIn("name=\"email\"", self.html)


if __name__ == "__main__":
    unittest.main()
