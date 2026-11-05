"""Fail-closed claims for future production admission; no VPS writes."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from factory_product_identity_gate_v1 import (  # noqa: E402
    SCHEMA, require_active_product, validate_claim,
)


class ProductIdentityGateTests(unittest.TestCase):
    def setUp(self):
        self.claim = {
            "schema": SCHEMA,
            "lane": "line41",
            "product_id": "farm_enterprise_economics",
            "generation": 1,
            "previous_handoff_sha256": None,
        }

    def check(self, **changes):
        claim = dict(self.claim, **changes)
        return validate_claim(json.dumps(claim), "line41", "farm_enterprise_economics")

    def test_first_product_admitted_with_exact_identity(self):
        self.assertEqual(self.check()["product_id"], "farm_enterprise_economics")

    def test_same_lane_cannot_admit_another_product(self):
        with self.assertRaisesRegex(ValueError, "DIFFERENT_ACTIVE_PRODUCT"):
            self.check(product_id="second_product")

    def test_other_lane_cannot_reuse_current_claim(self):
        with self.assertRaisesRegex(ValueError, "DIFFERENT_ACTIVE_PRODUCT"):
            self.check(lane="agri200")

    def test_next_generation_requires_previous_handoff_reference(self):
        with self.assertRaisesRegex(ValueError, "PREVIOUS_HANDOFF_REQUIRED"):
            self.check(generation=2)
        expected = "a" * 64
        self.assertEqual(self.check(generation=2, previous_handoff_sha256=expected)[
            "previous_handoff_sha256"], expected)

    def test_first_generation_rejects_fake_prior_handoff(self):
        with self.assertRaisesRegex(ValueError, "FIRST_HANDOFF_INVALID"):
            self.check(previous_handoff_sha256="a" * 64)

    def test_malformed_claims_fail_closed(self):
        for invalid in ("not json", "[]", "null"):
            with self.subTest(invalid=invalid):
                with self.assertRaises(ValueError):
                    validate_claim(invalid, "line41", "farm_enterprise_economics")

    def test_unexpected_fields_rejected(self):
        claim = dict(self.claim, release_authorized=True)
        with self.assertRaisesRegex(ValueError, "FIELDS_INVALID"):
            validate_claim(json.dumps(claim), "line41", "farm_enterprise_economics")

    def test_duplicate_json_keys_rejected(self):
        raw = json.dumps(self.claim)
        duplicate = raw.replace('"generation": 1', '"generation": 1, "generation": 2')
        with self.assertRaisesRegex(ValueError, "DUPLICATE_FIELD"):
            validate_claim(duplicate, "line41", "farm_enterprise_economics")

    def test_bool_and_zero_generations_rejected(self):
        for generation in (False, True, 0, -1):
            with self.subTest(generation=generation):
                with self.assertRaisesRegex(ValueError, "GENERATION_INVALID"):
                    self.check(generation=generation)

    def test_fake_product_identifiers_rejected(self):
        for product in ("../outside", " =FORMULA", "", "a" * 129):
            with self.subTest(product=product):
                with self.assertRaises(ValueError):
                    self.check(product_id=product)

    def test_unprotected_local_file_not_authoritative(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "anchor.json"
            path.write_text(json.dumps(self.claim), encoding="utf-8")
            with self.assertRaises(ValueError):
                require_active_product(path, "line41", "farm_enterprise_economics")

    def test_missing_anchor_is_never_idle(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(OSError):
                require_active_product(Path(tmp) / "missing.json", "line41", "farm_enterprise_economics")

    def test_read_only_cli_fails_closed_without_admin_anchor(self):
        with tempfile.TemporaryDirectory() as tmp:
            anchor = Path(tmp) / "anchor.json"
            anchor.write_text(json.dumps(self.claim), encoding="utf-8")
            before = anchor.read_bytes()
            result = subprocess.run([
                sys.executable,
                str(ROOT / "scripts" / "factory_product_identity_gate_v1.py"),
                "--anchor", str(anchor), "--lane", "line41",
                "--product-id", "farm_enterprise_economics",
            ], capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 3)
            self.assertIn("F01_PRODUCT_IDENTITY=HOLD", result.stderr)
            self.assertEqual(anchor.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
