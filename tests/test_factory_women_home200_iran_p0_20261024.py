"""Owner-required 200 women-focused home microbusiness P0 orders, independent of earlier 1200."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

BASE = Path(__file__).resolve().parents[1]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, BASE / "scripts" / path)
    obj = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(obj)
    return obj


HOME = load("women_home200", "factory_women_home200_iran_p0_intake_20261024.py")
JOBS = load("existing_jobs300", "factory_jobs300_iran_p0_intake_20261024.py")
EDU = load("existing_edu700", "factory_education700_p0_intake_20261024.py")
AGRI = load("existing_agri200", "factory_agri200_p0_intake.py")
STAGE = load("women_home_stage1", "factory_stage1_handoff.py")


class WomenHome200Tests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.queue = self.root / "production-instructions/orders"

    def test_200_unique_home_businesses_and_ten_exact_sectors(self):
        rows = HOME.catalog()
        self.assertEqual(len(rows), 200)
        self.assertEqual(len({r["trade"] for r in rows}), 200)
        self.assertEqual(len({r["title"] for r in rows}), 200)
        self.assertEqual(len({r["sector"] for r in rows}), 10)
        self.assertEqual(rows[0]["id"], "HOME-IR-001")
        self.assertEqual(rows[-1]["id"], "HOME-IR-200")
        previous = {name for _, names in JOBS.SECTORS for name in names}
        self.assertFalse(previous.intersection({r["trade"] for r in rows}))

    def test_every_product_is_p0_private_and_has_owner_discount_gate(self):
        for rank, spec in enumerate(HOME.catalog(), 1):
            order = HOME.order_for(spec, rank)
            self.assertEqual(order["origin"], HOME.ORIGIN)
            self.assertEqual(order["priority"], "P0")
            self.assertEqual(order["priority_rank"], rank)
            self.assertEqual(order["minimum_original_prose_words"], 100000)
            self.assertEqual(order["editions"][0]["locale"], "fa-IR")
            self.assertEqual(order["editions"][0]["site"], "zomorodmelal.ir")
            self.assertEqual(order["editions"][0]["currency"], "IRR")
            self.assertEqual(order["discount_percent"], 0)
            self.assertEqual(order["discount_authority"], "OWNER_ONLY")
            for key in ("manufacturing_qa_passed", "publication_approved",
                        "public_distribution_allowed", "warehouse_goods_created",
                        "independent_qc1000_verified", "commercial_release"):
                self.assertFalse(order[key])

    def test_200_private_orders_replay_no_duplicate_or_public_stock(self):
        self.assertEqual(HOME.install(self.root)["new_orders"], 200)
        before = {p.name: p.read_bytes() for p in self.queue.glob("WO-*.json")}
        self.assertEqual(HOME.install(self.root)["new_orders"], 0)
        self.assertEqual({p.name: p.read_bytes() for p in self.queue.glob("WO-*.json")}, before)
        idx = json.loads((self.root / "production-instructions/"
                          "owner-women-home200-ir-p0-index.json").read_text())
        self.assertEqual(idx["book_goal_count"], 200)
        self.assertEqual(idx["sector_count"], 10)
        self.assertEqual(idx["minimum_total_original_prose_words"], 20_000_000)
        self.assertEqual(idx["published_books"], 0)
        self.assertEqual(idx["fully_authored_books"], 0)

    def test_existing_300_orders_unchanged(self):
        JOBS.install(self.root)
        older = {p.name: p.read_bytes() for p in self.queue.glob("WO-*.json")}
        self.assertEqual(HOME.install(self.root)["new_orders"], 200)
        self.assertEqual(len(list(self.queue.glob("WO-*.json"))), 500)
        for key, value in older.items():
            self.assertEqual((self.queue / key).read_bytes(), value)

    def test_new_home_work_gets_receipt_even_when_1200_old_p0_issued(self):
        AGRI.install(self.root, BASE / "docs/agri200_p0_catalog.tsv")
        EDU.install(self.root)
        JOBS.install(self.root)
        self.assertEqual(len(list(self.queue.glob("WO-*.json"))), 1200)
        self.assertEqual(STAGE.run(self.root, batch=2000)["new_handoffs"], 1200)
        HOME.install(self.root)
        # Without an unreceipted-first sort, new orders at P0 rank group 3
        # would be starved by the 1200 already-forwarded "issued" orders.
        status = STAGE.run(self.root, batch=1000)
        self.assertEqual(status["new_handoffs"], 200)
        self.assertEqual(status["blocked_items_this_run"], 0)
        idx = json.loads((self.root / "production-instructions/"
                          "owner-women-home200-ir-p0-index.json").read_text())
        for name in idx["order_ids_ranked"]:
            receipt = self.root / "production-instructions/stage-01/receipts" / (name + "--r001.json")
            inbox = self.root / "production-instructions/stage-02/inbox" / (name + "--r001.json")
            self.assertTrue(receipt.is_file())
            self.assertTrue(inbox.is_file())
            self.assertFalse(json.loads(inbox.read_text())["quality1000_approved"])
        self.assertEqual(STAGE.run(self.root, batch=1000)["new_handoffs"], 0)

    def test_mutated_prior_order_is_rejected_not_accepted_as_new(self):
        HOME.install(self.root)
        path = self.queue / "WO-00000001.json"
        item = json.loads(path.read_text())
        item["discount_percent"] = 50
        AGRI.save(path, item)
        with self.assertRaisesRegex(ValueError, "HOME200_EXISTING_ORDER_FINGERPRINT_CONFLICT"):
            HOME.install(self.root)


if __name__ == "__main__":
    unittest.main()
