import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
SCRIPTS=Path(__file__).resolve().parents[1]/'scripts';REGISTRY=SCRIPTS.parent/'factory_config/forty_families.json'
def load(name):
    spec=importlib.util.spec_from_file_location(name,str(SCRIPTS/(name+'.py')));m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
planner=load('factory_product_planner');proto=load('factory_build_50')
CAP={'memory_available_mb':4096,'disk_free_mb':10000,'cpu_count':2,'load_average':0}
class ProductPlanner(unittest.TestCase):
    def setUp(self):
        t=tempfile.TemporaryDirectory();self.addCleanup(t.cleanup);self.root=Path(t.name)
        self.profiles={x['id']:x for x in json.loads(REGISTRY.read_text())['profiles']}
    def test_all_forty_routes_plan_real_unexecuted_tasks(self):
        r=planner.cycle(self.root,REGISTRY)
        self.assertEqual(r['registered_family_routes'],40);self.assertEqual(r['unique_product_plans'],40)
        self.assertEqual(len(r['families_awaiting_specialist_executor']),23)
        self.assertEqual(r['custom_product_executors_verified'],0)
        for path in (self.root/'product-planning/plans').glob('*.json'):
            p=planner.read(path);self.assertEqual(len(p['work_packages']),48)
            self.assertEqual(len({t['instruction'] for t in p['work_packages']}),48)
            self.assertEqual(p['completed_planned_work_packages'],0)
            self.assertTrue(all(t['status']=='not_executed' and t['evidence']==[] for t in p['work_packages']))
    def test_custom_objective_cannot_be_replaced_by_catalog_kit(self):
        bad={'schema':planner.SCHEMA,'kind':'catalog','family_id':'F20','recipe':planner.CATALOG['F20'],'objective':'Build a different plugin'}
        with self.assertRaises(ValueError):planner.request(bad,self.profiles)
        custom={'schema':planner.SCHEMA,'kind':'custom','family_id':'F20','objective':'Build a custom database validation plugin',
          'requirements':['Support a real database schema.','Provide independent integration tests.'],'audience':'developers','language':'en'}
        req=planner.request(custom,self.profiles);p=planner.prepare(self.root,req,self.profiles['F20'],load('factory_product_routes'))
        self.assertIn('validated_custom_product_executor_missing',p['blockers'])
    def test_new_product_specific_week_is_actually_manufactured(self):
        planner.cycle(self.root,REGISTRY)
        intake=self.root/'product-planning/intake'
        req={'schema':planner.SCHEMA,'kind':'catalog','family_id':'F31','recipe':'weekly_planner','parameters':{'week':'2026-11-02'}}
        (intake/'dated-product.json').write_text(json.dumps(req))
        # Existing catalog jobs must not be confused with this new requested date.
        actual=planner.execute
        with patch.object(planner,'resources',return_value=CAP),patch.object(planner,'execute',side_effect=lambda root,r: actual(root,r) if r['family_id']=='F31' else {'status':'blocked_executor_not_routed','retry_after_seconds':3600}):
            for _ in range(len(planner.CATALOG)+5):r=planner.cycle(self.root,REGISTRY,dispatch=True,max_execute=2)
        row=next(x for x in r['rows'] if x['request'].get('parameters',{}).get('week')=='2026-11-02')
        self.assertEqual(row['status'],'native_recipe_verified')
        self.assertEqual(row['proof']['verified_manufacturing_receipts'],50)
        self.assertEqual(row['proof']['product_id'],'fieldwork_planner_20261102')
        self.assertFalse(row['proof']['custom_requirements_satisfied'])
    def test_bad_input_isolated_semantic_duplicate_suppressed_and_legacy_orders_planned(self):
        planner.cycle(self.root,REGISTRY);intake=self.root/'product-planning/intake'
        seed=next(x for x in planner.seeds(self.profiles) if x['family_id']=='F20')
        (intake/'dup.json').write_text(json.dumps(seed));(intake/'bad.json').write_text('not json')
        old=self.root/'production-instructions/orders';old.mkdir(parents=True)
        for n in (1,2):
            item={'id':'WO-%08d'%n,'phase':'engineering_specification','family_id':'F29','subject':'Create a real custom contract template',
              'acceptance':['Deliver usable editable document.','Verify fields with independent tests.'],'status':'issued'}
            (old/(item['id']+'.json')).write_text(json.dumps(item))
        r=planner.cycle(self.root,REGISTRY)
        self.assertEqual(r['existing_order_plans'],1);self.assertEqual(r['existing_orders_scanned'],2)
        self.assertEqual(r['unique_product_plans'],41);self.assertGreaterEqual(r['duplicate_intakes_suppressed'],1)
        row=next(x for x in r['rows'] if len(x['source_orders'])==2)
        self.assertEqual(row['status'],'blocked_missing_engineering_or_inputs')
        self.assertEqual(len(r['rejected_inputs']),1)
    def test_resource_hold_never_launches_and_failure_does_not_claim_success(self):
        with patch.object(planner,'resources',return_value=dict(CAP,memory_available_mb=100)),patch.object(planner,'execute') as execute:
            r=planner.cycle(self.root,REGISTRY,dispatch=True);execute.assert_not_called();self.assertIn('memory_below_safe_reserve',r['resource_holds'])
        with patch.object(planner,'resources',return_value=CAP),patch.object(planner,'execute',return_value={'status':'timed_out','retry_after_seconds':300}):
            r=planner.cycle(self.root,REGISTRY,dispatch=True,max_execute=1)
        self.assertEqual(r['executions_this_tick'],1);self.assertEqual(r['verified_native_product_plans'],0)
        timed=next(x for x in r['rows'] if x['status']=='timed_out');self.assertGreater(timed['retry_at'],timed['last_attempt'])
    def test_all_catalog_routes_exist_and_office_has_sufficient_timeout(self):
        from types import SimpleNamespace
        import sys
        with patch.object(planner,'load',return_value=SimpleNamespace(toolchain=lambda p:(p.parent,Path(sys.executable)))):
            for family in planner.CATALOG:
                command,timeout=planner.command_for(self.root,{'family_id':family})
                script=next(Path(x) for x in command if x.endswith('.py'))
                self.assertTrue(script.is_file(),family)
                self.assertEqual(timeout,210 if family=='F27' else 90)
                if family=='F27':self.assertIn('--worker',command);self.assertIn('--toolchain',command)
        with patch.object(planner,'load',side_effect=RuntimeError('no verified toolchain')):
            self.assertEqual(planner.execute(self.root,{'family_id':'F27'})['status'],'blocked_executor_or_toolchain_unavailable')
    def test_non_object_intakes_do_not_crash_entire_queue(self):
        for value in (None,[],42,'invalid'):
            with self.assertRaises(ValueError):planner.request(value,self.profiles)
        planner.cycle(self.root,REGISTRY)
        (self.root/'product-planning/intake/array.json').write_text('[]')
        report=planner.cycle(self.root,REGISTRY)
        self.assertEqual(report['unique_product_plans'],40)
        self.assertEqual(len(report['rejected_inputs']),1)
    def test_f19_route_restores_tampered_export_and_metadata(self):
        req={'family_id':'F19'};product=planner.CATALOG['F19']
        self.assertEqual(planner.execute(self.root,req)['exit_code'],0)
        self.assertIsNotNone(planner.proof(self.root,product,'F19',proto))
        target=self.root/'digital-products'/product
        archive=target/(product+'-internal-qa.zip');original=archive.read_bytes()
        archive.write_bytes(b'forged')
        manifest=planner.read(target/'manufacturing_manifest.json')
        import hashlib
        manifest['artifact_sha256']=hashlib.sha256(b'forged').hexdigest()
        (target/'manufacturing_manifest.json').write_text(json.dumps(manifest))
        self.assertEqual(planner.execute(self.root,req)['exit_code'],0)
        self.assertEqual(archive.read_bytes(),original)
        self.assertIsNotNone(planner.proof(self.root,product,'F19',proto))
    def test_symlink_and_evidence_escape_rejected(self):
        alias=self.root/'alias';alias.symlink_to(self.root,target_is_directory=True)
        with self.assertRaises(ValueError):planner.cycle(alias,REGISTRY)
        valid,invalid=planner.evidence_checks(self.root,[{'path':'../secret','sha256':'a'*64,'purpose':'verified_sources'}])
        self.assertFalse(valid);self.assertEqual(len(invalid),1)
    def test_forged_export_and_manifest_do_not_pass_old_native_proof(self):
        f31=load('factory_build50_f31_planner');r=f31.build(self.root,'2026-11-02');product=r['product_id']
        self.assertIsNotNone(planner.proof(self.root,product,'F31',proto))
        p=self.root/'digital-products'/product;arc=p/(product+'-internal-qa.zip');arc.write_bytes(b'forged replacement')
        manifest=planner.read(p/'manufacturing_manifest.json');import hashlib
        manifest['artifact_sha256']=hashlib.sha256(arc.read_bytes()).hexdigest();(p/'manufacturing_manifest.json').write_text(json.dumps(manifest))
        self.assertIsNone(planner.proof(self.root,product,'F31',proto))
if __name__=='__main__':unittest.main()
