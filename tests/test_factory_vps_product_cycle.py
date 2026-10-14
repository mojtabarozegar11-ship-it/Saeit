"""Integration QA: order-independent autonomous VPS product manufacturing."""
import importlib.util
import json
from pathlib import Path
import sqlite3
import shutil
import tempfile
import unittest

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
        self.assertEqual(first["manufactured"], 2)
        state = json.loads((self.output / "production-state.json").read_text(encoding="utf-8"))
        self.assertFalse(state["depends_on_orders"])
        self.assertEqual(state["built_product_count"], 2)
        self.assertTrue(state["artifact_qa_passed"])
        self.assertFalse(state["publishable_product_count"])
        self.assertTrue((self.output / "digital-products" /
                         "farm_enterprise_economics" /
                         "farm_enterprise_economics-internal-qa.zip").exists())
        self.assertEqual(before, self.db.read_bytes())

    def test_second_cycle_is_safe_and_idempotent(self):
        cycle.run_cycle(self.db, self.output, self.recipes)
        subsequent = cycle.run_cycle(self.db, self.output, self.recipes)
        self.assertEqual(subsequent["status"], "ok")
        self.assertEqual(subsequent["updated"], 0)

    def test_missing_recipe_stops_without_claiming_production(self):
        with self.assertRaises(RuntimeError):
            cycle.run_cycle(self.db, self.output, self.home / "missing")
        self.assertFalse((self.output / "production-state.json").exists())


if __name__ == "__main__":
    unittest.main()
