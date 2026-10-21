import importlib.util,tempfile,unittest
from pathlib import Path
BASE=Path(__file__).resolve().parents[1]/"scripts"
def get(n):
 sp=importlib.util.spec_from_file_location(n,str(BASE/(n+".py")))
 m=importlib.util.module_from_spec(sp);sp.loader.exec_module(m);return m
maker=get("factory_build50_f35_cad")
review=get("factory_f35_cad_independent_review")
proto=get("factory_build_50")
class F35ActualCad(unittest.TestCase):
 def test_exact_48_unique_work_contracts(self):
  tasks=proto.validate_plan(maker.plan(proto))
  self.assertEqual(len(tasks),48)
  self.assertEqual(len({t["id"] for t in tasks}),48)
 def test_independent_real_mesh_byte_parsers_and_topology(self):
  with tempfile.TemporaryDirectory() as temp:
   folder=Path(temp)
   tasks=maker.plan(proto)["work_packages"]
   maker.create(folder,tasks[0])
   result=review.one(folder,tasks[0]["id"])
   self.assertEqual(result["watertight_edges"],18)
   self.assertEqual(result["triangles"],12)
   (folder/(tasks[0]["id"]+".stl")).write_bytes(b"fake")
   with self.assertRaisesRegex(ValueError,"STL_TRIANGLE_COUNT"):
    review.one(folder,tasks[0]["id"])
 def test_full_real_48_mesh_50_stage_native_build_and_idempotent(self):
  import json,zipfile
  with tempfile.TemporaryDirectory() as temp:
   root=Path(temp)
   first=maker.build(root)
   self.assertEqual(first["status"],"technical_50_stage_build_completed")
   self.assertEqual(first["completed_stages"],50)
   product=root/"digital-products"/maker.PRODUCT
   manifest=json.loads((product/"manufacturing_manifest.json").read_text())
   self.assertEqual(manifest["family_id"],"F35")
   self.assertFalse(manifest["public_listing_enabled"])
   self.assertFalse(manifest["independent_human_review"])
   archive=product/(maker.PRODUCT+"-internal-qa.zip")
   with zipfile.ZipFile(archive) as z:
    self.assertEqual(len(z.namelist()),193)
    self.assertIsNone(z.testzip())
   again=maker.build(root)
   self.assertEqual(again["status"],"unchanged_verified_technical_product")
   self.assertEqual(maker.sha(archive),manifest["artifact_sha256"])
 def test_invalid_glb_cannot_be_sold(self):
  with tempfile.TemporaryDirectory() as temp:
   folder=Path(temp);task=maker.plan(proto)["work_packages"][1]
   maker.create(folder,task)
   (folder/(task["id"]+".glb")).write_bytes(b"x"*2000)
   with self.assertRaisesRegex(ValueError,"GLB_MAGIC"):
    review.one(folder,task["id"])
if __name__=="__main__":unittest.main()
