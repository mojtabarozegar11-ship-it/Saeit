"""Measured factory code self-edit: security improvements, private scope, no fake generation."""
import importlib.util
import json
from pathlib import Path
import shutil
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("saeit_self_upgrader",
    str(ROOT/"scripts/factory_code_self_upgrade.py"))
upgrader = importlib.util.module_from_spec(spec)
spec.loader.exec_module(upgrader)


class CodeSelfUpgradeTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root=Path(temp.name)
        self.src=self.root/"checkout"
        (self.src/"scripts").mkdir(parents=True)
        self.output=self.root/"private-candidates"
        for name, *_ in upgrader.SAFE_FIXES:
            p=self.src/name
            p.parent.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(str(ROOT/name), str(p))

    def test_edits_source_with_measured_security_regression_improvement(self):
        state=upgrader.generate(self.src,self.output)
        self.assertEqual(state["candidate_count"],2)
        self.assertEqual(state["preexisting_verified_repairs"],2)
        self.assertEqual(state["validated_repair_rule_coverage"],4)
        self.assertEqual(state["factory_python_files_scanned"],4)
        self.assertEqual(state["private_verified_code_edits"],2)
        self.assertEqual(state["candidates_with_measured_improvement"],2)
        self.assertFalse(state["whole_code_autonomous_evolution_complete"])
        self.assertEqual(state["production_code_promotions"],0)
        self.assertEqual(state["generation_number_proven_in_production"],0)
        for item in state["candidates"]:
            self.assertTrue(item["changed_source"])
            self.assertTrue(item["negative_case_reproduced"])
            self.assertTrue(item["security_regression_prevented"])
            self.assertEqual(item["baseline"],{"blocked":False,"escaped":True})
            self.assertEqual(item["candidate"],{"blocked":True,"escaped":False})
            original=(self.src/item["path"]).read_bytes()
            self.assertEqual(upgrader.digest_bytes(original),item["baseline_sha256"])
        self.assertEqual(json.loads((self.output/"evolution-proof.json").read_text())
                         ["candidate_count"],2)

    def test_vps_installer_uses_real_checked_source_argument(self):
        installer=(ROOT/"deploy/install_factory_code_self_upgrade.sh").read_text()
        self.assertIn('source="$1"',installer)
        self.assertNotIn('source="1"',installer)
        self.assertIn('FACTORY_CODE_SELF_EDIT_PRIVATE_INSTALL=PASS',installer)

    def test_existing_patched_source_is_not_double_counted(self):
        state=upgrader.generate(self.src,self.output)
        self.assertEqual(state["preexisting_verified_repairs"],2)
        self.assertTrue(all(not rec["new_code_edit_performed"] for rec in state["already_protected_source_modules"]))
        self.assertEqual(set(x["path"] for x in state["already_protected_source_modules"]),
                         {"scripts/factory_research_triage.py",
                          "scripts/factory_specialist_pilots.py"})

    def test_missing_source_fails_closed(self):
        (self.src/"scripts/factory_research_triage.py").unlink()
        with self.assertRaises(RuntimeError):
            upgrader.generate(self.src,self.output)

    def test_output_must_be_outside_checkout(self):
        with self.assertRaises(RuntimeError):
            upgrader.generate(self.src,self.src/"generated")

    def test_idempotent_candidate_contents_with_stable_sha(self):
        first=upgrader.generate(self.src,self.output)
        second=upgrader.generate(self.src,self.output)
        self.assertEqual([a["candidate_sha256"] for a in first["candidates"]],
                         [a["candidate_sha256"] for a in second["candidates"]])

    def test_candidate_is_real_modified_code_and_original_unchanged(self):
        original=(self.src/"scripts/factory_research_triage.py")
        before=original.read_bytes()
        state=upgrader.generate(self.src,self.output)
        self.assertEqual(original.read_bytes(),before)
        item=next(x for x in state["candidates"] if x["path"].endswith("factory_first_product_pilot.py"))
        original=(self.src/item["path"])
        before=original.read_bytes()
        candidate=(self.output/"candidate-1"/"factory_first_product_pilot.py")
        self.assertTrue(candidate.exists())
        self.assertNotEqual(upgrader.digest_bytes(candidate.read_bytes()),item["baseline_sha256"])
        self.assertIn("SELF_UPGRADE_BLOCKED_SYMLINK_PARENT",candidate.read_text())


if __name__ == "__main__":
    unittest.main()
