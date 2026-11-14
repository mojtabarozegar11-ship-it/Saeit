"""Commercial gates remain independently unverified after source/CI success."""
import sys
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from revenue_cycle2_gate import GATES, explain_ratio, requirements
from mojtaba_revenue_portfolio import OFFERS


class GateTests(unittest.TestCase):
    def test_every_offer_has_seven_unknown_gates(self):
        for code in OFFERS:
            with self.subTest(code=code):
                result = requirements(code)
                self.assertEqual(result["gate_count"], 7)
                self.assertEqual({x["status"] for x in result["gates"]}, {"UNKNOWN"})
                self.assertFalse(result["commercial_ready"])
                self.assertIsNone(result["paid_orders"])

    def test_payment_and_delivery_proofs_are_separate(self):
        names = [name for name, _ in GATES]
        self.assertIn("receipt", names)
        self.assertIn("delivery", names)
        self.assertNotEqual(names.index("receipt"), names.index("delivery"))

    def test_invalid_offers_blocked(self):
        for code in ("unknown", "", None, 1):
            with self.subTest(code=code), self.assertRaises(ValueError):
                requirements(code)

    def test_source_progress_does_not_verify_sales(self):
        r = explain_ratio(2, 7)
        self.assertAlmostEqual(r["percent"], 28.57)
        self.assertFalse(r["cash_receipt_proof"])

    def test_invalid_ratio_rejected(self):
        for a, b in ((True, 7), (2, 0), (8, 7), (-1, 7), (2, False)):
            with self.subTest(a=a, b=b), self.assertRaises(ValueError):
                explain_ratio(a, b)


if __name__ == "__main__":
    unittest.main()
