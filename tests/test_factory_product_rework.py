"""Real recipe-failure diagnosis, protected artifacts, and repair validation."""
import importlib.util
import json
from pathlib import Path
import shutil
import sqlite3
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


def load(module, filename):
    spec = importlib.util.spec_from_file_location(module, str(ROOT / "scripts" / filename))
    obj = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(obj)
    return obj


repair = load("factory_rework_test", "factory_product_rework.py")
cycle = load("factory_rework_cycle_test", "factory_vps_product_cycle.py")
maker = load("factory_rework_maker_test", "factory_product_maker.py")


class FactoryDefectLoopTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name)
        self.recipes = self.home / "recipes"
        self.output = self.home / "private"
        self.db = self.home / "factory.db"
        for recipe in maker.RECIPES:
            shutil.copytree(ROOT / "product_recipes" / recipe, self.recipes / recipe)
        with sqlite3.connect(str(self.db)) as conn:
            conn.executescript("""
                CREATE TABLE core_product(id INTEGER PRIMARY KEY, title TEXT,
                    product_type TEXT, metadata TEXT, active INTEGER, price TEXT,
                    owner_id INTEGER, knowledge_article_id INTEGER, factory_managed INTEGER);
                CREATE TABLE core_factoryrun(id INTEGER PRIMARY KEY, product_id INTEGER, status TEXT);
                CREATE TABLE core_researchproject(id INTEGER PRIMARY KEY, factory_run_id INTEGER);
                INSERT INTO core_product VALUES
                    (1,'Synthetic test opportunity','digital','{}',0,'0',NULL,NULL,1);
            """)

    def _ledger(self, recipe):
        return json.loads((self.output / "qa-rework" / recipe / "ledger.json").read_text())

    def test_failure_preserves_old_zip_and_does_not_block_other_recipe(self):
        initial = cycle.run_cycle(self.db, self.output, self.recipes)
        self.assertEqual(initial["manufactured"], len(maker.RECIPES))
        recipe = "farm_enterprise_economics"
        good_file = (self.output / "digital-products" / recipe /
                     (recipe + "-internal-qa.zip"))
        hash_before = maker.sha256_file(good_file)
        (self.recipes / recipe / "calculator.py").write_text(
            "raise RuntimeError('formula regression')\n", encoding="utf-8"
        )
        result = cycle.run_cycle(self.db, self.output, self.recipes)
        self.assertEqual(result["status"], "needs_rework")
        self.assertEqual(result["manufactured"], len(maker.RECIPES) - 1)
        self.assertEqual(result["failed"], 1)
        self.assertEqual(maker.sha256_file(good_file), hash_before)
        record = self._ledger(recipe)
        self.assertEqual(record["current_status"], "needs_rework")
        self.assertEqual(record["history"][0]["code"], "PRODUCT_QA_FAILED")
        self.assertIn("required_correction", record["history"][0])
        self.assertFalse(record["public_sale_allowed"])
        state = json.loads((self.output / "production-state.json").read_text())
        self.assertFalse(state["artifact_qa_passed"])
        self.assertEqual(state["manufacturing_failed_recipe_count"], 1)
        self.assertEqual(state["private_rework_queue"]["needs_rework"], 1)
        self.assertEqual(state["publishable_product_count"], 0)

    def test_same_failure_does_not_create_duplicate_issue_each_hour(self):
        target = self.recipes / "farm_enterprise_economics" / "calculator.py"
        target.write_text("raise RuntimeError('failure')\n", encoding="utf-8")
        cycle.run_cycle(self.db, self.output, self.recipes)
        first = self._ledger("farm_enterprise_economics")
        cycle.run_cycle(self.db, self.output, self.recipes)
        second = self._ledger("farm_enterprise_economics")
        self.assertEqual(len(first["history"]), 1)
        self.assertEqual(len(second["history"]), 1)

    def test_source_repair_rebuilds_and_keeps_failure_history(self):
        recipe = "farm_enterprise_economics"
        target = self.recipes / recipe / "calculator.py"
        original = target.read_bytes()
        target.write_text("raise RuntimeError('simulated')\n", encoding="utf-8")
        cycle.run_cycle(self.db, self.output, self.recipes)
        target.write_bytes(original)
        after = cycle.run_cycle(self.db, self.output, self.recipes)
        self.assertEqual(after["status"], "ok")
        record = self._ledger(recipe)
        self.assertEqual(record["history"][0]["status"], "technically_recovered")
        self.assertEqual(len(record["history"][0]["fixed_artifact_sha256"]), 64)
        self.assertFalse(record["public_sale_allowed"])
        self.assertEqual(after["rework_queue"]["technical_qa_pass_only_owner_and_content_review_pending"], 1)

    def test_third_distinct_revision_escalates_to_expert_not_deletion(self):
        for index in range(3):
            status = repair.record_failure(
                self.output, "farm_enterprise_economics",
                "PRODUCT_QA_FAILED: failed assertion " + str(index),
                "sha256-source-" + str(index),
            )
        self.assertEqual(status["status"], "expert_review")
        self.assertEqual(len(self._ledger("farm_enterprise_economics")["history"]), 3)
        self.assertEqual(repair.summarize(self.output)["expert_review"], 1)

    def test_research_quality_failure_generates_actionable_non_discarding_ticket(self):
        result = cycle.run_cycle(self.db, self.output, self.recipes)
        self.assertEqual(result["status"], "ok")
        ledger = self.output / "research-rework" / "product-1" / "ledger.json"
        self.assertTrue(ledger.is_file())
        obj = json.loads(ledger.read_text())
        self.assertEqual(obj["current_status"], "research_correction_required")
        self.assertGreater(len(obj["history"][0]["blocking_reasons"]), 0)
        self.assertGreater(len(obj["history"][0]["corrective_actions"]), 0)
        self.assertFalse(obj["public_sale_allowed"])
        self.assertEqual(obj["history"][0]["independent_review_required"], True)
        before = len(obj["history"])
        cycle.run_cycle(self.db, self.output, self.recipes)
        self.assertEqual(len(json.loads(ledger.read_text())["history"]), before)
        state = json.loads((self.output / "production-state.json").read_text())
        self.assertEqual(state["research_correction_queue"]["research_correction_required"], 1)
        self.assertEqual(state["publishable_product_count"], 0)

    def test_research_defect_remains_stored_when_source_changes(self):
        cycle.run_cycle(self.db, self.output, self.recipes)
        with sqlite3.connect(str(self.db)) as conn:
            conn.execute(
                "UPDATE core_product SET metadata=? WHERE id=1",
                (json.dumps({"validation": {"outcome":"NEEDS_MORE_EVIDENCE", "missing_factors":["market_demand"]}}),)
            )
        cycle.run_cycle(self.db, self.output, self.recipes)
        obj = json.loads((self.output / "research-rework" / "product-1" / "ledger.json").read_text())
        self.assertEqual(len(obj["history"]), 2)
        self.assertEqual(obj["current_status"], "research_correction_required")

    def test_invalid_recipe_slug_never_writes_outside_private_root(self):
        with self.assertRaises(ValueError):
            repair.record_failure(self.output, "../danger", "any failure", "src")
        self.assertFalse((self.output / "qa-rework").exists())

    def test_pass_not_claimed_without_real_sha(self):
        repair.record_failure(self.output, "farm_enterprise_economics",
                              "PRODUCT_QA_FAILED: sample", "sha")
        with self.assertRaises(RuntimeError):
            repair.record_technical_recovery(
                self.output, "farm_enterprise_economics",
                {"qa_status": "passed", "artifact_sha256": "pretend"}
            )
        self.assertEqual(self._ledger("farm_enterprise_economics")["current_status"],
                         "needs_rework")


if __name__ == "__main__":
    unittest.main()
