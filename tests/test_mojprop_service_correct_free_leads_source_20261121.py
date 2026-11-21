"""Service-correct no-charge MOJ PROP lead routing; no fake post or invoice."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1] / "templates" / "moj-prop"
RULES = ROOT / "rules" / "index.html"
SIGNALS = ROOT / "signals" / "index.html"


class ServiceCorrectFunnelStaticSourceTests(unittest.TestCase):
    def test_simulated_starter30_goes_only_to_blueprint_written_terms(self):
        page = RULES.read_text(encoding="utf-8")
        self.assertEqual(page.count(
            '/moj-prop-intake/?format=html&amp;service=blueprint&amp;package=starter-30-trx'
        ), 1)
        self.assertIn("Ask for Starter30 written terms — free, no payment", page)
        self.assertIn('href="/moj-prop/#request">Request rulebook design</a>', page)
        self.assertNotIn('href="/mojprop-starter30-checkout/"', page)
        self.assertNotIn('method="post"', page.lower())

    def test_signal_quote_uses_signal_service_not_starter30_billing(self):
        page = SIGNALS.read_text(encoding="utf-8")
        self.assertEqual(page.count(
            '/moj-prop-intake/?format=html&amp;service=signals'
        ), 1)
        self.assertIn("Request a written educational signal proposal — no payment", page)
        self.assertIn('href="/moj-prop/?service=signals#request"', page)
        self.assertNotIn('href="/mojprop-starter30-checkout/"', page)
        self.assertNotIn('service=blueprint&amp;package=starter-30-trx', page)
        self.assertIn("No live trading calls", page)
        self.assertIn("No automatic", page)


if __name__ == "__main__":
    unittest.main()
