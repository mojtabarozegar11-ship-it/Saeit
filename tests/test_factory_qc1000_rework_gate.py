import json
from pathlib import Path
import importlib.util
import tempfile
import unittest

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


if __name__ == "__main__":
    unittest.main()
