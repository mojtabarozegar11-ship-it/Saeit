import importlib.util
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch
BASE=Path(__file__).resolve().parents[1];SCRIPTS=BASE/'scripts';REGISTRY=BASE/'factory_config/forty_families.json'
def load(name):
    s=importlib.util.spec_from_file_location(name,str(SCRIPTS/(name+'.py')));m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
builder=load('factory_build50_f18_webapps');planner=load('factory_product_planner');warehouse=load('factory_production_warehouse');organizer=load('factory_capability_organizer')
class F18AndOrganization(unittest.TestCase):
    def setUp(self):
        t=tempfile.TemporaryDirectory();self.addCleanup(t.cleanup);self.root=Path(t.name);self.ops=self.root/'ops';self.ops.mkdir()
    def test_real_web_apps_independent_http_and_strict_stock(self):
        r=builder.build(self.root);self.assertEqual(r['completed_stages'],50)
        proof=planner.proof(self.root,builder.PRODUCT,'F18',load('factory_build_50'));self.assertEqual(proof['verified_manufacturing_receipts'],50)
        self.assertEqual(builder.build(self.root)['status'],'unchanged_verified_technical_product')
        stock=warehouse.cycle(self.root,strict_build50=True);self.assertEqual(stock['stocked'],1)
        receipt=planner.read(self.root/'digital-products'/builder.PRODUCT/'manufacturing_manifest.json')
        self.assertEqual(receipt['qa_measurements']['applications_http_tested'],12)
        self.assertFalse(receipt['qa_measurements']['human_browser_review'])
    def test_all_families_get_actual_support_calls_and_legacy_is_not_workers(self):
        wb=load('factory_1000_workbench');cat=wb.catalog(json.loads(REGISTRY.read_text()))
        area=self.root/'production-toolkit';area.mkdir();(area/'catalog.json').write_text(json.dumps(cat))
        target=self.ops/'production-workbench-1000';target.mkdir();shutil.copyfile(SCRIPTS/'factory_1000_workbench.py',target/'runner.py')
        (area/'verification.json').write_text(json.dumps({'runtime_sha256':organizer.hashfile(target/'runner.py'),'catalog_sha256':organizer.hashfile(area/'catalog.json'),'synthetic_test_invocations_passed':1000}))
        with patch.object(organizer,'toolchain',return_value={'state':'test_missing_engines','engines':{}}):
            r=organizer.run(self.root,REGISTRY,self.ops,BASE)
        self.assertEqual(r['family_count'],40);self.assertEqual(r['real_family_support_invocations_this_cycle'],200)
        self.assertEqual(r['support_tool_bindings_available'],1000);self.assertEqual(r['unique_support_operations'],25)
        self.assertEqual(r['legacy']['matching_modules'],77);self.assertEqual(r['separate_agents_started'],0)
        self.assertFalse(r['candidate_engines_are_complete_builders']);self.assertFalse(r['commercial_release'])
        self.assertTrue(all(not x['custom_product_generation_proven'] for x in r['families']))
    def test_workbench_tampering_is_detected_without_stopping_discovery(self):
        area=self.root/'production-toolkit';area.mkdir();(area/'catalog.json').write_text('{}');(area/'verification.json').write_text('{}')
        with patch.object(organizer,'toolchain',return_value={'state':'unavailable','engines':{}}):r=organizer.run(self.root,REGISTRY,self.ops,BASE)
        self.assertEqual(r['real_family_support_invocations_this_cycle'],0);self.assertEqual(len(r['families']),40)
    def test_forged_export_rebuilt_from_verified_inputs(self):
        builder.build(self.root);folder=self.root/'digital-products'/builder.PRODUCT;arc=folder/(builder.PRODUCT+'-internal-qa.zip');original=arc.read_bytes();arc.write_bytes(b'bad')
        m=planner.read(folder/'manufacturing_manifest.json');m['artifact_sha256']=organizer.hashfile(arc);(folder/'manufacturing_manifest.json').write_text(json.dumps(m))
        self.assertEqual(builder.build(self.root)['status'],'technical_50_stage_build_completed');self.assertEqual(arc.read_bytes(),original)
if __name__=='__main__':unittest.main()
