import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('build50',ROOT/'scripts/factory_build_50.py')
engine=importlib.util.module_from_spec(spec);spec.loader.exec_module(engine)

class Build50Tests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.plan={'schema':engine.SCHEMA,'product_id':'test_product','producer_id':'author',
                   'source_snapshot_sha256':'a'*64,'work_packages':[
                       {'id':'task_%02d'%i,'instruction':'Complete the following measurable task: '+('derive constraints for ','implement a working solution for ','independently test ','revise identified defects in ')[i%4]+('input schema','edge behavior','compatibility','error messages','failure recovery','data provenance','user workflow','accessibility','security boundary','data integrity','resource usage','release package')[i//4],
                        'acceptance':['Expected result is independently checked','Failure behavior is explicitly checked']} for i in range(48)]}
    def worker(self,task,context):
        name=task['id']+'.txt';(Path(context['folder'])/name).write_text(task['instruction'])
        return {'passed':True,'outputs':[name],'successful_checks':2}
    def assembler(self,plan,context):
        (Path(context['folder'])/'assembled.txt').write_text('\n'.join(t['instruction'] for t in plan['work_packages']))
        return {'passed':True,'outputs':['assembled.txt'],'successful_checks':1}
    def reviewer(self,plan,context):
        (Path(context['folder'])/'review.txt').write_text('SIMULATED UNIT TEST REVIEW, NOT A PRODUCTION APPROVAL')
        return {'passed':True,'reviewer_id':'independent_fixture','critical_defects':[],
                'gates':dict.fromkeys(engine.GATES,True),'outputs':['review.txt'],'successful_checks':10}
    def run_build(self,worker=None,reviewer=None,now=0):
        return engine.run_attempt(self.root,self.plan,worker or self.worker,self.assembler,reviewer or self.reviewer,now=now)
    def test_exact_1_48_1_actual_work_and_hash_chain(self):
        state=self.run_build()
        self.assertEqual(state['completed_stages'],50)
        self.assertEqual(state['status'],'awaiting_owner_acceptance')
        self.assertTrue(engine.verify_attempt(self.root/'build-50/test_product',state,'a'*64))
        self.assertFalse(state['commercial_release'])
        self.assertIsNone(state['universal_quality_score'])
    def test_failure_returns_to_planning_and_keeps_failed_output(self):
        def broken(task,context):
            if task['id']=='task_07':raise ValueError('DELIBERATE_FAILURE')
            return self.worker(task,context)
        first=self.run_build(worker=broken)
        self.assertEqual(first['next_stage'],1)
        self.assertEqual(first['status'],'rework_required')
        self.assertTrue((Path(first['attempt_folder'])/'task_00.txt').is_file())
        seen=[]
        def corrected(task,context):
            seen.append(task['id']);self.assertTrue(context['previous_defects'])
            return self.worker(task,context)
        second=self.run_build(worker=corrected,now=61)
        self.assertEqual(seen[0],'task_00')
        self.assertEqual(second['attempt'],2)
        self.assertEqual(second['completed_stages'],50)
    def test_false_success_without_files_cannot_advance(self):
        state=self.run_build(worker=lambda task,context:{'passed':True,'outputs':[],'successful_checks':100})
        self.assertEqual(state['completed_stages'],1)
        self.assertEqual(state['status'],'rework_required')
    def test_repeated_work_is_rejected(self):
        def duplicate(task,context):
            (Path(context['folder'])/'same.txt').write_text('same work')
            return {'passed':True,'outputs':['same.txt'],'successful_checks':2}
        state=self.run_build(worker=duplicate)
        self.assertEqual(state['status'],'rework_required')
        self.assertIn('REUSED_WORK',state['defects'][0]['reason'])
    def test_subsets_of_earlier_outputs_cannot_be_new_work(self):
        def subsets(task,context):
            folder=Path(context['folder'])
            for name in ('first','second','third'):(folder/(name+'.txt')).write_text(name)
            names=['first.txt','second.txt','third.txt'] if task['id']=='task_00' else ['first.txt','second.txt']
            return {'passed':True,'outputs':names,'successful_checks':2}
        state=self.run_build(worker=subsets)
        self.assertEqual(state['completed_stages'],2)
        self.assertIn('REUSED_WORK',state['defects'][0]['reason'])
    def test_precreated_future_file_does_not_count_as_new_stage_work(self):
        def precreate(task,context):
            folder=Path(context['folder'])
            if task['id']=='task_00':
                (folder/'future.txt').write_text('precreated future output')
                return self.worker(task,context)
            return {'passed':True,'outputs':['future.txt'],'successful_checks':2}
        state=self.run_build(worker=precreate)
        self.assertEqual(state['completed_stages'],2)
        self.assertIn('NO_NEW_WORK',state['defects'][0]['reason'])
    def test_critical_defect_cannot_be_averaged_away(self):
        def reviewer(plan,context):
            result=self.reviewer(plan,context);result['critical_defects']=['incorrect calculation'];return result
        self.assertEqual(self.run_build(reviewer=reviewer)['next_stage'],1)
    def test_same_author_review_is_rejected(self):
        def reviewer(plan,context):
            result=self.reviewer(plan,context);result['reviewer_id']='author';return result
        self.assertEqual(self.run_build(reviewer=reviewer)['status'],'rework_required')
    def test_reviewer_cannot_mutate_previous_work(self):
        def reviewer(plan,context):
            (Path(context['folder'])/'task_00.txt').write_text('tampered')
            return self.reviewer(plan,context)
        self.assertEqual(self.run_build(reviewer=reviewer)['status'],'rework_required')
    def test_corruption_invalidates_verified_attempt(self):
        state=self.run_build();(Path(state['attempt_folder'])/'task_20.txt').write_text('damaged')
        self.assertFalse(engine.verify_attempt(self.root/'build-50/test_product',state,'a'*64))
        self.assertFalse(engine.verify_attempt(self.root/'build-50/test_product',state,'b'*64))
    def test_technical_products_are_sent_to_planning_not_auto_approved(self):
        folder=self.root/'digital-products/test_product';folder.mkdir(parents=True)
        package=folder/'test_product-internal-qa.zip';package.write_bytes(b'TEST FIXTURE ONLY')
        engine.save(folder/'manufacturing_manifest.json',{'artifact_sha256':engine.file_sha(package)})
        result=engine.audit(self.root)
        self.assertEqual(result['requiring_replanning'],1)
        self.assertEqual(result['verified_50_stage_builds'],0)
        self.assertTrue(package.exists())
        ticket=engine.read(self.root/'build-50/test_product/planning-request.json')
        self.assertEqual(ticket['required_work_packages'],48)
    def test_unchanged_audit_receipts_are_not_rewritten_but_tampering_rechecks(self):
        import os
        folder=self.root/'digital-products/test_product';folder.mkdir(parents=True)
        package=folder/'test_product-internal-qa.zip'
        package.write_bytes(b'VALID_HASH_BOUND_FIXTURE')
        engine.save(folder/'manufacturing_manifest.json',
                    {'artifact_sha256':engine.file_sha(package)})
        self.assertEqual(engine.audit(self.root)['requiring_replanning'],1)
        ticket=self.root/'build-50/test_product/planning-request.json'
        status=self.root/'build-50-status.json'
        older=1_700_000_000_000_000_000
        os.utime(ticket,ns=(older,older))
        os.utime(status,ns=(older,older))
        self.assertEqual(engine.audit(self.root)['verified_50_stage_builds'],0)
        self.assertEqual(ticket.stat().st_mtime_ns,older)
        self.assertEqual(status.stat().st_mtime_ns,older)
        before=engine.read(ticket)
        package.write_bytes(b'CHANGED_BYTES')
        self.assertEqual(engine.audit(self.root)['verified_50_stage_builds'],0)
        after=engine.read(ticket)
        self.assertNotEqual(before['source_snapshot_sha256'],after['source_snapshot_sha256'])
        self.assertFalse(after['technical_artifact_integrity'])
        self.assertFalse(after['commercial_release'])
        self.assertNotEqual(ticket.stat().st_mtime_ns,older)
        self.assertEqual(status.stat().st_mtime_ns,older)

    def test_unchanged_audit_never_trusts_symlinked_ticket(self):
        folder=self.root/'digital-products/test_product';folder.mkdir(parents=True)
        package=folder/'test_product-internal-qa.zip'
        package.write_bytes(b'FIXTURE')
        engine.save(folder/'manufacturing_manifest.json',
                    {'artifact_sha256':engine.file_sha(package)})
        ticket=self.root/'build-50/test_product/planning-request.json'
        ticket.parent.mkdir(parents=True)
        protected=self.root/'protected.txt';protected.write_text('UNTOUCHED')
        ticket.symlink_to(protected)
        with self.assertRaisesRegex(ValueError,'BUILD50_UNSAFE_STATE'):
            engine.audit(self.root)
        self.assertEqual(protected.read_text(),'UNTOUCHED')

    def test_fewer_than_48_tasks_is_rejected(self):
        self.plan['work_packages'].pop()
        with self.assertRaises(ValueError):self.run_build()
    def test_changing_only_task_numbers_is_not_distinct_work(self):
        for i,task in enumerate(self.plan['work_packages']):
            task['instruction']='Write the same generic report again, merely changing its sequence number to %d.'%i
        with self.assertRaisesRegex(ValueError,'DISTINCT_SUBSTANTIVE'):
            self.run_build()
    def test_repair_does_not_stop_after_three_or_thirty_attempts(self):
        def failing(task,context):raise ValueError('REPAIR_NOT_YET_VALID')
        for n in range(35):state=self.run_build(worker=failing,now=n*61)
        self.assertEqual(state['attempt'],35)
        self.assertEqual(state['next_stage'],1)
        self.assertIsNone(state['lifetime_attempt_limit'])
        self.assertEqual(len(list((self.root/'build-50/test_product').glob('attempt-*'))),35)
    def test_every_quality_gate_is_mandatory(self):
        for n,gate in enumerate(engine.GATES):
            def reject(plan,context,gate=gate):
                result=self.reviewer(plan,context);result['gates'][gate]=False;return result
            self.assertEqual(self.run_build(reviewer=reject,now=n*61)['status'],'rework_required')

    def test_review_cannot_reuse_assembled_product_as_evidence(self):
        def reviewer(plan,context):
            result=self.reviewer(plan,context);result['outputs']=['assembled.txt'];return result
        state=self.run_build(reviewer=reviewer)
        self.assertEqual(state['status'],'rework_required')
        self.assertIn('REVIEW_REUSES',state['defects'][0]['reason'])

    def test_worker_cannot_claim_protocol_receipt_as_product(self):
        state=self.run_build(worker=lambda task,context:{'passed':True,
            'outputs':['01-plan.json'],'successful_checks':2})
        self.assertEqual(state['status'],'rework_required')
        self.assertIn('RESERVED_EVIDENCE',state['defects'][0]['reason'])

    def test_rejected_or_incomplete_state_never_verifies(self):
        state=self.run_build();home=self.root/'build-50/test_product'
        for change in ({'status':'rework_required'},{'completed_stages':49},
                       {'defects':['unresolved']},{'product_id':'other_product'}):
            self.assertFalse(engine.verify_attempt(home,dict(state,**change),'a'*64))

    def test_missing_reviewer_or_checks_never_verifies_even_with_rehashed_receipt(self):
        state=self.run_build();home=self.root/'build-50/test_product'
        final_path=Path(state['attempt_folder'])/'50-summary.json'
        original=engine.read(final_path)
        for change in ({'reviewer_id':''},{'successful_checks':0},{'passed':False}):
            final=json.loads(json.dumps(original));final['review'].update(change)
            engine.save(final_path,final)
            forged=dict(state,final_receipt_sha256=engine.digest(final))
            self.assertFalse(engine.verify_attempt(home,forged,'a'*64))

    def test_interrupted_process_does_not_permanently_block_product(self):
        def killed(task,context):
            self.worker(task,context)
            raise KeyboardInterrupt('simulated process termination')
        with self.assertRaises(KeyboardInterrupt):self.run_build(worker=killed)
        retained=self.root/'build-50/test_product/attempt-00000001'
        self.assertTrue((retained/'task_00.txt').is_file())
        seen=[]
        def recovered(task,context):
            seen.extend(context['previous_defects']);return self.worker(task,context)
        state=self.run_build(worker=recovered,now=61)
        self.assertEqual(state['attempt'],2)
        self.assertEqual(state['completed_stages'],50)
        self.assertEqual(seen[0]['reason'],'BUILD50_INTERRUPTED_ATTEMPT')
        self.assertTrue((retained/'task_00.txt').is_file())
        self.assertTrue(engine.verify_attempt(self.root/'build-50/test_product',state,'a'*64))

    def test_lock_symlink_is_rejected(self):
        home=self.root/'build-50/test_product';home.mkdir(parents=True)
        target=self.root/'unrelated';target.write_text('preserve')
        (home/'.attempt.lock').symlink_to(target)
        with self.assertRaisesRegex(ValueError,'UNSAFE_LOCK'):self.run_build()
        self.assertEqual(target.read_text(),'preserve')
