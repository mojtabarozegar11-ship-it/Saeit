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
        self.assertIn("verified funds, broker contract", self.page)
        self.assertIn("No wallet or payment collection now.", self.page)

    def test_actual_two_stage_risk_terms_present(self):
        for term in ("9.6%", "6%", "50 verified distinct closed", "4% daily / 8% total",
                     "32% best-day", "28 days", "70% trader / 30% company"):
            with self.subTest(term=term):
                self.assertIn(term, self.page)

    def test_root_wsgi_intake_not_static_mount(self):
        self.assertIn("const endpoint='/moj-prop-intake/';", self.page)
        self.assertIn('path("moj-prop-intake/", mojprop_intake', self.urls)
        self.assertNotIn('action="/moj-prop/interest/"', self.page)

    def test_accessible_non_js_request_exists(self):
        self.assertGreaterEqual(self.page.count('/moj-prop-interest/form/'), 3)
        self.assertNotIn('/moj-prop-intake/?format=html&amp;service=blueprint&amp;package=moj-prop-01', self.page)
        self.assertNotIn('/moj-prop/?service=blueprint&amp;package=moj-prop-01#request', self.page)
        self.assertIn('dedicated Plan 1 consent form', self.page)

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


if __name__ == "__main__":
    unittest.main()
