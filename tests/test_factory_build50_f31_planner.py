import importlib.util
from pathlib import Path
import tempfile
import unittest
import zipfile
import xml.etree.ElementTree as ET
SCRIPTS=Path(__file__).resolve().parents[1]/'scripts'
def load(name):
    spec=importlib.util.spec_from_file_location(name,str(SCRIPTS/(name+'.py')))
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
producer=load('factory_build50_f31_planner');review=load('factory_f31_independent_review');proto=load('factory_build_50')
class PlannerProduction(unittest.TestCase):
    def setUp(self):
        t=tempfile.TemporaryDirectory();self.addCleanup(t.cleanup);self.root=Path(t.name)
    def test_real_50_stages_archive_reuse_and_next_week(self):
        first=producer.build(self.root,'2026-10-19');self.assertEqual(first['completed_stages'],50)
        home=self.root/'build-50'/first['product_id'];state=proto.read(home/'state.json')
        self.assertTrue(proto.verify_attempt(home,state,state['source_snapshot_sha256']))
        with zipfile.ZipFile(self.root/'digital-products'/first['product_id']/(first['product_id']+'-internal-qa.zip')) as z:self.assertEqual(len(z.namelist()),50)
        self.assertEqual(producer.build(self.root,'2026-10-19')['status'],'unchanged_verified_technical_product')
        self.assertEqual(proto.read(home/'state.json')['attempt'],1)
        second=producer.build(self.root,'2026-10-26');self.assertNotEqual(first['product_id'],second['product_id'])
        self.assertFalse(second['commercial_release'])
    def test_corrupt_package_rebuilt_and_previous_evidence_retained(self):
        result=producer.build(self.root,'2026-10-19');p=self.root/'digital-products'/result['product_id']/(result['product_id']+'-internal-qa.zip')
        previous=p.read_bytes();p.write_bytes(b'corruption');self.assertEqual(producer.build(self.root,'2026-10-19')['status'],'technical_50_stage_build_completed')
        home=self.root/'build-50'/result['product_id'];self.assertEqual(proto.read(home/'state.json')['attempt'],2)
        self.assertTrue((home/'attempt-00000001').is_dir())
        self.assertEqual(p.read_bytes(),previous)
    def test_missing_fields_external_links_and_active_svg_rejected(self):
        result=producer.build(self.root,'2026-10-19');state=proto.read(self.root/'build-50'/result['product_id']/'state.json')
        folder=Path(state['attempt_folder']);archive=folder/(result['product_id']+'-internal-qa.zip')
        for name,needle,replacement in [('priorities_accessible.html','for="field0"','for="missing"'),('index.html','href="priorities_accessible.html"','href="https://example.org"'),('risks_blank.svg','<rect','<script')]:
            p=folder/name;original=p.read_text();p.write_text(original.replace(needle,replacement,1))
            with self.assertRaises((ValueError,ET.ParseError)):review.check(folder,archive,result['product_id'],'2026-10-19')
            p.write_text(original)
    def test_strict_warehouse_accepts_real_build50_output(self):
        result=producer.build(self.root,'2026-10-19')
        warehouse=load('factory_production_warehouse')
        stocked=warehouse.cycle(self.root,strict_build50=True)
        self.assertEqual(stocked['stocked'],1)
        saved=proto.read(self.root/'production-warehouse'/'stock-register.json')
        self.assertEqual(saved['records'][0]['family_id'],'F31')
    def test_date_and_symlink_rejected(self):
        with self.assertRaises(ValueError):producer.build(self.root,'2026-10-20')
        other=self.root/'alias';other.symlink_to(self.root,target_is_directory=True)
        with self.assertRaises(ValueError):producer.build(other,'2026-10-19')
if __name__=='__main__':unittest.main()
