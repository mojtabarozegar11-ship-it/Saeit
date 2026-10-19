"""Do not confuse BUILD50 receipts or family pilot files with product sales."""
import importlib.util
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
def load(name,filename):
    spec=importlib.util.spec_from_file_location(name,str(ROOT/'scripts'/filename))
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    return m
bridge=load('factory_40_build50_bridge_tests','factory_build50_family_bridge.py')
protocol=load('factory_build50_protocol_tests','factory_build_50.py')
master=load('factory_master_40_tests','factory_40_family_master.py')
REGISTRY=ROOT/'factory_config/forty_families.json'

class FamilyBridgeTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root=Path(temp.name)
    def execute(self):
        return bridge.inventory(self.root,REGISTRY,protocol,master)
    def test_all_forty_families_have_explicit_contract_without_fake_production(self):
        status=self.execute()
        self.assertEqual(status['counts']['registered_families'],40)
        self.assertEqual(status['counts']['families_without_verified_50_stage_executor'],39)
        self.assertEqual(status['counts']['technical_products_with_verified_50_stages'],0)
        self.assertEqual(status['counts']['commercially_approved_and_published_products'],0)
        self.assertEqual(len(status['families']),40)
        self.assertTrue(all(p['required_stages']==50 and p['worker_packages_required']==48 for p in status['families']))
        self.assertFalse(status['commercial_release_allowed'])
    def test_valid_family_pilot_is_technical_not_finished_50_stage_product(self):
        p=self.root/'family-pilots/F14'/('a'*20)
        p.mkdir(parents=True)
        artifact=p/'game.js'
        artifact.write_bytes(b'function start(){return 1;}'*40)
        (p/'technical-receipt.json').write_text(json.dumps({
            'family':'F14','source_key':'a'*20,'technical_quality_passed':True,
            'commercial_release':False,'files':{'game.js':bridge.digest(artifact)}}))
        result=self.execute()
        f=result['families'][13]
        self.assertEqual(f['technical_pilot_count'],1)
        self.assertEqual(f['technical_50_stage_completed'],0)
        self.assertEqual(result['counts']['families_without_verified_50_stage_executor'],39)
        artifact.write_bytes(b'tampered')
        self.assertEqual(self.execute()['families'][13]['technical_pilot_count'],0)
    def test_true_verified_fifty_stage_attempt_is_counted_with_its_family(self):
        topics=('input_validation','output_units','rounding_precision','error_boundaries',
                'dependency_resolution','accessibility_notes','formula_correctness','security_limits',
                'data_integrity','performance_limits','compatibility_matrix','user_workflow')
        actions=('Specify real conditions for','Create distinct evidence for',
                 'Verify negative scenarios for','Document tested limitations for')
        plan={'schema':protocol.SCHEMA,'product_id':'sampleF27','family_id':'F27',
              'producer_id':'workbook_producer','source_snapshot_sha256':'c'*64,
              'work_packages':[{'id':'real_%02d'%i,
                'instruction':actions[i%4]+' '+topics[i//4]+' using nonreused files and measurable acceptance proofs.',
                'acceptance':['Real file matches tested expected behavior','Failure case is checked']}
                for i in range(48)]}
        def worker(task,context):
            out='actual_%02d.txt'%context['stage']
            (Path(context['folder'])/out).write_text(task['instruction'])
            return {'passed':True,'outputs':[out],'successful_checks':2}
        def assembler(plan,context):
            (Path(context['folder'])/'full_artifact.txt').write_text('Standalone technical package')
            return {'passed':True,'outputs':['full_artifact.txt'],'successful_checks':1}
        def reviewer(plan,context):
            (Path(context['folder'])/'independent-review.txt').write_text('Independent check: simulated fixture')
            return {'passed':True,'reviewer_id':'independent_test_fixture','critical_defects':[],
                    'gates':dict.fromkeys(protocol.GATES,True),
                    'outputs':['independent-review.txt'],'successful_checks':10}
        state=protocol.run_attempt(self.root,plan,worker,assembler,reviewer)
        self.assertEqual(state['completed_stages'],50)
        report=self.execute()
        self.assertEqual(report['counts']['technical_products_with_verified_50_stages'],1)
        self.assertEqual(report['families'][26]['technical_50_stage_completed'],1)
        self.assertEqual(report['counts']['commercially_approved_and_published_products'],0)
        (Path(state['attempt_folder'])/'actual_02.txt').write_text('damaged')
        bad=self.execute()
        self.assertEqual(bad['counts']['technical_products_with_verified_50_stages'],0)
        self.assertEqual(bad['products'][0]['status'],'corrupt_50_stage_proof')
    def test_forged_completion_and_outside_path_do_not_count(self):
        p=self.root/'build-50/sampleF04'
        p.mkdir(parents=True)
        (p/'state.json').write_text(json.dumps({'status':'awaiting_owner_acceptance',
                             'completed_stages':50,'attempt':1,'source_snapshot_sha256':'d'*64}))
        result=self.execute()
        self.assertEqual(result['counts']['technical_products_with_verified_50_stages'],0)
        self.assertIn(result['products'][0]['status'],
                      ('invalid_attempt_directory','invalid_50_stage_proof'))
        with self.assertRaises(RuntimeError):
            bridge.main.__name__ if False else bridge.inventory(self.root/'missing',REGISTRY,protocol,master)
if __name__=='__main__':unittest.main()
