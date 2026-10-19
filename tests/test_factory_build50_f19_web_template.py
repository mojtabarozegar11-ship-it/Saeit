"""Actual F19 product acceptance tests; no simulated 50-stage green status."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

HERE=Path(__file__).resolve().parents[1]/'scripts'
def load(name,file):
    spec=importlib.util.spec_from_file_location(name,str(HERE/file))
    x=importlib.util.module_from_spec(spec);spec.loader.exec_module(x);return x
producer=load('f19_real_product_under_test','factory_build50_f19_web_template.py')
proto=load('f19_build50_genuine_protocol_under_test','factory_build_50.py')
reviewer=load('f19_independent_quality_under_test','factory_f19_independent_web_review.py')
class F19RealProduct(unittest.TestCase):
    def setUp(self):
        t=tempfile.TemporaryDirectory();self.addCleanup(t.cleanup)
        self.root=Path(t.name)
    def test_48_substantive_distinct_tasks(self):
        p=producer.plan(proto)
        tasks=proto.validate_plan(p)
        self.assertEqual(len(tasks),48)
        self.assertEqual(p['family_id'],'F19')
        self.assertEqual(len(set(x['id'] for x in tasks)),48)
        self.assertEqual(len(producer.HTML),12)
        self.assertEqual(len(producer.STYLES),12)
        self.assertEqual(len(producer.RESPONSIVE),12)
    def test_complete_real_build_private_zip_and_no_false_release(self):
        result=producer.build(self.root)
        self.assertEqual(result['status'],'technical_50_stage_build_completed',result)
        self.assertEqual(result['completed_stages'],50)
        self.assertFalse(result['commercial_release'])
        code=producer.PRODUCT
        stage=self.root/'build-50'/code
        state=proto.read(stage/'state.json')
        self.assertTrue(proto.verify_attempt(stage,state,producer.plan(proto)['source_snapshot_sha256']))
        self.assertEqual(len(list(Path(state['attempt_folder']).glob('??-work.json'))),48)
        stock=self.root/'digital-products'/code
        manifest=proto.read(stock/'manufacturing_manifest.json')
        self.assertFalse(manifest['owner_publication_approval'])
        self.assertFalse(manifest['public_listing_enabled'])
        self.assertFalse(manifest['independent_human_review'])
        data=stock/(code+'-internal-qa.zip')
        with zipfile.ZipFile(data) as archive:
            index=archive.read(code+'/index.html').decode()
            styles=archive.read(code+'/styles.css').decode()
            self.assertIn('href="#main"',index)
            self.assertIn('Northstar',index)
            self.assertNotIn('<script',index.lower())
            self.assertIn('prefers-reduced-motion',styles)
            self.assertIn('@media (max-width: 760px)',styles)
        audit=proto.audit(self.root)
        self.assertIn(code,[row['product_id'] for row in audit['products'] if row['build_50_verified']])
        self.assertEqual(producer.build(self.root)['status'],'unchanged_verified_technical_product')
        self.assertEqual(len(list(stage.glob('attempt-*'))),1)
    def test_independent_review_rejects_tampered_archive(self):
        result=producer.build(self.root)
        self.assertEqual(result['completed_stages'],50)
        stage=proto.read(self.root/'build-50'/producer.PRODUCT/'state.json')
        folder=Path(stage['attempt_folder'])
        archive=folder/(producer.PRODUCT+'-internal-qa.zip')
        archive.write_bytes(b'not a valid zip')
        with self.assertRaises((zipfile.BadZipFile,ValueError)):
            reviewer.check(folder,archive,producer.PRODUCT)
        current=proto.audit(self.root)
        self.assertEqual(current['verified_50_stage_builds'],0)
if __name__=='__main__':unittest.main()
