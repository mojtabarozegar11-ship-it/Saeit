from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
HOME = ROOT / "core" / "templates" / "mojplaywin" / "home.html"
MOJ_PROP = ROOT / "templates" / "moj-prop-v4" / "index.html"
STARTER30 = ROOT / "templates" / "moj-prop-v4" / "starter-30-trx" / "index.html"


class Starter30NavigationAndPaymentCopyTests(unittest.TestCase):
    def test_home_directly_exposes_canonical_page_and_checkout(self):
        source = HOME.read_text(encoding="utf-8")
        self.assertIn('href="/moj-prop/starter-30-trx/"', source)
        self.assertIn('href="/mojprop-starter30-checkout/"', source)
        self.assertIn('id="starter30-featured"', source)

    def test_moj_prop_separates_plan1_prelaunch_from_starter30_payment(self):
        source = MOJ_PROP.read_text(encoding="utf-8")
        self.assertIn('href="/moj-prop/starter-30-trx/">Open the canonical Starter30 page', source)
        self.assertIn('href="/moj-prop/rules/">Read the published Starter30 rules', source)
        self.assertIn("MOJ-PROP-01 (the proposed two-stage live-account route) remains prelaunch", source)
        self.assertIn("Starter30 payment:", source)
        self.assertNotIn("paid challenges, live accounts, KYC, automatic payment and profit guarantees are not active", source)

    def test_starter30_uses_current_payment_message(self):
        source = STARTER30.read_text(encoding="utf-8")
        self.assertIn("payment admission under independent verification", source)
        self.assertIn("Current status:</strong> Starter30 is the separate 60-day simulated product.", source)
        self.assertNotIn("Current status:</strong> payable simulated challenge", source)


if __name__ == "__main__":
    unittest.main()
