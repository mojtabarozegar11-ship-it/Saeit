"""Exercise real F34 vector icon production end-to-end without payment or store."""
import importlib.util
from pathlib import Path
import tempfile
import unittest
import zipfile

HERE=Path(__file__).resolve().parents[1]/'scripts'
def load(name,path):
    spec=importlib.util.spec_from_file_location(name,str(HERE/path))
    x=importlib.util.module_from_spec(spec);spec.loader.exec_module(x);return x
producer=load('real_f34_under_test','factory_build50_f34_icon_kit.py')
reviewer=load('real_f34_review_under_test','factory_f34_independent_icon_review.py')
proto=load('real_f34_protocol_under_test','factory_build_50.py')
class F34RealArtwork(unittest.TestCase):
    def setUp(self):
        t=tempfile.TemporaryDirectory();self.addCleanup(t.cleanup)
        self.root=Path(t.name)
    def test_distinct_forty_eight_original_icons_planned(self):
        plan=producer.spec(proto)
        self.assertEqual(len(proto.validate_plan(plan)),48)
        self.assertEqual(len(set(x['id'] for x in plan['work_packages'])),48)
        self.assertEqual(plan['family_id'],'F34')
        self.assertEqual(len(producer.CONCEPTS),12)
    def test_fifty_stages_produce_readable_original_icon_kit(self):
        done=producer.build(self.root)
        self.assertEqual(done['status'],'technical_50_stage_build_completed',done)
        self.assertEqual(done['completed_stages'],50)
        self.assertEqual(done['icons'],48)
        self.assertFalse(done['commercial_release'])
        home=self.root/'build-50'/producer.PRODUCT
        state=proto.read(home/'state.json')
        self.assertTrue(proto.verify_attempt(home,state,producer.spec(proto)['source_snapshot_sha256']))
        folder=Path(state['attempt_folder'])
        self.assertEqual(len(list(folder.glob('??-work.json'))),48)
        result=reviewer.review(folder,producer.PRODUCT)
        self.assertTrue(all(result['gates'].values()))
        manifest=proto.read(self.root/'digital-products'/producer.PRODUCT/'manufacturing_manifest.json')
        self.assertFalse(manifest['public_listing_enabled'])
        self.assertFalse(manifest['owner_publication_approval'])
        arc=self.root/'digital-products'/producer.PRODUCT/(producer.PRODUCT+'-internal-qa.zip')
        with zipfile.ZipFile(arc) as z:
            self.assertEqual(len(z.namelist()),100)
            self.assertIn(producer.PRODUCT+'/sprout_outline.svg',z.namelist())
            self.assertIn(producer.PRODUCT+'/compass_dual.png',z.namelist())
        self.assertEqual(producer.build(self.root)['status'],'unchanged_verified_technical_product')
        self.assertEqual(len(list(home.glob('attempt-*'))),1)
    def test_independent_checker_rejects_tampered_icon(self):
        result=producer.build(self.root)
        self.assertEqual(result['completed_stages'],50)
        state=proto.read(self.root/'build-50'/producer.PRODUCT/'state.json')
        folder=Path(state['attempt_folder'])
        (folder/'sprout_outline.svg').write_text('<script>alert(1)</script>')
        with self.assertRaises(ValueError):
            reviewer.review(folder,producer.PRODUCT)
        self.assertEqual(proto.audit(self.root)['verified_50_stage_builds'],0)
if __name__=='__main__':unittest.main()
