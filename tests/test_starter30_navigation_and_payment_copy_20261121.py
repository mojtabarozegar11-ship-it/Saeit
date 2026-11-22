from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
HOME = ROOT / "core" / "templates" / "mojplaywin" / "home.html"
MOJ_PROP = ROOT / "templates" / "moj-prop-v4" / "index.html"
STARTER30 = ROOT / "templates" / "moj-prop-v4" / "starter-30-trx" / "index.html"


class Starter30NavigationAndPaymentCopyTests(unittest.TestCase):
    def test_home_links_canonical_rules_and_free_request_not_disabled_checkout(self):
        source = HOME.read_text(encoding="utf-8")
        self.assertIn('href="/moj-prop/starter-30-trx/"', source)
        self.assertIn('id="starter30-featured"', source)
        self.assertNotIn('href="/mojprop-starter30-checkout/"', source)
        self.assertNotIn("Go to secure 30 TRX checkout", source)
        self.assertIn(
            'href="/moj-prop-intake/?format=html&amp;service=blueprint&amp;package=starter-30-trx"',
            source,
        )
        self.assertIn('href="/moj-prop/signals/"', source)
        self.assertIn("No TRX payment is available at present.", source)
        self.assertIn("The free request does not charge you", source)

    def test_home_maintains_original_layout_and_existing_store_research_routes(self):
        source = HOME.read_text(encoding="utf-8")
        for marker in (
            'class="mw-shell"',
            'class="mw-hero"',
            'class="mw-actions"',
            'href="/store/"',
            'href="/research/"',
            'id="starter30-featured"',
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, source)
        self.assertEqual(source.count('id="starter30-featured"'), 1)

    def test_moj_prop_removes_free_plan_and_explains_paid_virtual_progression(self):
        source = MOJ_PROP.read_text(encoding="utf-8")
        self.assertIn('href="/moj-prop/starter-30-trx/">Open the canonical Starter30 page', source)
        self.assertIn('href="/moj-prop/rules/">Read the published Starter30 rules', source)
        self.assertNotIn("Plan 1", source)
        self.assertNotIn("MOJ-PROP-01", source)
        self.assertIn("30 TRX INITIAL ENTRY", source)
        self.assertIn("$100,000 virtual", source)
        self.assertIn("Starter30 · 30 TRX plan", source)
        self.assertIn("14 SIMULATED LEVELS", source)
        self.assertIn("Starter30 payment:", source)
        self.assertNotIn("paid challenges, live accounts, KYC, automatic payment and profit guarantees are not active", source)

    def test_starter30_uses_current_payment_message(self):
        source = STARTER30.read_text(encoding="utf-8")
        self.assertIn("payment admission under independent verification", source)
        self.assertIn("Current status:</strong> Starter30 is the separate 60-day simulated product.", source)
        self.assertNotIn("Current status:</strong> payable simulated challenge", source)


if __name__ == "__main__":
    unittest.main()
