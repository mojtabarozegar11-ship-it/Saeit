"""Autonomous factory inventory is demand-aware in principle, never order-driven."""
import importlib.util
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "saeit_autonomous_factory", str(ROOT / "scripts" / "factory_autonomous_portfolio.py")
)
factory = importlib.util.module_from_spec(spec)
spec.loader.exec_module(factory)


class AutonomousProductTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db = Path(self.temp.name) / "factory.db"
        self.out = Path(self.temp.name) / "private-output"
        with sqlite3.connect(str(self.db)) as con:
            con.executescript("""
                CREATE TABLE core_product(
                    id INTEGER PRIMARY KEY, title TEXT, product_type TEXT,
                    metadata TEXT, active INTEGER, price TEXT, owner_id INTEGER,
                    knowledge_article_id INTEGER, factory_managed INTEGER
                );
                CREATE TABLE core_factoryrun(
                    id INTEGER PRIMARY KEY, product_id INTEGER, status TEXT
                );
                CREATE TABLE core_researchproject(
                    id INTEGER PRIMARY KEY, factory_run_id INTEGER
                );
            """)
            meta = json.dumps({"factory_state": "needs_research", "validation": {
                "outcome": "NEEDS_MORE_EVIDENCE", "missing_factors": ["more evidence"]}})
            con.executemany("INSERT INTO core_product VALUES (?,?,?,?,?,?,?,?,?)", [
                (1, "Factory research one", "digital", meta, 0, "0", None, None, 1),
                (2, "Ordinary website product", "digital", meta, 0, "0", None, None, 0),
                (3, "Factory research three", "digital", meta, 0, "0", None, None, 1),
                (4, "Already published", "digital", meta, 1, "120", 1, None, 1),
                (5, "Factory research five", "digital", meta, 0, "0", None, None, 1),
            ])

    def test_processes_unsold_products_without_any_order_table(self):
        original = self.db.read_bytes()
        first = factory.build(str(self.db), str(self.out), 2)
        self.assertEqual([p["product_id"] for p in first["entries"]], [1, 3])
        self.assertFalse(first["depends_on_customer_orders"])
        self.assertTrue(all(not p["publish_authorized"] for p in first["entries"]))
        self.assertEqual(first["updated_count"], 2)
        self.assertEqual(self.db.read_bytes(), original)
        self.assertFalse((self.out / "product-2").exists())
        self.assertFalse((self.out / "product-4").exists())
        self.assertTrue((self.out / "product-1" / "internal_draft.md").exists())
        self.assertEqual((self.out / "product-1" / "internal_draft.md").stat().st_mode & 0o777, 0o600)

    def test_rotates_inventory_and_skips_identical_dossiers(self):
        factory.build(str(self.db), str(self.out), 2)  # 1 and 3
        second = factory.build(str(self.db), str(self.out), 2)
        self.assertEqual([p["product_id"] for p in second["entries"]], [5, 1])
        self.assertEqual(second["updated_count"], 1)
        self.assertEqual(second["unchanged_count"], 1)
        third = factory.build(str(self.db), str(self.out), 3)
        self.assertEqual([p["product_id"] for p in third["entries"]], [3, 5, 1])
        self.assertEqual(third["updated_count"], 0)

    def test_invalid_batch_fails_without_file_changes(self):
        with self.assertRaises(ValueError):
            factory.build(str(self.db), str(self.out), 0)
        self.assertFalse(self.out.exists())

    def test_no_products_is_safe(self):
        with sqlite3.connect(str(self.db)) as con:
            con.execute("UPDATE core_product SET factory_managed=0")
        result = factory.build(str(self.db), str(self.out), 25)
        self.assertEqual(result["processed_count"], 0)
        self.assertFalse((self.out / "product-1").exists())


if __name__ == "__main__":
    unittest.main()
