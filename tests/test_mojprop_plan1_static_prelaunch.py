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
        self.assertNotIn('/moj-prop-interest/form/', self.page)
        self.assertNotIn('/moj-prop/?service=blueprint&amp;package=moj-prop-01#request', self.page)
        self.assertIn('prefilled accessible Plan 1 request', self.page)

    def test_no_js_plan1_fallback_exists_in_current_main_backend(self):
        backend = (ROOT / "core/mojprop_accessible_intake.py").read_text(encoding="utf-8")
        self.assertIn('if packages == ["moj-prop-01"]:', backend)
        self.assertIn('Prelaunch interest only: MOJ-PROP-01', backend)
        self.assertIn('No payment', backend)
        self.assertIn('ACTION = "/moj-prop-intake/?format=html"', backend)

    def test_nonpayable_root_endpoint_is_used_not_unmerged_feature_app(self):
        self.assertIn('path("moj-prop-intake/", mojprop_intake', self.urls)
        self.assertNotIn('href="/moj-prop-interest/form/"', self.page)
        self.assertNotIn("action='/moj-prop/interest/'", self.page)
        self.assertIn('manual review, not enrolment', self.page)

    def test_legacy_crm_is_labeled_prelaunch_and_nonpayable(self):
        self.assertIn("The explicit product identity is recorded in notes", self.page)
        self.assertIn("not a paid order", self.page)
        self.assertIn("Prelaunch interest ONLY:", self.page)

    def test_no_live_payment_action_or_wallet_exposure(self):
        self.assertNotIn('action="/moj-prop/checkout/', self.page)
        self.assertNotIn("Send 30 TRX", self.page)
        self.assertIn("no payment", self.page.lower())

    def test_landing_has_canonical_and_source_scoping(self):
        self.assertIn('<link rel="canonical" href="https://mojplaywin.com/moj-prop/">', self.page)
        self.assertEqual(len(re.findall(r'id="plan-one"', self.page)), 1)


    def test_nav_points_to_existing_root_consent_form_not_generic_anchor(self):
        self.assertIn('class="nav-cta" href="/moj-prop-intake/?format=html&amp;service=blueprint&amp;package=moj-prop-01"', self.page)

    def test_no_missing_notes_field_instruction_in_accessible_cta(self):
        self.assertIn("Accessible Plan 1 form — no payment", self.page)
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
        self.assertIn("Request free Plan 1 launch information", self.page)
        self.assertIn("Free Plan 1 prelaunch enquiry", self.page)

    def test_no_public_page_view_confused_with_saved_customer(self):
        self.assertIn("Only a server-accepted consent record, not a click or GET 200", self.page)
        self.assertIn("does not record a lead by itself", self.page)

    def test_jurisdiction_and_refund_require_prepayment_terms(self):
        self.assertIn("permitted jurisdiction, signed customer terms", self.page)
        self.assertIn("published refund conditions", self.page)
        self.assertIn("independent merchant-wallet verification", self.page)

    def test_private_data_and_withdrawal_are_disclosed(self):
        self.assertIn("withdrawal of prelaunch contact consent", self.page)
        self.assertIn("never disclose passwords, wallet keys or KYC documents", self.page)



if __name__ == "__main__":
    unittest.main()
