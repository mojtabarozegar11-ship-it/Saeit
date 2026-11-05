import json
from pathlib import Path
import importlib.util
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("qc_gate", ROOT / "scripts/factory_qc1000_rework_gate.py")
GATE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(GATE)


class QC1000ReworkGateTests(unittest.TestCase):
    def test_missing_clearance_is_hold(self):
        with tempfile.TemporaryDirectory() as directory:
            result = GATE.evaluate(Path(directory))
        self.assertEqual(result["status"], "HOLD")
        self.assertIn("SIGNED_CLEARANCE_MISSING", result["reasons"])
        self.assertEqual(result["schema"], "saeit.factory.qc1000-readiness.v2")
        self.assertEqual(len(result["rework_queue"]), 8)
        self.assertEqual(result["rework_queue"][0]["gate_id"], "G01")

    def test_incomplete_clearance_is_hold(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "quality-excellence/signed-clearances/farm_enterprise_economics"
            path.mkdir(parents=True)
            (path / "current.json").write_text(json.dumps({
                "verified_grade_total": 1000,
                "eligible": True,
                "valid_signed_roles": ["domain_specialist"],
                "publication_executed": False,
                "payment_activated": False,
            }))
            result = GATE.evaluate(Path(directory))
        self.assertEqual(result["status"], "HOLD")
        self.assertIn("INDEPENDENT_SIGNATURES_INCOMPLETE", result["reasons"])

    def test_forged_complete_role_claim_never_passes_without_signatures(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "quality-excellence/signed-clearances/farm_enterprise_economics"
            path.mkdir(parents=True)
            (path / "current.json").write_text(json.dumps({
                "schema": "saeit.factory.signed-quality-clearance.v1",
                "verified_grade_total": 1000,
                "eligible": True,
                "valid_signed_roles": ["domain_specialist", "independent_quality_auditor", "rights_reviewer"],
                "owner_authorization_kind": "direct_owner",
                "publication_executed": False,
                "payment_activated": False,
            }))
            result = GATE.evaluate(Path(directory))
        self.assertEqual(result["status"], "HOLD")
        self.assertIn("INDEPENDENT_SIGNATURES_NOT_AUTHENTICATED", result["reasons"])

    def test_malformed_clearance_does_not_crash(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "quality-excellence/signed-clearances/farm_enterprise_economics"
            path.mkdir(parents=True)
            (path / "current.json").write_text(json.dumps({"valid_signed_roles": [["domain_specialist"]]}))
            result = GATE.evaluate(Path(directory))
        self.assertEqual(result["status"], "HOLD")
        self.assertIn("INDEPENDENT_SIGNATURES_INCOMPLETE", result["reasons"])

    def test_authentic_verifier_is_required_even_when_roles_are_complete(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "quality-excellence/signed-clearances/farm_enterprise_economics"
            path.mkdir(parents=True)
            (path / "current.json").write_text(json.dumps({
                "schema": "saeit.factory.signed-quality-clearance.v1",
                "verified_grade_total": 1000,
                "eligible": True,
                "valid_signed_roles": ["domain_specialist", "independent_quality_auditor", "rights_reviewer"],
                "owner_authorization_kind": "direct_owner",
                "publication_executed": False,
                "payment_activated": False,
            }))
            with patch.object(GATE, "_authenticated_independent_signatures", return_value=True) as verifier:
                result = GATE.evaluate(Path(directory))
        self.assertEqual(result["status"], "PASS")
        verifier.assert_called_once()


if __name__ == "__main__":
    unittest.main()
