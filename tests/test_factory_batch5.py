import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import zipfile

SCRIPTS=Path(__file__).resolve().parents[1]/'scripts'
def load(name):
    spec=importlib.util.spec_from_file_location(name,str(SCRIPTS/(name+'.py')))
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
build=load('factory_batch5_build');specs=load('factory_batch5_specs');proto=load('factory_build_50');warehouse=load('factory_production_warehouse');review=load('factory_batch5_review')

class FiveFamilyProduction(unittest.TestCase):
    def setUp(self):
        t=tempfile.TemporaryDirectory();self.addCleanup(t.cleanup);self.root=Path(t.name)
    def test_five_real_products_fifty_receipts_and_strict_warehouse(self):
        for family in specs.FAMILIES:
            with self.subTest(family=family):
                result=build.build(self.root,family)
                self.assertEqual(result['completed_stages'],50)
                home=self.root/'build-50'/result['product_id'];state=proto.read(home/'state.json')
                self.assertTrue(proto.verify_attempt(home,state,state['source_snapshot_sha256']))
                folder=Path(state['attempt_folder'])
                with zipfile.ZipFile(folder/(result['product_id']+'-internal-qa.zip')) as z:self.assertEqual(len(z.namelist()),51)
                self.assertEqual(build.build(self.root,family)['status'],'unchanged_verified_technical_product')
                self.assertEqual(proto.read(home/'state.json')['attempt'],1)
                for p in folder.glob('*_test.py'):
                    command=subprocess.run([sys.executable,'-B',str(p)],capture_output=True,text=True,timeout=5)
                    self.assertEqual(command.returncode,0,command.stderr)
                keys=[r[0] for r in (specs.FIXTURES if family=='F25' else specs.SPECS[family])]
                input_file=self.root/'input.json'
                if family!='F25':input_file.write_text(json.dumps(specs.SPECS[family][0][3]))
                command=[sys.executable,'-B',str(folder/'run_tool.py'),keys[0]]
                if family!='F25':command+=['--input',str(input_file)]
                proc=subprocess.run(command,capture_output=True,text=True,timeout=5)
                self.assertEqual(proc.returncode,0,proc.stderr);json.loads(proc.stdout)
                bad=subprocess.run([sys.executable,'-B',str(folder/'run_tool.py'),'../outside'],capture_output=True,text=True,timeout=5)
                self.assertNotEqual(bad.returncode,0)
        stock=warehouse.cycle(self.root,strict_build50=True)
        self.assertEqual(stock['stocked'],5)
        saved=proto.read(self.root/'production-warehouse'/'stock-register.json')
        self.assertEqual({r['family_id'] for r in saved['records']},set(specs.FAMILIES))
        self.assertTrue(all(not r['commercial_release'] for r in saved['records']))
    def test_archive_corruption_rebuild_is_deterministic(self):
        r=build.build(self.root,'F20');p=self.root/'digital-products'/r['product_id']/(r['product_id']+'-internal-qa.zip')
        original=p.read_bytes();p.write_bytes(b'broken')
        self.assertEqual(build.build(self.root,'F20')['status'],'technical_50_stage_build_completed')
        self.assertEqual(p.read_bytes(),original)
    def test_independent_reviewer_rejects_wrong_function_and_forged_labels(self):
        for family in ('F20','F25','F28'):
            r=build.build(self.root,family);home=self.root/'build-50'/r['product_id'];state=proto.read(home/'state.json');folder=Path(state['attempt_folder'])
            keys=[row[0] for row in (specs.FIXTURES if family=='F25' else specs.SPECS[family])]
            if family=='F25':
                p=folder/(keys[0]+'.json');rows=json.loads(p.read_text());rows[0]['expected_valid']=False;p.write_text(json.dumps(rows))
            else:(folder/(keys[0]+'.py')).write_text('def run(v):\n    return None\n')
            with self.assertRaises(ValueError):review.check(folder,folder/(r['product_id']+'-internal-qa.zip'),r['product_id'],family,keys)
    def test_record_pipeline_does_not_mutate_input(self):
        r=build.build(self.root,'F22');state=proto.read(self.root/'build-50'/r['product_id']/'state.json');folder=Path(state['attempt_folder'])
        p=self.root/'input.json';text='[{"email":" A@EXAMPLE.ORG ","name":" Ada ","id":1}]';p.write_text(text)
        proc=subprocess.run([sys.executable,'-B',str(folder/'run_tool.py'),'normalize_email','trim_names','public_fields','--input',str(p)],capture_output=True,text=True,timeout=5)
        self.assertEqual(proc.returncode,0,proc.stderr);self.assertEqual(json.loads(proc.stdout),[{'id':1,'name':'Ada'}]);self.assertEqual(p.read_text(),text)
    def test_symlink_and_unknown_family_fail_closed(self):
        alias=self.root/'alias';alias.symlink_to(self.root,target_is_directory=True)
        with self.assertRaises(ValueError):build.build(alias,'F20')
        with self.assertRaises(ValueError):build.build(self.root,'F99')

if __name__=='__main__':unittest.main()
