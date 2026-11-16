"""C120: no reported paid SKU readiness when real TRON merchant canary is false.

No site access, database access, checkout, invoice or network calls.
"""
import ast
from pathlib import Path
import unittest

WORKFLOW = Path(__file__).resolve().parents[1] / ".github/workflows/mpw-live-three-sku-rights-gate-20261026.yml"


class CanaryReportIntegrityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = WORKFLOW.read_text(encoding="utf-8")

    def test_live_sku_sellability_requires_literal_merchant_true(self):
        sale = self.source.split("is_sellable=(eligible and rights and file_ready", 1)[1].split(")", 1)[0]
        self.assertIn('getattr(settings,"MPW_WALLETLESS_TRX_MERCHANT_CANARY_PASSED",False) is True', sale)
        self.assertIn('getattr(settings,"MPW_WALLETLESS_TRX_PUBLIC_ENABLED",False) is True', sale)
        self.assertIn("release_authorized", sale)

    def test_canary_block_remains_independent_of_sku_file_presence(self):
        from scripts.mpw_three_sku_preflight_20261029 import classify
        import json
        flags = {
            "merchant_canary": False,
            "rights_gate_installed": True,
            "public_enabled": True,
            "release_authorized": True,
        }
        data = [
            {"id": sku, "exists": True, "active": True, "eligible": True,
             "private_file_ready": True, "stored_rights": True,
             "explicit_rights": True, "rights_hash_reference_matches_asset": True,
             "existing_catalog_hash_matches_asset": ["sha256"],
             "existing_approval_flags": {"publication_approved": True}}
            for sku in (72, 225, 879)
        ]
        lines = ["MPW_PUBLIC_TRX_FLAGS=" + json.dumps(flags)]
        lines.extend("MPW_PUBLIC_SKU_RIGHTS=" + json.dumps(p) for p in data)
        result = classify("\n".join(lines))
        self.assertEqual(result["preflight"], "blocked")
        self.assertIn("MERCHANT_CANARY_NOT_VERIFIED", result["global_blocks"])
        self.assertEqual(set(result["products"]), {"72", "225", "879"})

    def test_diagnostics_do_not_modify_canary_or_create_payments(self):
        self.assertNotIn("MPW_WALLETLESS_TRX_MERCHANT_CANARY_PASSED=True", self.source)
        self.assertNotIn("MPW_WALLETLESS_TRX_MERCHANT_CANARY_PASSED = True", self.source)
        self.assertIn("CHECK_READONLY=TRUE; ORDERS_MODIFIED=0", self.source)


if __name__ == "__main__":
    unittest.main()
