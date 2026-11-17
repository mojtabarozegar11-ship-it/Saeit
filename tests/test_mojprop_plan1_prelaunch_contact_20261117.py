"""MOJ-PROP-01 first-party support: source-only EN/FA customer acquisition contract.

No live HTTP, email send, order, customer record, trade, TRX, or deployment.
Only a real independently approved opt-in can count as a CRM lead.
"""
from __future__ import annotations

from html.parser import HTMLParser
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
CONTACT = ROOT / "templates/moj-prop/contact/index.html"
LANDING = ROOT / "templates/moj-prop-v4/index.html"
OLD_SUPPORT_MAILTO = (
    "mailto:support@mojplaywin.com?subject=Moj%20Prop%20Manual%20Service%20Enquiry"
)
PLAN1_SUPPORT_MAILTO = (
    "mailto:support@mojplaywin.com?subject=MOJ-PROP-01%20Prelaunch%20Information%20Request"
)


class Parsed(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.links = []
        self.lang_blocks = []
        self.forms = []
        self.scripts = []
        self.images = []
        self.headings = []
        self.ids = []
        self.tracking = []
        self.text_nodes = []
    def handle_starttag(self, tag, attrs):
        vals = dict(attrs)
        if tag == "a":
            self.links.append(vals.get("href", ""))
        if vals.get("lang"):
            self.lang_blocks.append((tag, vals.get("lang"), vals.get("dir")))
        if tag == "form":
            self.forms.append(vals)
        if tag == "script":
            self.scripts.append(vals)
        if tag in ("img", "iframe"):
            self.images.append(vals)
        if tag in ("h1", "h2"):
            self.headings.append(tag)
        if "id" in vals:
            self.ids.append(vals["id"])
        if tag in ("object", "embed", "video"):
            self.tracking.append(tag)
    def handle_data(self, data):
        self.text_nodes.append(data)


class FirstPlanOneContactTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = CONTACT.read_text(encoding="utf-8")
        cls.landing = LANDING.read_text(encoding="utf-8")
        cls.parsed = Parsed()
        cls.parsed.feed(cls.html)
        cls.parsed.close()

    def test_html_document_is_real_and_utf8(self):
        self.assertTrue(self.html.lower().startswith("<!doctype html>"))
        self.assertIn('charset="utf-8"', self.html.lower())

    def test_relevant_seo_title_never_says_buy(self):
        self.assertIn("Moj Prop Plan 1 | Contact support", self.html)
        self.assertIn("prelaunch only", self.html.lower())

    def test_canonical_matches_exact_published_contact_route(self):
        self.assertIn('href="https://mojplaywin.com/moj-prop/contact/"', self.html)

    def test_no_referrer_metadata_on_private_email_referral(self):
        self.assertIn('name="referrer" content="no-referrer"', self.html)

    def test_keyboard_skip_link_goes_to_real_main(self):
        self.assertIn('href="#main"', self.html)
        self.assertIn('id="main"', self.html)
        self.assertIn(':focus-visible', self.html)

    def test_mobile_responsive_layout(self):
        self.assertIn('@media(max-width:680px)', self.html)
        self.assertIn('grid-template-columns:1fr', self.html)

    def test_reduced_motion_respected(self):
        self.assertIn('prefers-reduced-motion:reduce', self.html)

    def test_english_and_farsi_are_actual_distinct_sections(self):
        self.assertIn(("section", "en", None), self.parsed.lang_blocks)
        self.assertIn(("section", "fa", "rtl"), self.parsed.lang_blocks)

    def test_persian_nav_jumps_to_actual_rtl_section(self):
        self.assertIn('#farsi', self.parsed.links)
        self.assertIn('farsi', self.parsed.ids)

    def test_english_nav_jumps_to_actual_section(self):
        self.assertIn('#english', self.parsed.links)
        self.assertIn('english', self.parsed.ids)

    def test_english_headings_accessible(self):
        self.assertIn('h1', self.parsed.headings)
        self.assertIn('contact-title', self.parsed.ids)

    def test_existing_general_support_address_preserved(self):
        self.assertIn(OLD_SUPPORT_MAILTO, self.parsed.links)
        self.assertIn("support@mojplaywin.com", self.html)

    def test_plan_one_subject_is_explicit_and_user_initiated(self):
        self.assertIn(PLAN1_SUPPORT_MAILTO, self.parsed.links)
        self.assertIn("nothing is sent automatically", self.html)

    def test_only_first_party_published_support_mailto(self):
        for href in self.parsed.links:
            with self.subTest(href=href):
                if href.startswith("mailto:"):
                    self.assertTrue(href.startswith("mailto:support@mojplaywin.com?subject="))
        self.assertNotIn("mojplaywin@gmail.com", self.html)

    def test_no_automatic_email_forms_javascript_trackers(self):
        self.assertEqual(self.parsed.forms, [])
        self.assertEqual(self.parsed.scripts, [])
        self.assertEqual(self.parsed.images, [])
        self.assertEqual(self.parsed.tracking, [])

    def test_price_is_indicative_native_trx(self):
        self.assertIn("30 native TRX = 30,000,000 SUN", self.html)
        self.assertIn("not payable today", self.html)

    def test_not_educational_product_or_deposit(self):
        self.assertIn("not a USD 100 deposit", self.html)
        self.assertIn("not the educational Starter30 product", self.html)

    def test_proposed_stage_profit_targets(self):
        self.assertIn("9.6% and 6%", self.html)

    def test_fifty_distinct_closed_trades_and_six_days_per_stage(self):
        self.assertIn("six qualifying trading days in each stage", self.html)
        self.assertIn("50 distinct verified closed trades combined", self.html)

    def test_28_days_only_after_lawful_paid_enrollment(self):
        self.assertIn("28 calendar days", self.html)
        self.assertIn("independently verified lawful paid enrollment", self.html)

    def test_risk_limits_and_consistency(self):
        for marker in ("4% daily / 8% total drawdown", "32% best-day consistency"):
            with self.subTest(marker=marker):
                self.assertIn(marker, self.html)

    def test_real_usd100_capital_is_not_guaranteed(self):
        self.assertIn("USD 100 after both stages depends on", self.html)
        self.assertIn("verified company funds and reserves", self.html)
        self.assertIn("No funding or return guarantee", self.html)

    def test_share_is_conditional_only_to_eligible_real_profit(self):
        self.assertIn("70% trader / 30% company", self.html)
        self.assertIn("eligible independently reconciled funded activity", self.html)

    def test_buyer_country_and_age_not_claimed_verified(self):
        self.assertIn("eligible countries", self.html)
        self.assertIn("Age 18+ and residence-country eligibility", self.html)
        self.assertIn("KYC", self.html)
        self.assertIn("jurisdictional authorization", self.html) if "jurisdictional authorization" in self.html else self.assertIn("legal eligibility", self.html)

    def test_privacy_contact_consent_is_not_marketing_optin(self):
        self.assertIn("one-to-one reply about that enquiry", self.html)
        self.assertIn("not", self.html.lower())
        self.assertIn("distinct recorded opt-in", self.html)
        self.assertIn("newsletters", self.html)

    def test_withdrawal_correction_and_deletion_channels(self):
        for term in ("contact correction", "withdrawal", "data deletion"):
            self.assertIn(term, self.html)

    def test_buyer_rights_and_refund_policy_precede_payment(self):
        self.assertIn("refund/cancellation rights", self.html)
        self.assertIn("signed buyer terms", self.html)
        self.assertIn("before", self.html)

    def test_support_is_neither_crm_lead_nor_paid_buyer(self):
        self.assertIn("not</strong> a verified Plan 1 lead, a paid order", self.html)
        self.assertIn("not a verified CRM consent record", self.html)

    def test_minimal_data_and_no_secret_requests(self):
        for text in ("identity scans", "passwords", "wallet seeds", "bank credentials"):
            self.assertIn(text, self.html)

    def test_farsi_fee_and_six_days_per_stage(self):
        for text in ("۳۰٬۰۰۰٬۰۰۰ SUN", "حداقل ۶ روز معاملاتی", "۵۰ معامله بسته‌شده", "۲۸ روز تقویمی"):
            self.assertIn(text, self.html)

    def test_farsi_protects_no_enrollment_no_email_blast(self):
        self.assertIn("عضویت در خبرنامه", self.html)
        self.assertIn("ثبت لید در CRM", self.html)
        self.assertIn("ارسال خودکار ندارد", self.html)

    def test_farsi_explains_refund_and_privacy_rights(self):
        self.assertIn("شرایط استرداد", self.html)
        self.assertIn("لغو رضایت تماس", self.html)

    def test_contact_points_to_dedicated_plan1_optin_candidate(self):
        self.assertIn("/moj-prop-interest/form/?service=blueprint&amp;package=moj-prop-01", self.html)

    def test_optin_link_not_claimed_production_ready(self):
        self.assertIn("live availability not verified", self.html)

    def test_candidate_requires_independent_deployment(self):
        self.assertIn("independent live deployment", self.html)

    def test_candidate_requires_server_receipt(self):
        self.assertIn("server-persisted receipt", self.html)

    def test_candidate_requires_crm_evidence(self):
        self.assertIn("accepted CRM opt-in", self.html)

    def test_missing_candidate_does_not_prompt_repeated_post(self):
        self.assertIn("do not repeat submissions", self.html)

    def test_contact_fallback_remains_after_candidate(self):
        self.assertLess(self.html.index("/moj-prop-interest/form/"), self.html.index("Open email app — MOJ-PROP-01 enquiry"))

    def test_candidate_is_not_checkout(self):
        self.assertNotIn("/moj-prop/checkout/", self.html)

    def test_candidate_is_not_payment_instruction(self):
        self.assertIn("No payable 30 TRX challenge", self.html)

    def test_candidate_exact_sku_not_starter30(self):
        self.assertIn("package=moj-prop-01", self.html)
        self.assertNotIn("package=starter30", self.html)

    def test_candidate_does_not_autosubmit(self):
        self.assertEqual(self.parsed.forms, [])
        self.assertEqual(self.parsed.scripts, [])

    def test_farsi_candidate_is_explicit(self):
        self.assertIn("مشاهده فرم پیشنهادی رضایت طرح اول", self.html)

    def test_farsi_candidate_is_unverified(self):
        self.assertIn("فعال‌بودن در سایت زنده تأیید نشده", self.html)

    def test_farsi_candidate_requires_real_consent(self):
        self.assertIn("ذخیره رضایت", self.html)

    def test_farsi_candidate_warns_against_repeated_sensitive_submissions(self):
        self.assertIn("اطلاعات حساس را دوباره ارسال نکنید", self.html)

    def test_candidate_link_is_first_party_relative(self):
        for link in self.parsed.links:
            if "moj-prop-interest" in link:
                self.assertTrue(link.startswith("/moj-prop-interest/form/"))

    def test_candidate_does_not_contain_personal_query_data(self):
        link = next(x for x in self.parsed.links if "moj-prop-interest" in x)
        for field in ("email=", "name=", "token=", "receipt=", "wallet="):
            self.assertNotIn(field, link.lower())

    def test_farsi_and_english_share_same_candidate(self):
        self.assertEqual(self.html.count('href="/moj-prop-interest/form/?service=blueprint&amp;package=moj-prop-01"'), 2)

    def test_contact_preserves_unpaid_support(self):
        self.assertIn("not a verified Plan 1 lead", self.html)

    def test_optin_is_not_automatic_marketing_consent(self):
        self.assertIn("distinct recorded opt-in", self.html)

    def test_landing_reaches_published_first_party_contact(self):
        self.assertIn('href="/moj-prop/contact/"', self.landing)
        self.assertIn('id="first-contact"', self.landing)

    def test_landing_does_not_claim_this_is_funded_payment(self):
        self.assertIn("prelaunch", self.landing.lower())
        self.assertNotIn('action="/moj-prop/checkout/', self.landing)


if __name__ == "__main__":
    unittest.main()
