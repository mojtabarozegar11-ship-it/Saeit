"""Operational work-order audit: never auto-invent findings or commercial approvals."""
import hashlib,importlib.util,json
from pathlib import Path
import tempfile,unittest
ROOT=Path(__file__).resolve().parents[1]
PATH=ROOT/"scripts/factory_quality_production_workorders_v1.py"
spec=importlib.util.spec_from_file_location("real_quality_orders",PATH)
jobs=importlib.util.module_from_spec(spec);spec.loader.exec_module(jobs)
SCORER=ROOT/"scripts/factory_quality_1000_v2.py"
CATALOG=ROOT/"factory_config/quality_100_criteria.json"

class WorkOrders(unittest.TestCase):
    def test_100_actionable_groups_and_immutable_repeat_safe_receipt(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);bucket=root/"quality-excellence/rework/example_product"
            bucket.mkdir(parents=True)
            initial={"recipe":"example_product","quality_status":"RETURN_TO_PRODUCTION_QUALITY",
                     "defects":["P0_ORIGINAL_INNOVATIONS_UNPROVEN"],
                     "rework_actions":["REWORK_NOVELTY"],
                     "artifact_sha256":"a"*64,
                     "quality_1000_scorecard":{"criteria":{}}}
            (bucket/"current.json").write_text(json.dumps(initial))
            first=jobs.work_orders(root,SCORER,CATALOG,"run1")
            self.assertEqual(first["products"],1)
            self.assertEqual(first["pending_groups_total"],100)
            order=root/"quality-excellence/production-workorders/example_product/current.json"
            record=json.loads(order.read_text())
            self.assertEqual(record["group_count"],100)
            self.assertEqual(record["points_per_group"],10)
            self.assertEqual(len(record["required_criterion_work"]),100)
            self.assertFalse(record["commercial_publish_allowed"])
            existing=sorted(order.parent.glob("order-*.json"))
            self.assertEqual(len(existing),1)
            digest=hashlib.sha256(existing[0].read_bytes()).hexdigest()
            second=jobs.work_orders(root,SCORER,CATALOG,"run2")
            self.assertEqual(second["products"],1)
            kept=sorted(order.parent.glob("order-*.json"))
            self.assertEqual(len(kept),1)
            self.assertEqual(hashlib.sha256(kept[0].read_bytes()).hexdigest(),digest)
    def test_evidence_done_does_not_automatically_sign_off(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);bucket=root/"quality-excellence/rework/example_product"
            bucket.mkdir(parents=True)
            rows={"Q%03d"%n:{"documentary_points":10,
                 "evidence_status":"HASH_CHECK_ONLY"} for n in range(1,101)}
            (bucket/"current.json").write_text(json.dumps({
                "recipe":"example_product","defects":[],"rework_actions":[],
                "artifact_sha256":"b"*64,
                "quality_1000_scorecard":{"criteria":rows}}))
            r=jobs.work_orders(root,SCORER,CATALOG,"run-valid")
            self.assertEqual(r["pending_groups_total"],0)
            document=json.loads((root/"quality-excellence/production-workorders/example_product/current.json").read_text())
            self.assertEqual(document["status"],"WAITING_SIGNED_INDEPENDENT_APPROVAL")
            self.assertTrue(document["signed_external_quality_approval_required"])
            self.assertFalse(document["commercial_publish_allowed"])
if __name__=="__main__":unittest.main()
