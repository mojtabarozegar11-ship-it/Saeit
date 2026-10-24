"""Realistic private factory intake regression for 700 international education books."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

BASE = Path(__file__).resolve().parents[1]


def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, BASE / "scripts" / filename)
    obj = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(obj)
    return obj


EDU = load("education700_intake", "factory_education700_p0_intake_20261024.py")
STAGE = load("education700_stage1", "factory_stage1_handoff.py")
AGRI = load("education700_agri200", "factory_agri200_p0_intake.py")


class EducationalPriorityIntakeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.orders = self.root / "production-instructions/orders"

    def test_allocation_and_exactly_700_distinct_deliverables(self):
        items = EDU.source_specs()
        self.assertEqual(len(items), 700)
        self.assertEqual(len({item["id"] for item in items}), 700)
        self.assertEqual(len({item["title"] for item in items}), 700)
        for group, count in EDU.COUNTS.items():
            self.assertEqual(sum(x["group"] == group for x in items), count)
        self.assertEqual(sum(x["country"] == "United States" for x in items), 50)
        self.assertEqual(sum(x["country"] == "Canada" for x in items), 50)
        self.assertEqual(sum(x["country"] == "Iran" for x in items), 200)
        self.assertEqual(sum(x["country"] in {x[1] for x in EDU.GULF_COUNTRIES}
                             for x in items), 200)
        self.assertEqual({x["locale"] for x in items if x["group"] == "GC"},
                         {"ar-SA", "ar-AE", "ar-QA", "ar-KW", "ar-OM"})
        self.assertEqual({x["locale"] for x in items if x["group"] == "NA"},
                         {"en-US", "en-CA", "fr-CA"})

    def test_orders_private_100k_owner_discount_and_correct_sites(self):
        rows = EDU.source_specs()
        for rank, item in enumerate(rows, 1):
            order = EDU.make_order(item, rank)
            self.assertEqual(order["priority"], "P0")
            self.assertEqual(order["priority_rank"], rank)
            self.assertEqual(order["minimum_original_prose_words"], 100000)
            self.assertIs(order["curriculum_verified"], False)
            self.assertIs(order["independent_qc1000_verified"], False)
            self.assertIs(order["publication_approved"], False)
            self.assertIs(order["public_distribution_allowed"], False)
            self.assertIs(order["warehouse_goods_created"], False)
            self.assertEqual(order["discount_percent"], 0)
            self.assertEqual(order["discount_authority"], "OWNER_ONLY")
            self.assertEqual(len(order["editions"]), 1)
            self.assertEqual(order["editions"][0]["locale"], item["locale"])
            self.assertEqual(order["editions"][0]["site"],
                             "zomorodmelal.ir" if item["group"] == "IR"
                             else "mojplaywin.com")

    def test_idempotent_registration_keeps_700_original_order_bytes(self):
        self.assertEqual(EDU.install(self.root)["created"], 700)
        before = {p.name: p.read_bytes() for p in self.orders.glob("WO-*.json")}
        self.assertEqual(len(before), 700)
        self.assertEqual(EDU.install(self.root)["created"], 0)
        self.assertEqual({p.name: p.read_bytes() for p in
                          self.orders.glob("WO-*.json")}, before)
        index = json.loads((self.root / "production-instructions/"
                            "owner-education700-p0-index.json").read_text())
        self.assertEqual(index["requested_books"], 700)
        self.assertEqual(index["minimum_total_original_words"], 70_000_000)
        self.assertEqual(len(set(index["order_ids_ranked"])), 700)
        self.assertEqual(index["actual_manuscripts_completed"], 0)
        self.assertFalse(index["commercial_release"])

    def test_stage1_priorities_preserve_old_agri_and_handle_new_700_first(self):
        AGRI.install(self.root, BASE / "docs/agri200_p0_catalog.tsv")
        EDU.install(self.root)
        # one ordinary item to prove the education priority is not FIFO-only
        order = {
            "schema": STAGE.SCHEMA, "id": "WO-00000901",
            "origin": "ordinary-work", "status": "issued",
            "source_sha256": "a"*64, "fingerprint": "b"*64,
            "subject": "Independent mathematical simulation workbook",
            "instruction": "Develop a grounded lesson plan with real exercises.",
            "acceptance": ["Evidence is independently checked"],
            "manufacturing_qa_passed": False,
            "publication_approved": False,
            "public_distribution_allowed": False,
        }
        AGRI.save(self.orders / "WO-00000901.json", order)
        first = STAGE.run(self.root, batch=200)
        self.assertEqual(first["new_handoffs"], 200)
        self.assertFalse((self.root / "production-instructions/stage-02/inbox/"
                          "WO-00000901--r001.json").exists())
        second = STAGE.run(self.root, batch=2000)
        self.assertEqual(second["new_handoffs"], 701)
        idx = json.loads((self.root / "production-instructions/"
                          "owner-education700-p0-index.json").read_text())
        for work_id in idx["order_ids_ranked"]:
            receipt = json.loads((self.root / "production-instructions/stage-01/"
                                  "receipts" / (work_id + "--r001.json")).read_text())
            self.assertIs(receipt["stage_1_completed"], True)
            self.assertIs(receipt["research_completed"], False)
        self.assertEqual(STAGE.run(self.root, batch=2000)["new_handoffs"], 0)

    def test_existing_work_order_state_remains_unchanged(self):
        EDU.install(self.root)
        path = self.orders / "WO-00000001.json"
        record = json.loads(path.read_text())
        record["status"] = "in_engineering"
        AGRI.save(path, record)
        before = path.read_bytes()
        self.assertEqual(EDU.install(self.root)["created"], 0)
        self.assertEqual(path.read_bytes(), before)

    def test_invalid_old_order_blocks_without_overwrite(self):
        EDU.install(self.root)
        path = self.orders / "WO-00000001.json"
        record = json.loads(path.read_text())
        record["public_distribution_allowed"] = True
        AGRI.save(path, record)
        with self.assertRaisesRegex(ValueError, "EDUCATION_INVALID_EXISTING_ORDER"):
            EDU.install(self.root)
        self.assertTrue(json.loads(path.read_text())["public_distribution_allowed"])


if __name__ == "__main__":
    unittest.main()
