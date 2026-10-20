"""Real private 40-family intake, guarded receipts, adversarial negatives."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
BASE=Path(__file__).resolve().parents[1]
src=BASE/"scripts/factory_all40_private_activation.py"
spec=importlib.util.spec_from_file_location("all40",str(src))
a=importlib.util.module_from_spec(spec);spec.loader.exec_module(a)
def fake_offers(root,ready=28):
    dest=root/"commercial40/offers"
    dest.mkdir(parents=True)
    for n in range(1,41):
        fid="F%02d"%n
        row={"family_id":fid,"offer_status":"commercial_preparation_private_only",
          "public_sale_allowed":False,"payment_enabled":False,"published":False,
          "technical_products_with_verified_archive":1 if n<=ready else 0,
          "commercial_blockers":["LICENSE_REVIEW_PENDING","CHECKOUT_TEST_UNPROVEN"]}
        (dest/(fid+".json")).write_text(json.dumps(row),encoding="utf8")
def request(ident,fid):
    return {"schema":a.REQUEST_SCHEMA,"request_id":ident,"family_id":fid,
       "intent":"custom_specification","title":"Original verified test technical brief",
       "specification":"Design a specific bounded example and document exact evidence and test results."}
class ActualAll40Activation(unittest.TestCase):
    def test_all_forty_are_real_active_private_intake_not_fake_sold(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);fake_offers(root)
            result=a.tick(root)
            self.assertEqual(result["report"]["families_available_for_private_intake"],40)
            self.assertEqual(result["report"]["technical_product_families"],28)
            self.assertEqual(result["report"]["families_needing_a_native_maker"],12)
            self.assertEqual(result["report"]["synthetic_local_route_probes_verified"],40)
            self.assertTrue(all(x["operational_intake_enabled"] for x in result["report"]["families"]))
            self.assertTrue(all(not x["commercial_sales_enabled"] for x in result["report"]["families"]))
            self.assertEqual(len({x["family_id"] for x in result["report"]["families"]}),40)
            self.assertEqual((root/"activation40/dashboard.json").stat().st_mode & 0o777,0o600)
            self.assertEqual(result["queued_requests_accepted"],0)
    def test_real_queue_receipts_and_distinct_lane_on_same_runtime(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);fake_offers(root)
            incoming=root/"activation40/requests";incoming.mkdir(parents=True)
            for fid in ("F01","F40","F29","F30"):
                ident="ticket_%s_2026"%fid
                (incoming/(ident+".json")).write_text(json.dumps(request(ident,fid)),encoding="utf8")
            first=a.tick(root)
            second=a.tick(root)
            self.assertEqual(first["queued_requests_accepted"],3)
            self.assertEqual(second["queued_requests_accepted"],1)
            self.assertEqual(len(list((root/"activation40/tasks").glob("*.json"))),4)
            for fid in ("F01","F40","F29","F30"):
                ident="ticket_%s_2026"%fid
                data=a.read(root/"activation40/tasks"/(ident+".json"))
                self.assertFalse(data["payment_created"])
                self.assertFalse(data["commercial_release_authorized"])
                self.assertEqual(data["status"],"queued_for_specialist_review")
                expected="product_admission_review" if fid in ("F01",) else "native_builder_gap_engineering"
                self.assertEqual(data["dispatch_lane"],expected)
                receipt=a.read(root/"activation40/receipts"/(ident+".json"))
                self.assertTrue(receipt["task_sha256"])
                self.assertFalse(receipt["public_sale_allowed"])
                self.assertEqual(receipt["task_sha256"],a.digest(data))
    def test_invalid_request_is_rejected_no_sale(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);fake_offers(root)
            path=root/"activation40/requests/bad_042026.json"
            path.parent.mkdir(parents=True)
            bad=request("bad_042026","F01")
            bad["payment_permission"]=True
            path.write_text(json.dumps(bad))
            outcome=a.tick(root)
            self.assertEqual(outcome["queued_requests_rejected"],1)
            self.assertEqual(outcome["queued_requests_accepted"],0)
            self.assertEqual(len(list((root/"activation40/tasks").glob("*.json"))),0)
            self.assertTrue((root/"activation40/rejected/bad_042026.reject.json").is_file())
    def test_offer_with_public_sale_claim_fails_closed(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);fake_offers(root)
            file=root/"commercial40/offers/F31.json";offer=json.loads(file.read_text())
            offer["payment_enabled"]=True;file.write_text(json.dumps(offer))
            with self.assertRaisesRegex(ValueError,"UNVERIFIED_SALES_FLAG"):
                a.tick(root)
    def test_queue_idempotency_must_not_repeat_work(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);fake_offers(root)
            path=root/"activation40/requests/ticket_repeat1.json"
            path.parent.mkdir(parents=True)
            path.write_text(json.dumps(request("ticket_repeat1","F24")))
            self.assertEqual(a.tick(root)["queued_requests_accepted"],1)
            path.write_text(json.dumps(request("ticket_repeat1","F24")))
            second=a.tick(root)
            self.assertEqual(second["queued_requests_accepted"],0)
            self.assertEqual(second["queued_requests_rejected"],1)
            self.assertEqual(len(list((root/"activation40/tasks").glob("*.json"))),1)
if __name__=="__main__":unittest.main()
