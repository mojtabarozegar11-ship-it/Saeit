"""Three real executable review packets with synthetic allowlisted metadata."""
import json
import sys
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from revenue_cycle2_quote import generate


class ExamplePackets(unittest.TestCase):
    def test_three_examples_execute(self):
        expected = ("website_diagnosis", "farm_economics", "digital_publication")
        for code in expected:
            with self.subTest(code=code):
                path = ROOT / "docs/revenue-p0/cycle2/examples" / (code + ".synthetic.json")
                input_data = json.loads(path.read_text(encoding="utf-8"))
                result = generate(input_data)
                self.assertEqual(result["offer_id"], code)
                self.assertTrue(result["synthetic_example"])
                self.assertFalse(result["quote_sent"])
                self.assertFalse(result["payment_verified"])
                self.assertIsNone(result["collected_revenue"])

    def test_unreleased_product_is_blocked(self):
        path = ROOT / "docs/revenue-p0/cycle2/examples/digital_publication.synthetic.json"
        result = generate(json.loads(path.read_text(encoding="utf-8")))
        self.assertIn("PRODUCT_NOT_LIVE_OR_PROVEN", result["review_blockers"])

    def test_indicative_prices_are_nonbinding(self):
        path = ROOT / "docs/revenue-p0/cycle2/examples/website_diagnosis.synthetic.json"
        result = generate(json.loads(path.read_text(encoding="utf-8")))
        self.assertEqual(result["indicative_non_binding_range"]["maximum"], 49)
        self.assertFalse(result["price_approved"])


if __name__ == "__main__":
    unittest.main()
