"""Offline-only contract checks for 200 owner-priority private agriculture orders."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

BASE=Path(__file__).resolve().parents[1]
SPEC=importlib.util.spec_from_file_location("factory_agri200",BASE/"scripts/factory_agri200_p0_intake.py")
MODULE=importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
ORDERS_SPEC=importlib.util.spec_from_file_location("factory_orders_lanes",BASE/"scripts/factory_continuous_production_orders.py")
ORDERS=importlib.util.module_from_spec(ORDERS_SPEC)
ORDERS_SPEC.loader.exec_module(ORDERS)
CATALOG=BASE/"docs/agri200_p0_catalog.tsv"


class OwnerAgri200Test(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)/"private"
        self.root.mkdir()

    def test_catalog_200_unique_ranked_localized_topics(self):
        rows=MODULE.catalog(CATALOG)
        self.assertEqual(len(rows),200)
        self.assertEqual(rows[0][0],"AGRI-001")
        self.assertEqual(rows[-1][0],"AGRI-200")
        item=MODULE.make_order(*rows[0],1)
        self.assertEqual(item["priority"],"P0")
        self.assertEqual(item["priority_rank"],1)
        self.assertEqual({e["locale"] for e in item["editions"]},{"fa-IR","en-US"})
        self.assertEqual({e["site"] for e in item["editions"]},{"zomorodmelal.ir","mojplaywin.com"})
        for name in ("manufacturing_qa_passed","publication_approved","warehouse_goods_created","commercial_release","public_distribution_allowed"):
            self.assertIs(item[name],False)

    def test_200_written_once_no_stock_or_site(self):
        initial=MODULE.install(self.root,CATALOG)
        self.assertEqual(initial["created"],200)
        self.assertEqual(initial["registered"],200)
        self.assertEqual(initial["editions"],400)
        queue=self.root/"production-instructions/orders"
        paths=sorted(queue.glob("WO-*.json"))
        self.assertEqual(len(paths),200)
        before={p.name:p.read_bytes() for p in paths}
        again=MODULE.install(self.root,CATALOG)
        self.assertEqual(again["created"],0)
        self.assertEqual({p.name:p.read_bytes() for p in paths},before)
        index=json.loads((self.root/"production-instructions/owner-agri200-p0-index.json").read_text())
        self.assertEqual(index["edition_goal_count"],400)
        self.assertEqual(len(index["order_ids_ranked"]),200)
        self.assertFalse(index["commercial_release"])
        self.assertFalse(index["qa1000_certified"])
        self.assertEqual(index["site_deployments"],0)

    def test_generator_lane_isolation_under_p0_load(self):
        MODULE.install(self.root,CATALOG)
        ORDERS.generate(self.root,max_backlog=1)
        status=json.loads((self.root/"production-instructions/order-status.json").read_text())
        self.assertEqual(status["pending_owner_agri_p0_instructions"],200)
        self.assertEqual(status["pending_research_instructions"],0)
        self.assertEqual(status["pending_manufacturing_instructions"],0)
        self.assertIsNone(status["manufacturing_capacity_available"])

    def test_existing_order_is_preserved(self):
        MODULE.install(self.root,CATALOG)
        p=self.root/"production-instructions/orders/WO-00000001.json"
        order=json.loads(p.read_text())
        order["status"]="in_engineering"
        MODULE.save(p,order)
        data=p.read_bytes()
        MODULE.install(self.root,CATALOG)
        self.assertEqual(p.read_bytes(),data)

    def test_reject_corrupt_prior_record_without_overwrite(self):
        MODULE.install(self.root,CATALOG)
        p=self.root/"production-instructions/orders/WO-00000001.json"
        content=json.loads(p.read_text());content["public_distribution_allowed"]=True
        MODULE.save(p,content)
        with self.assertRaisesRegex(ValueError,"P0_UNSAFE_EXISTING_ORDER"):
            MODULE.install(self.root,CATALOG)

    def test_deleted_historical_order_cannot_be_recreated(self):
        MODULE.install(self.root,CATALOG)
        index=self.root/"production-instructions/owner-agri200-p0-index.json"
        old_index=index.read_bytes()
        queue=self.root/"production-instructions/orders"
        (queue/"WO-00000001.json").unlink()  # synthetic temp fixture only
        with self.assertRaisesRegex(ValueError,"P0_HISTORICAL_ORDER_MISSING_RECONCILE_NOT_RECREATE"):
            MODULE.install(self.root,CATALOG)
        self.assertEqual(index.read_bytes(),old_index)
        self.assertEqual(len(list(queue.glob("WO-*.json"))),199)

    def test_all_deleted_historical_orders_remain_blocked(self):
        MODULE.install(self.root,CATALOG)
        index=self.root/"production-instructions/owner-agri200-p0-index.json"
        old_index=index.read_bytes()
        queue=self.root/"production-instructions/orders"
        for item in queue.glob("WO-*.json"):
            item.unlink()  # synthetic temp fixture only
        with self.assertRaisesRegex(ValueError,"P0_HISTORICAL_ORDER_MISSING_RECONCILE_NOT_RECREATE"):
            MODULE.install(self.root,CATALOG)
        self.assertEqual(index.read_bytes(),old_index)
        self.assertEqual(list(queue.glob("WO-*.json")),[])

    def test_tampered_historical_index_refuses_rebinding(self):
        MODULE.install(self.root,CATALOG)
        index=self.root/"production-instructions/owner-agri200-p0-index.json"
        data=json.loads(index.read_text())
        data["order_ids_ranked"][0]="WO-99999999"
        MODULE.save(index,data)
        old_index=index.read_bytes()
        with self.assertRaisesRegex(ValueError,"P0_HISTORICAL_ORDER_MISSING_RECONCILE_NOT_RECREATE"):
            MODULE.install(self.root,CATALOG)
        self.assertEqual(index.read_bytes(),old_index)



if __name__=="__main__":
    unittest.main()
