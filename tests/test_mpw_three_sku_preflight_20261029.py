"""Offline regression for the paid SKU preflight classifier. No database or network."""
import importlib.util
import json
from pathlib import Path
import textwrap
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/mpw_three_sku_preflight_20261029.py"
SPEC = importlib.util.spec_from_file_location("mpw_preflight", SCRIPT)
POLICY = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(POLICY)


def fixture():
    flags = {
        "rights_gate_installed": True, "merchant_canary": True,
        "commercial_db_ready": True, "merchant_receiver_ready": True,
        "public_enabled": True, "release_authorized": True,
        "guest_checkout_without_email_verified": True,
        "owned_invoice_receipt_issued": True,
        "receipt_paid_download_recovery_verified": True,
    }
    products = {
        sku: {
            "id": sku, "exists": True, "active": True, "eligible": True,
            "public_product_allowed": True,
            "private_file_ready": True, "stored_rights": True,
            "explicit_rights": True,
            "canonical_catalog_sha_matches_asset": True,
            "rights_hash_reference_matches_asset": True,
            "rights_document_hash_well_formed": True,
            "existing_catalog_hash_matches_asset": ["sha256"],
            "existing_approval_flags": {"publication_approved": True},
            "product_internal_gates": {key: True for key, _ in POLICY.INTERNAL_GATES},
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
        self.assertIs(result["commercial_sale_proven"], False)

    def test_each_global_blocker_is_fail_closed(self):
        for key in ("rights_gate_installed", "merchant_canary",
                    "commercial_db_ready", "merchant_receiver_ready",
                    "public_enabled", "release_authorized",
                    "guest_checkout_without_email_verified",
                    "owned_invoice_receipt_issued",
                    "receipt_paid_download_recovery_verified"):
            with self.subTest(key=key):
                f, p = fixture()
                f[key] = False
                self.assertEqual(POLICY.classify(render(f, p))["preflight"], "blocked")

    def test_missing_payment_backend_or_receiver_evidence_cannot_pass(self):
        for key, code in (("commercial_db_ready", "COMMERCIAL_DB_NOT_READY"),
                          ("merchant_receiver_ready", "MERCHANT_TRX_RECEIVER_NOT_READY")):
            with self.subTest(key=key):
                flags, products = fixture()
                flags.pop(key)
                result = POLICY.classify(render(flags, products))
                self.assertIn(code, result["global_blocks"])
                self.assertEqual(result["preflight"], "blocked")

    def test_email_is_optional_but_receipt_delivery_proofs_are_not(self):
        flags, products = fixture()
        flags["buyer_email_before_invoice"] = False
        flags["email_recovery_verified"] = False
        self.assertEqual(POLICY.classify(render(flags, products))["preflight"], "passed")
        flags.pop("owned_invoice_receipt_issued")
        flags.pop("receipt_paid_download_recovery_verified")
        result = POLICY.classify(render(flags, products))
        self.assertEqual(result["preflight"], "blocked")
        self.assertIn("PRIVATE_RECEIPT_ISSUANCE_NOT_VERIFIED", result["global_blocks"])
        self.assertIn("PAID_RECEIPT_RECOVERY_NOT_VERIFIED", result["global_blocks"])
        self.assertIs(result["commercial_sale_proven"], False)

    def test_each_product_blocker_is_fail_closed(self):
        keys = (
            "exists", "active", "public_product_allowed", "eligible", "private_file_ready",
            "stored_rights", "explicit_rights", "canonical_catalog_sha_matches_asset",
            "rights_hash_reference_matches_asset", "rights_document_hash_well_formed",
        )
        for sku in POLICY.SKU_IDS:
            for key in keys:
                with self.subTest(sku=sku, key=key):
                    f, p = fixture()
                    p[sku][key] = False
                    r = POLICY.classify(render(f, p))
                    self.assertEqual(r["preflight"], "blocked")
                    self.assertEqual(r["products"][str(sku)]["preflight"], "blocked")

    def test_missing_or_false_public_allowlist_has_exact_blocker(self):
        for sku in POLICY.SKU_IDS:
            for value in (False, None, 1, "true"):
                with self.subTest(sku=sku, value=value):
                    flags, products = fixture()
                    if value is None:
                        products[sku].pop("public_product_allowed")
                    else:
                        products[sku]["public_product_allowed"] = value
                    result = POLICY.classify(render(flags, products))
                    self.assertEqual(result["preflight"], "blocked")
                    self.assertIn("PRODUCT_NOT_IN_PUBLIC_TRX_ALLOWLIST",
                                  result["products"][str(sku)]["blocks"])
                    self.assertEqual(result["products"][str(next(k for k in POLICY.SKU_IDS if k != sku))]["preflight"], "passed")

    def test_publication_and_catalog_sha_are_mandatory(self):
        f, p = fixture()
        p[72]["existing_approval_flags"]["publication_approved"] = False
        p[225]["existing_catalog_hash_matches_asset"] = []
        r = POLICY.classify(render(f, p))
        self.assertIn("PUBLICATION_APPROVAL_MISSING", r["products"]["72"]["blocks"])
        self.assertIn("CATALOG_FILE_HASH_MISMATCH", r["products"]["225"]["blocks"])

    def test_each_product_internal_lock_has_a_specific_error_code(self):
        for key, code in POLICY.INTERNAL_GATES:
            with self.subTest(key=key):
                flags, products = fixture()
                products[879]["product_internal_gates"][key] = False
                result = POLICY.classify(render(flags, products))
                self.assertEqual(result["preflight"], "blocked")
                self.assertIn(code, result["products"]["879"]["blocks"])
                self.assertEqual(result["products"]["72"]["preflight"], "passed")

    def test_missing_internal_gate_evidence_cannot_pass(self):
        flags, products = fixture()
        products[72].pop("product_internal_gates")
        result = POLICY.classify(render(flags, products))
        self.assertIn("PRODUCT_INTERNAL_GATE_EVIDENCE_MISSING", result["products"]["72"]["blocks"])

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
        self.assertIn("VPS_SSH_HOST_KEY_MISMATCH_ON_PORT_", workflow)
        self.assertIn("VPS_SSH_UNREACHABLE_ON_PINNED_PORTS_22_423_1396", workflow)
        self.assertIn("Port $vps_port", workflow)
        self.assertNotIn("if blocked:sys.exit(3)", workflow)
        self.assertNotIn("workflow_dispatch(operation=apply)", workflow)

    def test_read_only_workflow_internal_gate_collector_is_valid_python(self):
        path = SCRIPT.parents[1] / ".github/workflows/mpw-live-three-sku-rights-gate-20261026.yml"
        workflow = path.read_text("utf8")
        step = workflow.split("- name: Check all three publicly listed products without changing checkout or customer data", 1)[1]
        body = step.split("<<'PY'\n", 1)[1].split("\n          PY", 1)[0]
        compile(textwrap.dedent(body), str(path), "exec")
        for key, _ in POLICY.INTERNAL_GATES:
            self.assertIn('"' + key + '":', body)
        self.assertIn('"product_internal_gates":internal_gates', body)
        self.assertIn('"public_product_allowed":public_allowed', body)
        self.assertIn('public_allowed = sku in configured_public_ids', body)
        self.assertIn('and public_allowed and release_authorized', body)
        self.assertIn('and commercial_db_ready and merchant_receiver_ready', body)
        self.assertIn('"commercial_db_ready":commercial_db_ready', body)
        self.assertIn('"merchant_receiver_ready":merchant_receiver_ready', body)
        self.assertIn('"canonical_catalog_sha_matches_asset":', body)
        self.assertIn('"rights_document_hash_well_formed":', body)
        self.assertIn('"rights_asset_sha256"', body)
        self.assertIn('"rights_document_sha256"', body)
        self.assertIn('and canonical_sha_ok and rights_asset_sha_ok and rights_document_sha_ok', body)


if __name__ == "__main__":
    unittest.main()
