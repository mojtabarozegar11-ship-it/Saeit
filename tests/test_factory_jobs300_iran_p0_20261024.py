"""300 original Iran trade-training orders, preserves prior 900 P0 queue positions."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

BASE = Path(__file__).resolve().parents[1]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, BASE / "scripts" / path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


JOBS = load("jobs300_owner_p0", "factory_jobs300_iran_p0_intake_20261024.py")
EDU = load("jobs300_existing_edu700", "factory_education700_p0_intake_20261024.py")
AGRI = load("jobs300_existing_agri200", "factory_agri200_p0_intake.py")
STAGE = load("jobs300_stage1", "factory_stage1_handoff.py")


class OwnerJobs300Tests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.queue = self.root / "production-instructions/orders"

    def test_exactly_300_unique_real_professions(self):
        rows = JOBS.catalog()
        self.assertEqual(len(rows), 300)
        self.assertEqual(len({x["trade"] for x in rows}), 300)
        self.assertEqual(len({x["title"] for x in rows}), 300)
        self.assertEqual(len({x["sector"] for x in rows}), 15)
        self.assertEqual(rows[0]["id"], "JOB-IR-001")
        self.assertEqual(rows[-1]["id"], "JOB-IR-300")
        self.assertEqual({x["selling_locale"] for x in rows}, {"fa-IR"})

    def test_every_order_meets_owner_private_quality_contract(self):
        for rank, spec in enumerate(JOBS.catalog(), 1):
            order = JOBS.order_for(spec, rank)
            self.assertEqual(order["origin"], JOBS.ORIGIN)
            self.assertEqual(order["priority"], "P0")
            self.assertEqual(order["priority_rank"], rank)
            self.assertEqual(order["editions"][0]["site"], "zomorodmelal.ir")
            self.assertEqual(order["editions"][0]["locale"], "fa-IR")
            self.assertEqual(order["editions"][0]["currency"], "IRR")
            self.assertEqual(order["minimum_original_prose_words"], 100000)
            self.assertEqual(order["discount_authority"], "OWNER_ONLY")
            self.assertEqual(order["discount_percent"], 0)
            for key in ("independent_qc1000_verified", "publication_approved",
                        "public_distribution_allowed", "warehouse_goods_created",
                        "commercial_release", "manufacturing_qa_passed"):
                self.assertIs(order[key], False)

    def test_real_private_queue_idempotent_and_immutable(self):
        first = JOBS.install(self.root)
        self.assertEqual(first["new_orders"], 300)
        before = {p.name: p.read_bytes() for p in self.queue.glob("WO-*.json")}
        self.assertEqual(len(before), 300)
        self.assertEqual(JOBS.install(self.root)["new_orders"], 0)
        self.assertEqual({p.name: p.read_bytes() for p in self.queue.glob("WO-*.json")}, before)
        index = json.loads((self.root / "production-instructions/"
                            "owner-jobs300-ir-p0-index.json").read_text())
        self.assertEqual(index["book_goal_count"], 300)
        self.assertEqual(index["minimum_total_original_prose_words"], 30_000_000)
        self.assertEqual(index["independently_approved_books"], 0)
        self.assertEqual(index["published_books"], 0)

    def test_prior_700_unchanged_and_high_priority_independent(self):
        EDU.install(self.root)
        old = {p.name: p.read_bytes() for p in self.queue.glob("WO-*.json")}
        self.assertEqual(len(old), 700)
        self.assertEqual(JOBS.install(self.root)["new_orders"], 300)
        for name, raw in old.items():
            self.assertEqual((self.queue / name).read_bytes(), raw)
        self.assertEqual(len(list(self.queue.glob("WO-*.json"))), 1000)

    def test_no_priority_starvation_with_1200_old_and_new_p0_orders(self):
        AGRI.install(self.root, BASE / "docs/agri200_p0_catalog.tsv")
        EDU.install(self.root)
        JOBS.install(self.root)
        self.assertEqual(len(list(self.queue.glob("WO-*.json"))), 1200)
        first = STAGE.run(self.root, batch=1000)
        self.assertEqual(first["new_handoffs"], 1000)
        self.assertEqual(first["blocked_items_this_run"], 0)
        second = STAGE.run(self.root, batch=1000)
        self.assertEqual(second["new_handoffs"], 200)
        self.assertEqual(second["blocked_items_this_run"], 0)
        idx = json.loads((self.root / "production-instructions/"
                          "owner-jobs300-ir-p0-index.json").read_text())
        for work_id in idx["order_ids_ranked"]:
            path = self.root / "production-instructions/stage-01/receipts" / (
                work_id + "--r001.json")
            inbox = self.root / "production-instructions/stage-02/inbox" / (
                work_id + "--r001.json")
            self.assertTrue(path.is_file())
            self.assertTrue(inbox.is_file())
            self.assertFalse(json.loads(inbox.read_text())["quality1000_approved"])
        self.assertEqual(STAGE.run(self.root, batch=1000)["new_handoffs"], 0)

    def test_mutated_existing_order_hard_blocked(self):
        JOBS.install(self.root)
        path = self.queue / "WO-00000001.json"
        data = json.loads(path.read_text())
        data["publication_approved"] = True
        AGRI.save(path, data)
        with self.assertRaisesRegex(ValueError, "JOBS300_EXISTING_ORDER_FINGERPRINT_CONFLICT"):
            JOBS.install(self.root)


if __name__ == "__main__":
    unittest.main()
