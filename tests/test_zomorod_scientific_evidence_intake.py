"""Validate offline scientific evidence-gate invariants in the main Django CI."""
import unittest

from scripts.zomorod_scientific_evidence_gate_20261024 import audit_records, self_test


class ScientificEvidenceGateTests(unittest.TestCase):
    def test_existing_synthetic_safety_suite(self):
        self_test()

    def test_malformed_nested_fields_fail_closed(self):
        sample = {
            "project_id": "ZM-RP-2026-0001",
            "stage": ["invalid", "list"],
            "evidence": [{"kind": ["invalid"], "url": "https://example.org"}],
        }
        result = audit_records([sample])
        self.assertEqual(result["candidate_count"], 0)
        self.assertEqual(result["rejected_count"], 1)
        self.assertIn("stage:invalid", result["rejected"][0]["reasons"])
        self.assertIn("evidence[0]:kind_invalid", result["rejected"][0]["reasons"])
        self.assertFalse(result["automatic_publication_allowed"])


if __name__ == "__main__":
    unittest.main()
