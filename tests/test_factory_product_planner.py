import importlib.util
import hashlib
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
        self.assertEqual(len(r['families_awaiting_specialist_executor']),20)
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
    def test_existing_mpw_order_recovers_verified_family_into_a_blocked_custom_plan(self):
        # The order itself has no family_id, as in the real three-order courier.
        # The exact ZIP hash, warehouse manifest and returned QA receipt must agree.
        import zipfile
        name="fieldwork_engineering_calculators"
        version="a"*64
        stock=self.root/"production-warehouse"/"finished"/name/version
        stock.mkdir(parents=True)
        archive=stock/"product.zip"
        with zipfile.ZipFile(archive,"w") as z:
            z.writestr("product/readme.txt","reproducible source-bound review")
        archive_sha=__import__("hashlib").sha256(archive.read_bytes()).hexdigest()
        (stock/"warehouse_manifest.json").write_text(json.dumps({
            "family_id":"F28","product_id":name,"source_sha256":version,
            "artifact_sha256":archive_sha,"manufacturing_qc":"passed",
            "commercial_release":False}))
        ret=self.root/"design-intake"/"mojplaywin-stage1-quality-returns"
        ret.mkdir(parents=True)
        (ret/(name+"-"+version+".json")).write_text(json.dumps({
            "tenant":"mojplaywin-main","status":"return_for_qa_completion",
            "product_id":name,"source_sha256":version,
            "artifact_sha256":archive_sha,"published":False}))
        queue=self.root/"production-instructions"/"orders"
        queue.mkdir(parents=True)
        identity="WO-00000001"
        order={"id":identity,"phase":"engineering_specification",
          "source_product_id":name,"source_sha256":version,
          "source_artifact_sha256":archive_sha,"requesting_site":"mojplaywin.com",
          "origin":"mojplaywin-site-qa-return","status":"issued",
          "subject":"Improve verified greenhouse margin calculator reliability",
          "acceptance":["Measure scientific reliability on real input cases.",
                        "Test invalid input and original source copyright."]}
        (queue/(identity+".json")).write_text(json.dumps(order))
        result=planner.cycle(self.root,REGISTRY)
        self.assertEqual(result["existing_order_plans"],1)
        row=next(x for x in result["rows"] if identity in x["source_orders"])
        self.assertEqual(row["family_id"],"F28")
        self.assertEqual(row["status"],"blocked_missing_engineering_or_inputs")
        self.assertIn("validated_custom_product_executor_missing",row["blockers"])
        self.assertEqual(result["custom_product_executors_verified"],0)
        # Tampering with the warehouse source revokes planning admission;
        # no historical order is edited or falsely completed.
        (stock/"product.zip").write_bytes(b"broken")
        later=planner.cycle(self.root,REGISTRY)
        self.assertEqual(later["existing_order_plans"],0)
        self.assertTrue(any(x.get("reason")=="site_return_lacks_verified_family_or_source"
                            for x in later["rejected_inputs"]))
        self.assertEqual(json.loads((queue/(identity+".json")).read_text())["status"],"issued")

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
                self.assertEqual(timeout,210 if family=='F27' else 240 if family in ('F36','F37','F39') else 90)
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
    def test_large_queue_fair_window_reaches_both_order_and_general_lanes(self):
        legacy={hashlib.sha256(('order-'+str(i)).encode()).hexdigest():{'family_id':'F31'} for i in range(900)}
        general={hashlib.sha256(('general-'+str(i)).encode()).hexdigest():{'family_id':'F32'} for i in range(200)}
        unique={**legacy,**general};seen=set();area=self.root/'product-planning'
        area.mkdir()
        for _ in range(3):
            selection,cursor,path=planner.planning_window(unique,legacy,area)
            keys=[k for k,_ in selection]
            self.assertEqual(len(keys),500)
            self.assertEqual(len(keys),len(set(keys)))
            self.assertGreaterEqual(sum(k in general for k in keys),100)
            seen.update(keys)
            planner.save(path,cursor)
        self.assertEqual(seen,set(unique))
        selection,_,_=planner.planning_window(unique,legacy,area)
        self.assertEqual(len(selection),500)

    def test_window_fills_unused_reserved_slots_and_rejects_unsafe_state(self):
        legacy={hashlib.sha256(('order-'+str(i)).encode()).hexdigest():{} for i in range(10)}
        general={hashlib.sha256(('general-'+str(i)).encode()).hexdigest():{} for i in range(1000)}
        area=self.root/'product-planning';area.mkdir()
        selection,cursor,path=planner.planning_window({**legacy,**general},legacy,area)
        self.assertEqual(len(selection),500)
        self.assertEqual(sum(key in legacy for key,_ in selection),10)
        planner.save(path,cursor)
        self.assertEqual(planner.planning_window({**legacy,**general},legacy,area)[1]['legacy'],cursor['legacy'])
        path.write_text('{"schema":"wrong","legacy":"","general":""}')
        with self.assertRaisesRegex(ValueError,'PLANNER_WINDOW_CURSOR_SCHEMA'):
            planner.planning_window({**legacy,**general},legacy,area)
        path.unlink();path.symlink_to(self.root/'not-a-cursor')
        with self.assertRaisesRegex(ValueError,'PLANNER_WINDOW_UNSAFE_CURSOR'):
            planner.planning_window({**legacy,**general},legacy,area)

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
