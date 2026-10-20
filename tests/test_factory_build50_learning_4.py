import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
SCRIPTS=Path(__file__).resolve().parents[1]/"scripts"
def module(name):
    spec=importlib.util.spec_from_file_location(name,str(SCRIPTS/(name+".py")))
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
maker=module("factory_build50_learning_4")
proto=module("factory_build_50")
review=module("factory_learning_independent_review")
@unittest.skipUnless(all(importlib.util.find_spec(x) is not None for x in ("reportlab","docx")),
                    "isolated factory job installs pinned reportlab and docx")
class FourLearningLines(unittest.TestCase):
    def test_real_four_family_private_build_and_replay(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            for family,product in maker.FAMILIES.items():
                plan=maker.plan(proto,family)
                self.assertEqual(len(proto.validate_plan(plan)),48)
                built=maker.build(root,family)
                self.assertEqual(built["status"],"technical_50_stage_build_completed",built)
                home=root/"build-50"/product;state=proto.read(home/"state.json")
                self.assertTrue(proto.verify_attempt(home,state,plan["source_snapshot_sha256"]))
                attempt=Path(state["attempt_folder"])
                self.assertTrue(review.check(attempt,attempt/(product+"-internal-qa.zip"),product,family)["passed"])
                self.assertEqual(maker.build(root,family)["status"],"unchanged_verified_technical_product")
                manifest=proto.read(root/"digital-products"/product/"manufacturing_manifest.json")
                self.assertFalse(manifest["public_listing_enabled"])
                self.assertFalse(manifest["owner_publication_approval"])
    def test_independent_math_and_archive_tamper_rejection(self):
        self.assertEqual(review.answer({"a":12,"b":3,"operator":"//"}),4)
        with self.assertRaises(ValueError):review.answer({"a":11,"b":3,"operator":"//"})
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);family="F10";product=maker.FAMILIES[family]
            made=maker.build(root,family)
            self.assertEqual(made["status"],"technical_50_stage_build_completed",made)
            home=root/"build-50"/product;state=proto.read(home/"state.json")
            attempt=Path(state["attempt_folder"])
            file=attempt/"backup_foundation.json"
            data=json.loads(file.read_text());data["questions"][0]["answer"]+=999
            file.write_text(json.dumps(data))
            self.assertFalse(proto.verify_attempt(home,state,state["source_snapshot_sha256"]))
            with self.assertRaises(ValueError):
                review.check(attempt,attempt/(product+"-internal-qa.zip"),product,family)
if __name__=="__main__":unittest.main()
