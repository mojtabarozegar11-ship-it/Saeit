"""Read-only repository source check; never attempts a live HTTP request."""
import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from revenue_cycle2_source_audit import MUST_HAVE, audit


class SourceAuditTests(unittest.TestCase):
    def test_ten_source_backed_offers(self):
        data = audit()
        self.assertEqual(data["offer_source_paths_checked"], 10)
        self.assertEqual(data["missing_source_contracts"], [])
        self.assertTrue(data["source_contract_ok"])

    def test_three_existing_service_templates_only(self):
        data = audit()
        self.assertEqual(data["service_cta_templates_checked"], 3)
        self.assertEqual(len(MUST_HAVE), 3)

    def test_source_not_live_proof(self):
        data = audit()
        self.assertFalse(data["live_render_verified"])
        self.assertFalse(data["revenue_verified"])
        self.assertFalse(data["delivery_verified"])


if __name__ == "__main__":
    unittest.main()
