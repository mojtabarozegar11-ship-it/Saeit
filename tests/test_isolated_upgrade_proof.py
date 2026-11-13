import hashlib
import json
import os
from pathlib import Path
import tempfile
import time
import unittest

from core.isolated_upgrade_proof import inspect_isolated_proof


def valid_dossier():
    paths = (
        "scripts/factory_research_triage.py",
        "scripts/factory_specialist_pilots.py",
        "scripts/factory_first_product_pilot.py",
        "scripts/factory_public_library_adapter.py",
    )
    inventory = [
        {"path": path, "source_sha256": hashlib.sha256(path.encode()).hexdigest(),
         "source_bytes": len(path)}
        for path in paths
    ]
    return {
        "schema": "saeit.factory.code-self-upgrade.v1",
        "factory_python_files_scanned": len(paths),
        "module_sha256_inventory": inventory,
        "candidate_count": 0,
        "private_verified_code_edits": 0,
        "candidates_with_measured_improvement": 0,
        "preexisting_verified_repairs": len(paths),
        "validated_repair_rule_coverage": len(paths),
        "modules_without_proven_repair": 0,
        "unresolved_known_security_regressions": 0,
        "production_code_promotions": 0,
        "whole_code_autonomous_evolution_complete": False,
        "candidates": [],
        "already_protected_source_modules": [
            {"path": item["path"], "source_sha256": item["source_sha256"],
             "negative_case_blocked": True, "new_code_edit_performed": False}
            for item in inventory
        ],
    }

class IsolatedProofTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "evolution-proof.json"
        self._write(valid_dossier())

    def _write(self, data):
        self.path.write_text(json.dumps(data), encoding="utf-8")
        self.path.chmod(0o600)

    def _add_candidate(self):
        proof = valid_dossier()
        prior = proof["already_protected_source_modules"].pop()
        candidate_data = b"# isolated reviewed repair candidate\n"
        slot = self.path.parent / "candidate-1"
        slot.mkdir()
        (slot / prior["path"].rsplit("/", 1)[-1]).write_bytes(candidate_data)
        proof["candidate_count"] = 1
        proof["private_verified_code_edits"] = 1
        proof["preexisting_verified_repairs"] = 3
        proof["candidates_with_measured_improvement"] = 1
        proof["candidates"] = [{
            "path": prior["path"],
            "baseline_sha256": prior["source_sha256"],
            "candidate_sha256": hashlib.sha256(candidate_data).hexdigest(),
            "changed_source": True,
            "private_only": True,
            "negative_case_reproduced": True,
            "security_regression_prevented": True,
            "measured_quality_improvement": True,
            "baseline": {"blocked": False, "escaped": True},
            "candidate": {"blocked": True, "escaped": False},
        }]
        self._write(proof)
        return proof, slot / prior["path"].rsplit("/", 1)[-1]

    def test_fresh_consistent_private_dossier_is_inspectable_without_mutation(self):
        before = self.path.read_bytes()
        result = inspect_isolated_proof(self.path)
        self.assertEqual(result["candidate_count"], 0)
        self.assertEqual(result["preexisting_verified_repairs"], 4)
        self.assertEqual(result["production_code_promotions"], 0)
        self.assertEqual(self.path.read_bytes(), before)

    def test_real_candidate_artifact_matches_proof_sha256(self):
        self._add_candidate()
        result = inspect_isolated_proof(self.path)
        self.assertEqual(result["candidate_artifacts_hash_verified"], 1)
        self.assertEqual(result["source_manifest_entries_checked"], 4)

    def test_rejects_mutated_candidate_file(self):
        _, candidate = self._add_candidate()
        candidate.write_bytes(b"tampered candidate")
        with self.assertRaisesRegex(ValueError, "CANDIDATE_HASH_MISMATCH"):
            inspect_isolated_proof(self.path)

    def test_rejects_missing_candidate_file(self):
        _, candidate = self._add_candidate()
        candidate.unlink()
        with self.assertRaisesRegex(ValueError, "CANDIDATE_MISSING"):
            inspect_isolated_proof(self.path)

    def test_rejects_fabricated_improvement_observation(self):
        proof, _ = self._add_candidate()
        proof["candidates"][0]["security_regression_prevented"] = False
        self._write(proof)
        with self.assertRaisesRegex(ValueError, "CANDIDATE_CLAIMS_INVALID"):
            inspect_isolated_proof(self.path)

    def test_rejects_inconsistent_source_manifest(self):
        proof = valid_dossier()
        proof["already_protected_source_modules"][0]["source_sha256"] = "b" * 64
        self._write(proof)
        with self.assertRaisesRegex(ValueError, "EXISTING_REPAIR_INVALID"):
            inspect_isolated_proof(self.path)

    def test_rejects_symlinked_ancestor(self):
        linked_parent = self.path.parent / "alias-parent"
        linked_parent.symlink_to(self.path.parent, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "UNSAFE"):
            inspect_isolated_proof(linked_parent / self.path.name)

    def test_rejects_publicly_readable_dossier(self):
        self.path.chmod(0o644)
        with self.assertRaisesRegex(ValueError, "PERMISSIONS_UNSAFE"):
            inspect_isolated_proof(self.path)

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
