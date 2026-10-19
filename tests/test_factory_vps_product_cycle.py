"""Integration QA: order-independent autonomous VPS product manufacturing."""
import importlib.util
import json
from pathlib import Path
import sqlite3
import shutil
import tempfile
import unittest
from unittest import mock
import fcntl

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "saeit_vps_cycle", str(ROOT / "scripts" / "factory_vps_product_cycle.py")
)
cycle = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cycle)


class FactoryVPSCycleTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.home = Path(self.temporary.name)
        self.db = self.home / "factory.db"
        self.recipes = self.home / "product_recipes"
        self.output = self.home / "factory-private"
        shutil.copytree(ROOT / "product_recipes" / "farm_enterprise_economics",
                        self.recipes / "farm_enterprise_economics")
        shutil.copytree(ROOT / "product_recipes" / "water_budget_economics",
                        self.recipes / "water_budget_economics")
        shutil.copytree(ROOT / "product_recipes" / "greenhouse_crop_margin",
                        self.recipes / "greenhouse_crop_margin")
        with sqlite3.connect(str(self.db)) as connection:
            connection.executescript("""
                CREATE TABLE core_product(
                    id INTEGER PRIMARY KEY, title TEXT, product_type TEXT,
                    metadata TEXT, active INTEGER, price TEXT,
                    owner_id INTEGER, knowledge_article_id INTEGER,
                    factory_managed INTEGER
                );
                CREATE TABLE core_factoryrun(id INTEGER PRIMARY KEY, product_id INTEGER, status TEXT);
                CREATE TABLE core_researchproject(id INTEGER PRIMARY KEY, factory_run_id INTEGER);
            """)
            metadata = json.dumps({"factory_state":"needs_research","validation":{
                "outcome":"NEEDS_MORE_EVIDENCE","missing_factors":["sources","QA"]}})
            connection.execute("INSERT INTO core_product VALUES (?,?,?,?,?,?,?,?,?)",
                (1, "Factory Candidate", "digital", metadata, 0, "0", None, None, 1))

    def test_cycle_manufactures_real_product_with_no_order_table(self):
        before = self.db.read_bytes()
        first = cycle.run_cycle(self.db, self.output, self.recipes)
        self.assertEqual(first["status"], "ok")
        self.assertEqual(first["processed"], 1)
        self.assertEqual(first["manufactured"], 3)
        state = json.loads((self.output / "production-state.json").read_text(encoding="utf-8"))
        self.assertFalse(state["depends_on_orders"])
        self.assertEqual(state["built_product_count"], 3)
        self.assertEqual(state["new_or_updated_product_count"],3)
        self.assertEqual(state["unchanged_product_rechecks"],0)
        self.assertEqual(first["new_artifacts"],3)
        self.assertEqual(state["api_usage"], "none")
        self.assertEqual(state["token_usage"], 0)
        self.assertTrue(state["artifact_qa_passed"])
        self.assertTrue(state["technical_zip_checks_only"])
        self.assertEqual(state["research_review_candidate_count"], 0)
        self.assertFalse(state["research_evidence_thresholds_satisfied_for_all_scanned"])
        self.assertFalse(state["commercial_quality_review_completed"])
        self.assertFalse(state["publishable_product_count"])
        self.assertTrue((self.output / "digital-products" /
                         "farm_enterprise_economics" /
                         "farm_enterprise_economics-internal-qa.zip").exists())
        self.assertTrue((self.output / "digital-products" /
                         "greenhouse_crop_margin" /
                         "greenhouse_crop_margin-internal-qa.zip").exists())
        self.assertEqual(before, self.db.read_bytes())

    def test_second_cycle_is_safe_and_idempotent(self):
        cycle.run_cycle(self.db, self.output, self.recipes)
        subsequent = cycle.run_cycle(self.db, self.output, self.recipes)
        self.assertEqual(subsequent["status"], "ok")
        self.assertEqual(subsequent["updated"], 0)
        self.assertEqual(subsequent["new_artifacts"],0)
        state=json.loads((self.output/"production-state.json").read_text(encoding="utf8"))
        self.assertEqual(state["new_or_updated_product_count"],0)
        self.assertEqual(state["unchanged_product_rechecks"],3)

    def test_cycle_builds_a_recipe_added_after_the_factory_code(self):
        shutil.copytree(ROOT / "product_recipes" / "farm_enterprise_economics",
                        self.recipes / "new_product_family")
        (self.recipes / "new_product_family" / "README.md").write_text(
            "# New Product Family\n", encoding="utf-8")
        result = cycle.run_cycle(self.db, self.output, self.recipes)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["manufactured"], 4)
        self.assertTrue((self.output / "digital-products" / "new_product_family" /
                         "new_product_family-internal-qa.zip").is_file())
        state = json.loads((self.output / "production-state.json").read_text(encoding="utf-8"))
        self.assertEqual(state["registered_recipe_count"], 4)
        self.assertEqual(state["token_usage"], 0)

    def test_missing_recipe_stops_without_claiming_production(self):
        with self.assertRaises(RuntimeError):
            cycle.run_cycle(self.db, self.output, self.home / "missing")
        self.assertFalse((self.output / "production-state.json").exists())


if __name__ == "__main__":
    unittest.main()

class FactoryCycleIsolationTests(unittest.TestCase):
    setUp = FactoryVPSCycleTests.setUp
    def test_bounded_cycles_rotate_recipes(self):
        seen = []
        for _ in range(3):
            cycle.run_cycle(self.db, self.output, self.recipes, max_recipes=1)
            state = json.loads((self.output/'production-state.json').read_text())
            seen.extend(state['built_product_recipes'])
        self.assertEqual(len(set(seen)),3)

    def test_invalid_recipe_is_reported_without_stopping_good_products(self):
        (self.recipes/'broken_recipe').mkdir()
        result = cycle.run_cycle(self.db, self.output, self.recipes)
        self.assertEqual(result['status'],'needs_rework')
        self.assertEqual(result['manufactured'],3)
        state = json.loads((self.output/'production-state.json').read_text())
        self.assertEqual(state['recipe_admission_failures'][0]['recipe'],'broken_recipe')
        self.assertFalse(state['artifact_qa_passed'])


class FactorySynthesisIntegrationTests(unittest.TestCase):
    setUp = FactoryVPSCycleTests.setUp

    def test_cli_overlap_is_successful_skip(self):
        self.output.mkdir()
        with (self.output/'.production-cycle.lock').open('a+b') as locked:
            fcntl.flock(locked.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            status=cycle.main(['--db',str(self.db),'--out',str(self.output),
                               '--recipes',str(self.recipes)])
        self.assertEqual(status,0)
        self.assertFalse((self.output/'production-state.json').exists())

    def test_designer_storage_failure_does_not_stop_existing_products(self):
        self.output.mkdir()
        (self.output/'design-state').write_text('deliberately not a directory')
        result=cycle.run_cycle(self.db,self.output,self.recipes,enable_designer=True)
        self.assertEqual(result['status'],'needs_rework')
        self.assertEqual(result['manufactured'],3)
        state=json.loads((self.output/'production-state.json').read_text())
        self.assertTrue(state['designer_failures'])
        self.assertEqual(len(list((self.output/'digital-products').glob('*/*-internal-qa.zip'))),3)

    def test_unclassified_product_runtime_failure_is_durable_and_isolated(self):
        real_load=cycle.load
        maker=real_load('isolated_maker',ROOT/'scripts/factory_product_maker.py')
        original=maker.manufacture
        def manufacture(recipe,*args,**kwargs):
            if recipe=='farm_enterprise_economics':
                raise RuntimeError('NEW_PRODUCT_FAILURE_CATEGORY')
            return original(recipe,*args,**kwargs)
        def load(name,path):
            return maker if name=='saeit_factory_manufacturer_cycle' else real_load(name,path)
        with mock.patch.object(maker,'manufacture',side_effect=manufacture), mock.patch.object(cycle,'load',side_effect=load):
            result=cycle.run_cycle(self.db,self.output,self.recipes)
        self.assertEqual(result['status'],'needs_rework')
        self.assertEqual(result['manufactured'],2)
        ledger=json.loads((self.output/'qa-rework/farm_enterprise_economics/ledger.json').read_text())
        self.assertIn('NEW_PRODUCT_FAILURE_CATEGORY',ledger['history'][-1]['actual_error_excerpt'])

    def test_missing_generated_tests_are_repaired_before_catalog_admission(self):
        cycle.run_cycle(self.db,self.output,self.recipes,enable_designer=True)
        cycle.run_cycle(self.db,self.output,self.recipes,enable_designer=True)
        generated=next((self.output/'generated-product-recipes').iterdir())
        for file in generated.glob('test_*.py'): file.unlink()
        result=cycle.run_cycle(self.db,self.output,self.recipes,enable_designer=True)
        self.assertEqual(result['status'],'ok')
        self.assertEqual(result['registered_recipes'],5)
        self.assertTrue(list(generated.glob('test_*.py')))
        state=json.loads((self.output/'production-state.json').read_text())
        self.assertEqual(len(state['source_recoveries']),1)
        retained=Path(state['source_recoveries'][0]['retained_broken_source'])
        self.assertFalse(list(retained.glob('test_*.py')))

    def test_new_recipe_is_generated_built_and_repaired_without_static_folder(self):
        static_before = sorted(x.name for x in self.recipes.iterdir())
        first = cycle.run_cycle(self.db, self.output, self.recipes, enable_designer=True)
        self.assertEqual(first["registered_recipes"],4)
        self.assertEqual(first["new_recipe_count"],1)
        second = cycle.run_cycle(self.db, self.output, self.recipes, enable_designer=True)
        self.assertEqual(second["registered_recipes"],5)
        self.assertEqual(second["new_recipe_count"],1)
        self.assertEqual(sorted(x.name for x in self.recipes.iterdir()),static_before)
        generated=next((self.output/"generated-product-recipes").iterdir())
        (generated/"calculator.py").write_text("raise RuntimeError('deliberate fault')\n")
        third=cycle.run_cycle(self.db, self.output, self.recipes, enable_designer=True)
        self.assertEqual(third["status"],"ok")
        self.assertEqual(third["new_artifacts"],0)
        state=json.loads((self.output/"production-state.json").read_text())
        self.assertEqual(len(state["source_recoveries"]),1)
        self.assertTrue(Path(state["source_recoveries"][0]["retained_broken_source"]).is_dir())
        ledger=json.loads((self.output/"qa-rework"/generated.name/"ledger.json").read_text())
        self.assertEqual(ledger["current_status"],"technical_qa_pass_only_owner_and_content_review_pending")
        self.assertGreaterEqual(len(ledger["history"]),1)
