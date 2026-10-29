"""Offline regression for the paid SKU preflight classifier. No database or network."""
import importlib.util
import json
from pathlib import Path
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/mpw_three_sku_preflight_20261029.py"
SPEC = importlib.util.spec_from_file_location("mpw_preflight", SCRIPT)
POLICY = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(POLICY)


def fixture():
    flags = {
        "rights_gate_installed": True, "merchant_canary": True,
        "public_enabled": True, "release_authorized": True,
    }
    products = {
        sku: {
            "id": sku, "exists": True, "active": True, "eligible": True,
            "private_file_ready": True, "stored_rights": True,
            "explicit_rights": True,
            "rights_hash_reference_matches_asset": True,
            "existing_catalog_hash_matches_asset": ["sha256"],
            "existing_approval_flags": {"publication_approved": True},
        } for sku in POLICY.SKU_IDS
    }
    return flags, products


def render(flags, products):
    lines = ["MPW_PUBLIC_TRX_FLAGS=" + json.dumps(flags)]
    lines += ["MPW_PUBLIC_SKU_RIGHTS=" + json.dumps(p) for p in products.values()]
    return "\n".join(lines)


class PreflightContract(unittest.TestCase):
    def test_complete_synthetic_preflight_does_not_claim_a_purchase(self):
        f, p = fixture()
        result = POLICY.classify(render(f, p))
        self.assertEqual(result["preflight"], "passed")
        self.assertEqual(result["paid_receipt"], "not_examined")
        self.assertEqual(result["authenticated_download_e2e"], "not_examined")
        self.assertEqual(result["independent_legal_clearance"],
                         "not_established_by_metadata")

    def test_each_global_blocker_is_fail_closed(self):
        for key in ("rights_gate_installed", "merchant_canary",
                    "public_enabled", "release_authorized"):
            with self.subTest(key=key):
                f, p = fixture()
                f[key] = False
                self.assertEqual(POLICY.classify(render(f, p))["preflight"], "blocked")

    def test_each_product_blocker_is_fail_closed(self):
        keys = (
            "exists", "active", "eligible", "private_file_ready",
            "stored_rights", "explicit_rights", "rights_hash_reference_matches_asset",
        )
        for sku in POLICY.SKU_IDS:
            for key in keys:
                with self.subTest(sku=sku, key=key):
                    f, p = fixture()
                    p[sku][key] = False
                    r = POLICY.classify(render(f, p))
                    self.assertEqual(r["preflight"], "blocked")
                    self.assertEqual(r["products"][str(sku)]["preflight"], "blocked")

    def test_publication_and_catalog_sha_are_mandatory(self):
        f, p = fixture()
        p[72]["existing_approval_flags"]["publication_approved"] = False
        p[225]["existing_catalog_hash_matches_asset"] = []
        r = POLICY.classify(render(f, p))
        self.assertIn("PUBLICATION_APPROVAL_MISSING", r["products"]["72"]["blocks"])
        self.assertIn("CATALOG_FILE_HASH_MISMATCH", r["products"]["225"]["blocks"])

    def test_missing_duplicate_and_unexpected_products_fail_closed(self):
        f, p = fixture()
        p.pop(879)
        with self.assertRaisesRegex(ValueError, "MISSING_OR_DUPLICATE"):
            POLICY.classify(render(f, p))
        f, p = fixture()
        data = render(f, p)
        duplicate = "MPW_PUBLIC_SKU_RIGHTS=" + json.dumps(p[72])
        with self.assertRaisesRegex(ValueError, "DUPLICATE_OR_UNEXPECTED"):
            POLICY.classify(data + "\n" + duplicate)
        f, p = fixture()
        p[72]["id"] = 999
        with self.assertRaisesRegex(ValueError, "DUPLICATE_OR_UNEXPECTED"):
            POLICY.classify(render(f, p))

    def test_truthy_values_are_not_approvals(self):
        f, p = fixture()
        f["merchant_canary"] = "true"
        p[72]["stored_rights"] = 1
        p[225]["rights_hash_reference_matches_asset"] = "yes"
        self.assertEqual(POLICY.classify(render(f, p))["preflight"], "blocked")

    def test_workflow_remains_read_only_and_asserts_synthetic_checks(self):
        path = SCRIPT.parents[1] / ".github/workflows/mpw-live-three-sku-rights-gate-20261026.yml"
        workflow = path.read_text("utf8")
        self.assertIn("github.event_name != 'pull_request'", workflow)
        self.assertIn("scripts/mpw_three_sku_preflight_20261029.py", workflow)
        self.assertIn("SYNTHETIC_EXPIRED_INVOICE_ASSERTION_FAILED", workflow)
        self.assertIn("LOGIN_RETURN_CONTRACT_FAILED", workflow)
        self.assertIn("MPW_LEGACY_PRECHECK_PASS=", workflow)
        self.assertNotIn("if blocked:sys.exit(3)", workflow)
        self.assertNotIn("workflow_dispatch(operation=apply)", workflow)


if __name__ == "__main__":
    unittest.main()
