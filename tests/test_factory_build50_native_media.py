import importlib.util
import shutil
import tempfile
import unittest
from pathlib import Path
HERE=Path(__file__).resolve().parents[1]/"scripts"
def load(name):
    s=importlib.util.spec_from_file_location(name,str(HERE/(name+".py")))
    m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
maker=load("factory_build50_native_media")
proto=load("factory_build_50")
review=load("factory_native_media_review")

@unittest.skipUnless(shutil.which("ffmpeg") and importlib.util.find_spec("PIL"),
                     "Requires actual ffmpeg and Pillow for media end-to-end tests")
class NativeMedia(unittest.TestCase):
    def test_three_real_media_manufacturing_lines(self):
        ffmpeg=Path(shutil.which("ffmpeg"))
        for family,product in maker.FAMILIES.items():
            with self.subTest(family=family),tempfile.TemporaryDirectory() as temp:
                root=Path(temp)
                plan=maker.plan(proto,family,ffmpeg)
                self.assertEqual(len(proto.validate_plan(plan)),48)
                built=maker.build(root,family,ffmpeg)
                self.assertEqual(built["status"],"technical_50_stage_build_completed",built)
                home=root/"build-50"/product
                state=proto.read(home/"state.json")
                self.assertTrue(proto.verify_attempt(home,state,plan["source_snapshot_sha256"]))
                folder=Path(state["attempt_folder"]);zipname=product+"-internal-qa.zip"
                self.assertTrue(review.check(folder,folder/zipname,product,family,ffmpeg)["passed"])
                self.assertEqual(maker.build(root,family,ffmpeg)["status"],
                                 "unchanged_verified_technical_product")
                manifest=proto.read(root/"digital-products"/product/"manufacturing_manifest.json")
                self.assertFalse(manifest["public_listing_enabled"])
                self.assertFalse(manifest["owner_publication_approval"])
    def test_tamper_and_forged_receipt_rejected(self):
        ffmpeg=Path(shutil.which("ffmpeg"))
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);family="F39";product=maker.FAMILIES[family]
            built=maker.build(root,family,ffmpeg)
            self.assertEqual(built["status"],"technical_50_stage_build_completed",built)
            home=root/"build-50"/product
            state=proto.read(home/"state.json")
            folder=Path(state["attempt_folder"])
            output=folder/"dunes_subtle.wav";output.write_bytes(b"forged")
            self.assertFalse(proto.verify_attempt(home,state,state["source_snapshot_sha256"]))
            with self.assertRaises((ValueError,EOFError,RuntimeError)):
                review.check(folder,folder/(product+"-internal-qa.zip"),product,family,ffmpeg)
if __name__=="__main__":unittest.main()
