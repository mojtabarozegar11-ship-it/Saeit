"""Single bot public portal can send distinct free signals leads to the real CRM."""
from pathlib import Path
import unittest
PAGE = Path(__file__).resolve().parents[1] / "templates" / "core" / "mojtaba_bot_portal.html"


class MojtabaCentralBotSignalEnquiryTests(unittest.TestCase):
    def test_signals_are_discoverable_without_purchase_claim(self):
        text = PAGE.read_text(encoding="utf-8")
        self.assertIn('href="/moj-prop/signals/">Educational signals</a>', text)
        self.assertEqual(text.count(
            'href="/moj-prop-intake/?format=html&amp;service=signals"'
        ), 1)
        self.assertIn("Request a written educational signal proposal — no payment", text)
        self.assertIn("not a trading order, signal subscription, paid invoice or confirmed delivery", text.lower())
        self.assertNotIn('href="/mojprop-starter30-checkout/"', text)

    def test_starter30_remains_distinct_simulated_blueprint_offer(self):
        text = PAGE.read_text(encoding="utf-8")
        self.assertEqual(text.count(
            'href="/moj-prop-intake/?format=html&amp;service=blueprint&amp;package=starter-30-trx"'
        ), 1)
        self.assertIn("Starter30 is a simulated trading challenge", text)
        self.assertIn('href="/moj-prop/starter-30-trx/"', text)
        self.assertIn('/privacy/', text)


if __name__ == "__main__":
    unittest.main()
