import json
import os
from pathlib import Path
import tempfile
import time
import unittest

from core.isolated_upgrade_proof import inspect_isolated_proof


def valid_dossier():
    return {
        "schema": "saeit.factory.code-self-upgrade.v1",
        "candidate_count": 0,
        "candidates_with_measured_improvement": 0,
        "preexisting_verified_repairs": 4,
        "validated_repair_rule_coverage": 4,
        "unresolved_known_security_regressions": 0,
        "production_code_promotions": 0,
        "whole_code_autonomous_evolution_complete": False,
        "candidates": [],
        "already_protected_source_modules": [{"path": str(i)} for i in range(4)],
    }


class IsolatedProofTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "evolution-proof.json"
        self._write(valid_dossier())

    def _write(self, data):
        self.path.write_text(json.dumps(data), encoding="utf-8")

    def test_fresh_consistent_private_dossier_is_inspectable_without_mutation(self):
        before = self.path.read_bytes()
        result = inspect_isolated_proof(self.path)
        self.assertEqual(result["candidate_count"], 0)
        self.assertEqual(result["preexisting_verified_repairs"], 4)
        self.assertEqual(result["production_code_promotions"], 0)
        self.assertEqual(self.path.read_bytes(), before)

    def test_rejects_stale_dossier(self):
        expired = time.time() - 49 * 3600
        os.utime(self.path, (expired, expired))
        with self.assertRaisesRegex(ValueError, "STALE"):
            inspect_isolated_proof(self.path)

    def test_rejects_symlink(self):
        linked = self.path.parent / "linked.json"
        linked.symlink_to(self.path)
        with self.assertRaisesRegex(ValueError, "UNSAFE"):
            inspect_isolated_proof(linked)

    def test_rejects_inconsistent_repair_claims(self):
        proof = valid_dossier()
        proof["candidate_count"] = 2
        self._write(proof)
        with self.assertRaisesRegex(ValueError, "INCONSISTENT"):
            inspect_isolated_proof(self.path)

    def test_rejects_production_promotion_claim(self):
        proof = valid_dossier()
        proof["production_code_promotions"] = 1
        self._write(proof)
        with self.assertRaisesRegex(ValueError, "INCONSISTENT"):
            inspect_isolated_proof(self.path)

    def test_rejects_invalid_schema_and_json(self):
        proof = valid_dossier()
        proof["schema"] = "untrusted"
        self._write(proof)
        with self.assertRaisesRegex(ValueError, "SCHEMA"):
            inspect_isolated_proof(self.path)
        self.path.write_text("{", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "INVALID_JSON"):
            inspect_isolated_proof(self.path)

    def test_rejects_booleans_as_numeric_counters(self):
        proof = valid_dossier()
        proof["candidate_count"] = True
        self._write(proof)
        with self.assertRaisesRegex(ValueError, "COUNTER"):
            inspect_isolated_proof(self.path)


if __name__ == "__main__":
    unittest.main()
