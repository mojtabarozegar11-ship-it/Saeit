"""Tests for privately repairing available buyer packages without sale approval."""
import tempfile,unittest,json
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
 def test_no_human_approvals_in_outcome(self):
  with tempfile.TemporaryDirectory() as t:
   root=Path(t)
   (root/"design-intake/mojplaywin-stage1-quality-returns").mkdir(parents=True)
   v=worker.run(root,max_new=0)
   self.assertFalse(v["site_sales_enabled"])
   self.assertTrue(v["no_cross_tenant_modification"])
if __name__=="__main__":unittest.main()
