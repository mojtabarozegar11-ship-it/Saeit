"""Static production candidate guard for MOJ PROP real Plan 1 prelaunch.

This suite does not activate a TRX invoice or prove live release. It prevents
the formerly promoted educational Starter30 product from reappearing as the
featured offer while the owner pursues only the genuine funded challenge.
"""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "templates/moj-prop-v4/index.html"
URLCONF = ROOT / "config/urls.py"


class RealFundedPlanOneStaticTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.page = PAGE.read_text(encoding="utf-8")
        cls.urls = URLCONF.read_text(encoding="utf-8")

    def test_funded_challenge_is_the_only_featured_product(self):
        self.assertIn('id="plan-one"', self.page)
        self.assertIn("SOLE CURRENT PRODUCT", self.page)
        self.assertIn("MOJ-PROP-01", self.page)

    def test_educational_starter_is_not_misrepresented_as_real_prop(self):
        self.assertNotIn("MOJPROP-STARTER30", self.page)
        self.assertNotIn("ten-session", self.page)
        self.assertNotIn("starter-30-trx", self.page)

    def test_30_trx_is_challenge_fee_not_real_capital(self):
        self.assertIn("30 native TRX", self.page)
        self.assertIn("NOT a $100 deposit", self.page)
        self.assertIn("challenge entrance fee", self.page)

    def test_capital_is_independently_conditional(self):
        self.assertIn("independently verified funds/reserves", self.page)
        self.assertIn("No wallet or payment collection now.", self.page)

    def test_actual_two_stage_risk_terms_present(self):
        for term in ("9.6%", "6%", "50 verified distinct closed", "4% daily / 8% total",
                     "32% best-day", "28 calendar days", "70% trader / 30% company"):
            with self.subTest(term=term):
                self.assertIn(term, self.page)

    def test_root_wsgi_intake_not_static_mount(self):
        self.assertIn("const endpoint='/moj-prop-intake/';", self.page)
        self.assertIn('path("moj-prop-intake/", mojprop_intake', self.urls)
        self.assertNotIn('action="/moj-prop/interest/"', self.page)

    def test_accessible_non_js_request_exists(self):
        self.assertGreaterEqual(self.page.count('/moj-prop-intake/?format=html&amp;service=blueprint&amp;package=moj-prop-01'), 3)
        self.assertIn('/moj-prop-interest/form/', self.page)
        self.assertNotIn('/moj-prop/?service=blueprint&amp;package=moj-prop-01#request', self.page)
        self.assertIn('MOJ-PROP-01 prefilled accessible request (manual review, not enrolment; deployment unverified)', self.page)

    def test_no_js_plan1_fallback_exists_in_current_main_backend(self):
        backend = (ROOT / "core/mojprop_accessible_intake.py").read_text(encoding="utf-8")
        self.assertIn('if packages == ["moj-prop-01"]:', backend)
        self.assertIn('Prelaunch interest only: MOJ-PROP-01', backend)
        self.assertIn('No payment', backend)
        self.assertIn('ACTION = "/moj-prop-intake/?format=html"', backend)

    def test_nonpayable_root_endpoint_is_used_not_unmerged_feature_app(self):
        self.assertIn('path("moj-prop-intake/", mojprop_intake', self.urls)
        self.assertIn('href="/moj-prop-interest/form/"', self.page)
        self.assertNotIn("action='/moj-prop/interest/'", self.page)
        self.assertIn('manual review, not enrolment', self.page)

    def test_generic_desk_is_not_a_plan_one_intake(self):
        self.assertIn("Other service requests — not Plan 1", self.page)
        self.assertIn("Other prop-program design consultation (not MOJ-PROP-01)", self.page)
        self.assertNotIn('<option value="blueprint">Moj Prop Plan 1 prelaunch enquiry</option>', self.page)

    def test_no_live_payment_action_or_wallet_exposure(self):
        self.assertNotIn('action="/moj-prop/checkout/', self.page)
        self.assertNotIn("Send 30 TRX", self.page)
        self.assertIn("no payment", self.page.lower())

    def test_landing_has_canonical_and_source_scoping(self):
        self.assertIn('<link rel="canonical" href="https://mojplaywin.com/moj-prop/">', self.page)
        self.assertEqual(len(re.findall(r'id="plan-one"', self.page)), 1)


    def test_nav_points_to_existing_root_consent_form_not_generic_anchor(self):
        self.assertIn('class="nav-cta" href="/moj-prop/contact/"', self.page)

    def test_no_missing_notes_field_instruction_in_accessible_cta(self):
        self.assertIn("Try the browser-native enquiry (not yet live-verified)", self.page)
        self.assertNotIn("Accessible enquiry (state MOJ-PROP-01 in notes)", self.page)

    def test_no_fake_one_hundred_percent_risk_readiness(self):
        self.assertNotIn("Rule visibility</span><b>100%</b>", self.page)
        self.assertNotIn("Risk framework</span><b>100%</b>", self.page)
        self.assertNotIn('style="--w:100%"', self.page)

    def test_unverified_payment_meter_does_not_imply_progress(self):
        self.assertNotIn('style="--w:28%"', self.page)
        self.assertIn("automatic payment", self.page.lower())

    def test_exact_native_trx_price_units_no_checkout(self):
        self.assertIn("30,000,000 SUN", self.page)
        self.assertNotIn('action="/moj-prop/checkout/', self.page)

    def test_each_phase_six_valid_days_and_fifty_positions(self):
        self.assertIn("six eligible trading days in EACH stage", self.page)
        self.assertIn("50 verified distinct closed positions combined", self.page)

    def test_28_day_clock_requires_lawful_paid_enrollment(self):
        self.assertIn("28 calendar days measured from independently verified paid enrollment after lawful launch", self.page)

    def test_capital_allocation_is_genuinely_conditional(self):
        self.assertIn("No funded brokerage account is available now", self.page)
        self.assertIn("passing both phases", self.page)
        self.assertIn("independently verified funds/reserves", self.page)

    def test_nav_and_main_cta_do_not_imply_enrollment(self):
        self.assertNotIn("Join Plan 1 prelaunch enquiry", self.page)
        self.assertIn("Contact support about future Plan 1 (free)", self.page)
        self.assertIn("Ask Plan 1 support — no purchase", self.page)

    def test_no_public_page_view_confused_with_saved_customer(self):
        self.assertIn("Only a server-accepted consent record with traceable source and privacy notice", self.page)
        self.assertIn("does not record a lead by itself", self.page)

    def test_jurisdiction_and_refund_require_prepayment_terms(self):
        self.assertIn("permitted jurisdiction, signed customer terms", self.page)
        self.assertIn("published refund conditions", self.page)
        self.assertIn("independent merchant-wallet verification", self.page)

    def test_private_data_and_withdrawal_are_disclosed(self):
        self.assertIn("withdrawal of prelaunch contact consent", self.page)
        self.assertIn("never disclose passwords, wallet keys or KYC documents", self.page)



    def test_metadata_factual_prelaunch_not_funded_product(self):
        self.assertIn("Trading evaluation prelaunch — information only", self.page)
        self.assertIn("free prelaunch information only, no payment", self.page)

    def test_marketing_does_not_claim_reserved_account(self):
        self.assertIn("no paid challenge, reserved slot, funded account", self.page)
        self.assertIn("no payment, booking, broker account or capital allocation", self.page)

    def test_no_unverified_bot_autodelivery_claim(self):
        self.assertIn("aims to review requests, disclose blocking conditions", self.page)

    def test_generic_service_consent_is_explicit_and_narrow(self):
        self.assertIn("I consent to storing this other-service request", self.page)
        self.assertIn("No recurring marketing consent is given", self.page)

    def test_generic_service_selector_cannot_choose_real_plan_one(self):
        self.assertNotIn('<option value="blueprint">Moj Prop Plan 1', self.page)
        self.assertIn("Other prop-program design consultation", self.page)

    def test_generic_service_draft_placeholder_excludes_funded_offer(self):
        self.assertNotIn('placeholder="Please ask me about the MOJ-PROP-01', self.page)
        self.assertIn("Describe your other service request", self.page)

    def test_plan_one_url_prefix_not_in_generic_javascript(self):
        self.assertNotIn("planOnePrefix", self.page)
        self.assertNotIn("planOneRequested", self.page)
        self.assertNotIn("syncPlanOne", self.page)

    def test_plan_one_generic_hidden_summary_removed(self):
        self.assertNotIn('id="selected-plan-one"', self.page)
        self.assertIn("Generic services must not infer a funded-challenge SKU", self.page)

    def test_server_persistence_is_required_for_optin_claim(self):
        self.assertIn("not independently verified on production", self.page)
        self.assertIn("not a saved lead", self.page)

    def test_review_consent_not_bulk_marketing(self):
        self.assertIn("does <strong>not</strong> opt you into bulk email", self.page)
        self.assertIn("Voluntarily contacting support authorizes only a response", self.page)

    def test_pii_never_requested_for_prelaunch(self):
        self.assertIn("Never submit a password, ID scan", self.page)
        self.assertIn("wallet key", self.page)

    def test_withdrawal_and_data_rights_are_visible(self):
        self.assertIn("consent withdrawal or a request for personal-data deletion", self.page)
        self.assertIn("/moj-prop/contact/", self.page)

    def test_refund_rules_prepayment_disclosure(self):
        self.assertIn("eventual refund policy must be disclosed before payment", self.page)
        self.assertIn("no paid refund is processed", self.page)

    def test_country_is_a_gate_not_automatic_eligibility(self):
        self.assertIn("Country of residence and regulatory eligibility must be independently checked", self.page)

    def test_persian_section_is_labeled_rtl_and_accessible(self):
        self.assertIn('id="plan-one-fa" lang="fa" dir="rtl"', self.page)
        self.assertIn('aria-labelledby="plan-one-fa-title"', self.page)
        self.assertIn('lang="fa">فارسی</a>', self.page)

    def test_persian_fee_is_not_payable_today(self):
        self.assertIn("۳۰٬۰۰۰٬۰۰۰ SUN", self.page)
        self.assertIn("اکنون هیچ وجهی دریافت نمی‌شود", self.page)

    def test_persian_targets_and_six_days_each_phase(self):
        for phrase in ("۹٫۶٪", "۶٪", "۶ روز معاملاتی واجد شرایط در هر مرحله"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, self.page)

    def test_persian_fifty_trades_and_28_day_clock(self):
        self.assertIn("۵۰ معامله بسته‌شده یکتای تأییدشده", self.page)
        self.assertIn("۲۸ روز تقویمی", self.page)

    def test_persian_drawdown_and_best_day_consistency(self):
        self.assertIn("۴٪ / ۸٪", self.page)
        self.assertIn("۳۲٪", self.page)

    def test_persian_profit_split_and_100_funding_conditional(self):
        self.assertIn("۷۰٪ معامله‌گر و ۳۰٪ شرکت", self.page)
        self.assertIn("۱۰۰ دلار سرمایه واقعی", self.page)
        self.assertIn("تأیید قانونی", self.page)

    def test_persian_privacy_withdrawal_and_no_credentials(self):
        self.assertIn("لغو رضایت", self.page)
        self.assertIn("کلید کیف پول", self.page)
        self.assertIn("شرایط اقامت", self.page)

    def test_persian_cta_remains_nonpayable_nonjs_main_route(self):
        self.assertIn("تماس با پشتیبانی رسمی — رایگان", self.page)
        self.assertIn("فرم در نسخه اصلی ممکن است انگلیسی باشد", self.page)
        self.assertGreaterEqual(self.page.count("package=moj-prop-01"), 4)

    def test_persian_does_not_pretend_20_locals_translated(self):
        self.assertIn("برای ۱۸ زبان دیگر هنوز ترجمه حقوقی تأییدشده منتشر نشده است", self.page)

    def test_persian_section_is_only_one_and_has_no_payment_form(self):
        self.assertEqual(self.page.count('id="plan-one-fa"'), 1)
        self.assertNotIn('action="/moj-prop/payment/"', self.page)

    def test_editorial_guide_is_separate_from_checkout(self):
        self.assertIn('id="prelaunch-guidance"', self.page)
        self.assertNotIn('name="wallet_address"', self.page)



    def test_public_nav_is_real_first_party_support_not_unverified_intake(self):
        self.assertIn('class="nav-cta" href="/moj-prop/contact/"', self.page)
        self.assertNotIn('class="nav-cta" href="/moj-prop-intake/', self.page)

    def test_hero_primary_is_existing_support_path(self):
        self.assertIn('<a class="btn primary" href="/moj-prop/contact/">Ask about Plan 1 via official support</a>', self.page)

    def test_secondary_root_form_remains_distinct_and_transparent(self):
        self.assertIn('Try the prelaunch form (availability unverified)', self.page)
        self.assertIn('Try the browser-native enquiry (not yet live-verified)', self.page)

    def test_no_fake_live_form_consent_or_receipt(self):
        self.assertIn('NOT been independently verified in production', self.page)
        self.assertIn('do not assume a submitted request was saved', self.page)

    def test_first_contact_section_exists_once(self):
        self.assertEqual(self.page.count('id="first-contact"'), 1)
        self.assertIn('aria-labelledby="first-contact-title"', self.page)

    def test_fallback_is_first_party_support_only(self):
        self.assertIn('href="/moj-prop/contact/">Official first-party contact', self.page)
        self.assertNotIn('mailto:', self.page.lower())

    def test_fallback_does_not_transmit_credentials(self):
        self.assertIn('Do not include documents, credentials, bank details or wallet keys', self.page)

    def test_contact_form_is_not_auto_marketing_consent(self):
        self.assertIn('A voluntary request permits a reply about that request only', self.page)
        self.assertIn('updates need separate, affirmative recorded consent', self.page)

    def test_support_reply_does_not_equal_customer(self):
        self.assertIn('Support contact is NOT an accepted Plan 1 CRM lead', self.page)
        self.assertIn('independently confirmed server receipt', self.page)

    def test_country_review_precedes_lawful_offer(self):
        self.assertIn('permitted jurisdictions', self.page)
        self.assertIn('source, jurisdiction and stored opt-in', self.page)

    def test_broken_status_html_not_claimed_as_available(self):
        self.assertIn('public request-status HTML endpoint is not verified as available', self.page)

    def test_navigation_to_customer_support_without_javascript(self):
        self.assertIn('<a href="#first-contact">Prelaunch contact</a>', self.page)

    def test_minimal_personal_information_in_support_route(self):
        self.assertIn('minimum reply details and country of residence if specifically requested', self.page)

    def test_no_priority_or_reply_time_promises(self):
        self.assertIn('no promised response time', self.page.lower())
        self.assertIn('no guaranteed reply time', self.page.lower())

    def test_persian_fallback_labeled_free_and_not_enrollment(self):
        self.assertIn('تماس با پشتیبانی رسمی — رایگان', self.page)
        self.assertIn('این پیام به‌تنهایی ثبت رضایت در CRM', self.page)

    def test_persian_customer_can_find_help(self):
        self.assertIn('مسیر رسمی پشتیبانی و حریم خصوصی منتشرشده', self.page)
        self.assertIn('اگر پاسخ یا رسید واقعی دریافت نشد', self.page)

    def test_persian_form_uncertainty_is_translated(self):
        self.assertIn('فرم اختصاصی علاقه‌مندی طرح اول (انتشار تأیید نشده)', self.page)

    def test_no_plan1_payment_collection_in_fallback(self):
        self.assertNotIn('action="/moj-prop/checkout/', self.page)
        self.assertIn('no transfer to an unverified wallet', self.page)

    def test_consent_is_not_implied_by_support_email(self):
        self.assertIn('A separate, recorded opt-in would be required for future updates', self.page)

    def test_fallback_preserves_nonjs_root_for_after_release(self):
        self.assertGreaterEqual(self.page.count('package=moj-prop-01'), 4)
        self.assertIn('not yet live-verified', self.page)

    def test_site_does_not_claim_public_buyer_exists(self):
        self.assertIn('not validated CRM opt-ins, invoices, reservations or purchases', self.page)

    def test_support_is_not_paid_transaction(self):
        self.assertIn('no payment, no priority reservation, no guaranteed funded account', self.page)

    def test_static_meta_does_not_imply_payable_challenge(self):
        self.assertIn('Voluntary first-party support contact.', self.page)
        self.assertIn('No payment or funded account today.', self.page)

    def test_support_fallback_no_auto_send_or_tracker(self):
        first=self.page.split('<section class="section" id="first-contact"',1)[1].split('</section>',1)[0]
        self.assertNotIn('<script', first.lower())
        self.assertNotIn('<form', first.lower())
        self.assertNotIn('data-email=', first.lower())
        self.assertNotIn('pixel', first.lower())


if __name__ == "__main__":
    unittest.main()
