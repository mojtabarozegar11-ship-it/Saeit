import importlib.util
from pathlib import Path
import tempfile
import unittest

SCRIPTS=Path(__file__).resolve().parents[1]/"scripts"
def load(name):
    spec=importlib.util.spec_from_file_location(name,str(SCRIPTS/(name+".py")))
    obj=importlib.util.module_from_spec(spec);spec.loader.exec_module(obj);return obj
maker=load("factory_build50_creative_kits")
proto=load("factory_build_50")
reviewer=load("factory_creative_independent_review")

@unittest.skipUnless(all(importlib.util.find_spec(name) is not None for name in ('docx','pptx','PIL')), 'Office and image test dependencies are verified in isolated factory workflow')
class CreativeKits(unittest.TestCase):
    def test_all_three_real_50_stage_products_and_replay(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            for fid,product in maker.PRODUCTS.items():
                plan=maker.tasks(proto,fid)
                self.assertEqual(len(proto.validate_plan(plan)),48)
                made=maker.build(root,fid)
                self.assertEqual(made["status"],"technical_50_stage_build_completed",made)
                home=root/"build-50"/product
                state=proto.read(home/"state.json")
                self.assertTrue(proto.verify_attempt(home,state,plan["source_snapshot_sha256"]))
                source=Path(state["attempt_folder"])
                archive=source/(product+"-internal-qa.zip")
                self.assertTrue(reviewer.check(source,archive,product,fid)["passed"])
                self.assertEqual(maker.build(root,fid)["status"],"unchanged_verified_technical_product")
                manifest=proto.read(root/"digital-products"/product/"manufacturing_manifest.json")
                self.assertFalse(manifest["public_listing_enabled"])
                self.assertFalse(manifest["independent_human_review"])
    def test_tampered_deliverable_is_not_accepted(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);fid="F33";product=maker.PRODUCTS[fid]
            maker.build(root,fid)
            home=root/"build-50"/product
            state=proto.read(home/"state.json")
            asset=Path(state["attempt_folder"])/"project_scope_brief.svg"
            asset.write_text("broken")
            self.assertFalse(proto.verify_attempt(home,state,state["source_snapshot_sha256"]))
            self.assertEqual(maker.build(root,fid)["status"],"technical_50_stage_build_completed")
if __name__=="__main__":unittest.main()
