"""Tests for privately repairing available buyer packages without sale approval."""
import tempfile,unittest,json
from datetime import datetime,timezone
from unittest import mock
from pathlib import Path
from scripts import mpw_factory_stage1_technical_repair as worker
from scripts import mpw_vps_warehouse_courier as courier
class Stage1Test(unittest.TestCase):
 def test_empty_queue(self):
  with tempfile.TemporaryDirectory() as t:
   root=Path(t)
   (root/"design-intake/mojplaywin-stage1-quality-returns").mkdir(parents=True)
   v=worker.run(root,max_new=0)
   self.assertEqual(v["returned_products_inspected"],0)
   self.assertEqual(v["commercially_approved_returns"],0)
   self.assertEqual(v["stage1_returns_remaining_open"],0)
   self.assertEqual(v["source_product_rebuilds_verified"],0)
   self.assertEqual(v["public_store_products_modified"],0)
   self.assertEqual(v["new_native_private_previews_statically_validated"],0)
 def test_invalid_return_does_not_exhaust_new_package_budget(self):
  with tempfile.TemporaryDirectory() as t:
   root=Path(t)
   row_bad={"product_id":"bad","source_sha256":"wrong"}
   row_ok={"product_id":"valid_product","source_sha256":"a"*64}
   entries=[(Path("bad.json"),row_bad),(Path("valid.json"),row_ok)]
   attempted=[]
   def fake_once(root,courier,packager,native,filename,row,do_pack):
    attempted.append(do_pack)
    return {
     "product_id":row["product_id"],"source_sha256":row["source_sha256"],
     "technical_zip_integrity_passed":False,
     "new_customer_bundle_rebuilt":False,
     "new_native_private_preview_created":False,
     "consumer_bundle_status":"held_for_rework",
     "consumer_package_sha256":None,
     "blocking_reason":"REPAIR_MOCK_BLOCKED"
    }
   # Freeze the rotation bucket so the intentionally bad receipt is first.
   # A successful repair attempt must not be consumed by this unrelated blocker.
   with mock.patch.object(worker,"stage1",return_value=entries),mock.patch.object(worker,"once",side_effect=fake_once),mock.patch.object(worker,"datetime") as clock:
    clock.now.return_value=datetime(2026,10,20,0,0,tzinfo=timezone.utc)
    report=worker.run(root,max_new=1)
   self.assertEqual(attempted,[False,True])
   self.assertEqual(report["technical_package_attempts_consumed"],1)
   self.assertEqual(report["commercially_approved_returns"],0)

 def test_bad_budget(self):
  with tempfile.TemporaryDirectory() as t:
   with self.assertRaises(ValueError):
    worker.run(t,max_new=44)
 def test_installer_reserves_256_mib_in_kib_and_reports_failure_stage(self):
  script=(Path(__file__).resolve().parents[1]/"deploy"/"install_mpw_stage1_technical_repair.sh").read_text()
  self.assertIn('df -Pk "$root"',script)
  self.assertIn('test "$free_kib" -lt 262144',script)
  self.assertNotIn('df -Pm "$root"',script)
  self.assertIn('MPW_STAGE1_INSTALL_FAILURE_STAGE=',script)
  self.assertIn("factory_personal_owner_passport_policy_20261020.py",script)
 def test_courier_stages_personal_rights_passport_code(self):
  wf=(Path(__file__).resolve().parents[1]/".github/workflows/mpw-factory-execute-stage1-repairs-20261020.yml").read_text()
  self.assertIn("scripts/factory_personal_owner_passport_policy_20261020.py scripts/mpw_factory_stage1_deep_evidence.py",wf)
  self.assertIn("needs: preflight",wf)
  self.assertIn("github.ref == 'refs/heads/main'",wf)
 def test_no_human_approvals_in_outcome(self):
  with tempfile.TemporaryDirectory() as t:
   root=Path(t)
   (root/"design-intake/mojplaywin-stage1-quality-returns").mkdir(parents=True)
   v=worker.run(root,max_new=0)
   self.assertFalse(v["site_sales_enabled"])
   self.assertTrue(v["no_cross_tenant_modification"])
if __name__=="__main__":unittest.main()
