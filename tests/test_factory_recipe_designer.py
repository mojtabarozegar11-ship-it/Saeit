"""Synthesize and run real programs without a hand-authored recipe directory."""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

ROOT=Path(__file__).resolve().parents[1]
def load(name):
    spec=importlib.util.spec_from_file_location(name, ROOT/'scripts'/(name+'.py'))
    module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module

designer=load('factory_recipe_designer')
maker=load('factory_product_maker')
warehouse=load('factory_production_warehouse')
SEEDS=ROOT/'factory_config'/'design_opportunities.json'

class DesignerTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.spec=json.loads(SEEDS.read_text())['requests'][0]

    def test_synthesizes_then_manufactures_and_stocks_real_tool(self):
        self.assertFalse((self.root/'recipes').exists())
        result=designer.compile_recipe(self.spec,self.root/'recipes')
        self.assertTrue(result['created'])
        self.assertEqual(result['heldout_examples_passed'],3)
        self.assertGreater(result['search_states_evaluated'],0)
        folder=self.root/'recipes'/result['recipe']
        module_spec=importlib.util.spec_from_file_location('synthesized_tool',folder/'calculator.py')
        module=importlib.util.module_from_spec(module_spec); module_spec.loader.exec_module(module)
        self.assertEqual(module.calculate({'batch_units':20,'parallel_workers':3,'batch_minutes':4})['result'],'15.00')
        made=maker.manufacture(result['recipe'],self.root/'recipes',self.root/'digital-products')
        self.assertTrue(made['changed'])
        archive, manifest=warehouse.inspect_source(self.root,result['recipe'])
        self.assertTrue(archive.is_file())
        self.assertEqual(manifest['qa_measurements']['successful_tests'],3)
        self.assertFalse(result['commercial_release'])

    def test_title_and_examples_do_not_inflate_product_count(self):
        first=designer.compile_recipe(self.spec,self.root/'recipes')
        renamed=copy.deepcopy(self.spec); renamed['title']='A changed title for the same behavior'
        second=designer.compile_recipe(renamed,self.root/'recipes')
        self.assertEqual(first['recipe'],second['recipe'])
        self.assertFalse(second['created'])

    def test_holdout_failure_never_emits_product(self):
        self.spec['acceptance_examples'][0]['output']=999
        with self.assertRaisesRegex(ValueError,'INDEPENDENT_ACCEPTANCE_FAILED'):
            designer.compile_recipe(self.spec,self.root/'recipes')
        self.assertFalse((self.root/'recipes').exists())

    def test_no_training_holdout_overlap(self):
        self.spec['acceptance_examples'][0]=copy.deepcopy(self.spec['training_examples'][0])
        with self.assertRaisesRegex(ValueError,'HOLDOUT_LEAKAGE'):
            designer.compile_recipe(self.spec,self.root/'recipes')

    def test_input_names_cannot_inject_python(self):
        self.spec['inputs'][0]['name']="__import__('os').system('true')"
        with self.assertRaisesRegex(ValueError,'INVALID_INPUT_FIELD'):
            designer.compile_recipe(self.spec,self.root/'recipes')

    def test_unsupported_family_stays_in_rework(self):
        self.spec['family_id']='F12'
        designer.save(self.root/'design-intake'/'request.json',self.spec)
        result=designer.cycle(self.root)
        self.assertEqual(result['new_recipes'],0)
        self.assertIn('ADAPTER_NOT_IMPLEMENTED',result['rework'][0]['reason'])
        self.assertTrue((self.root/'design-intake'/'request.json').is_file())

    def test_unchanged_failure_is_not_retried_each_minute(self):
        self.spec['family_id']='F12'
        designer.save(self.root/'design-intake'/'request.json',self.spec)
        designer.cycle(self.root)
        with mock.patch.object(designer,'compile_recipe',side_effect=AssertionError('must not retry')):
            result=designer.cycle(self.root)
        self.assertEqual(result['requests_processed'],0)

    def test_corrected_request_returns_to_execution(self):
        broken=copy.deepcopy(self.spec); broken['family_id']='F12'
        target=self.root/'design-intake'/'request.json'
        designer.save(target,broken); designer.cycle(self.root)
        designer.save(target,self.spec)
        self.assertEqual(designer.cycle(self.root)['new_recipes'],1)
        self.assertEqual(len(list((self.root/'design-state').glob('*.json'))),2)

    def test_bounded_ticks_do_not_bound_total_catalog(self):
        first=designer.cycle(self.root,seed_file=SEEDS)
        second=designer.cycle(self.root,seed_file=SEEDS)
        third=designer.cycle(self.root,seed_file=SEEDS)
        self.assertEqual([x['new_recipes'] for x in (first,second,third)],[1,1,0])
        self.assertIsNone(first['catalog_lifetime_limit'])
        self.assertEqual(len(list((self.root/'generated-product-recipes').iterdir())),2)

    def test_budget_exhaustion_does_not_approve(self):
        with mock.patch.object(designer,'MAX_STATES',1):
            with self.assertRaisesRegex(ValueError,'SEARCH_BUDGET'):
                designer.compile_recipe(self.spec,self.root/'recipes')
        self.assertFalse((self.root/'recipes').exists())

    def test_training_and_holdouts_have_real_distinct_values(self):
        for group in ('training_examples','acceptance_examples'):
            self.assertGreaterEqual(len(self.spec[group]),3)
        self.spec['training_examples'][0]['inputs']['batch_units']='NaN'
        with self.assertRaisesRegex(ValueError,'NUMBER_OUT_OF_RANGE'):
            designer.compile_recipe(self.spec,self.root/'recipes')

    def test_generated_tool_rejects_zero_denominator(self):
        result=designer.compile_recipe(self.spec,self.root/'recipes')
        path=self.root/'recipes'/result['recipe']/'calculator.py'
        spec=importlib.util.spec_from_file_location('zero_denominator',path)
        tool=importlib.util.module_from_spec(spec); spec.loader.exec_module(tool)
        with self.assertRaises(ValueError):
            tool.calculate({'batch_units':2,'parallel_workers':3,'batch_minutes':0})

class ActualSourceRecoveryTests(unittest.TestCase):
    setUp=DesignerTests.setUp
    def test_broken_generated_code_is_rebuilt_tested_and_retained(self):
        result=designer.compile_recipe(self.spec,self.root/'recipes')
        source=self.root/'recipes'/result['recipe']
        (source/'calculator.py').write_text("raise RuntimeError('injected defect')\n")
        with self.assertRaises(RuntimeError): maker.verify_recipe(source)
        recovered=designer.recover_recipe(result['recipe'],self.root/'recipes')
        self.assertIn('injected defect',(Path(recovered['retained_broken_source'])/'calculator.py').read_text())
        self.assertEqual(recovered['qa_measurements']['successful_tests'],3)
        self.assertEqual(maker.verify_recipe(source),'unit_tests_passed')

    def test_changed_original_spec_is_not_silently_overwritten(self):
        result=designer.compile_recipe(self.spec,self.root/'recipes')
        source=self.root/'recipes'/result['recipe']
        original=json.loads((source/'design_request.json').read_text())
        original['title']='Tampered provenance'
        (source/'design_request.json').write_text(json.dumps(original))
        with self.assertRaisesRegex(ValueError,'PROVENANCE_MISMATCH'):
            designer.recover_recipe(result['recipe'],self.root/'recipes')

class DatabaseDesignIntakeTests(unittest.TestCase):
    setUp=DesignerTests.setUp
    def test_explicit_spec_in_factory_draft_becomes_recipe_without_db_mutation(self):
        import sqlite3
        db=self.root/'products.sqlite3'
        with sqlite3.connect(db) as conn:
            conn.execute('CREATE TABLE core_product(id INTEGER,metadata TEXT,active INTEGER,factory_managed INTEGER)')
            for ident,active,managed in ((1,0,1),(2,1,1),(3,0,0)):
                conn.execute('INSERT INTO core_product VALUES (?,?,?,?)',(ident,json.dumps({'factory_design':self.spec}),active,managed))
        before=db.read_bytes()
        result=designer.cycle(self.root,database=db)
        self.assertEqual(result['database_design_requests_imported'],1)
        self.assertEqual(result['new_recipes'],1)
        self.assertEqual(db.read_bytes(),before)

    def test_new_origin_requires_explicit_supported_origin(self):
        for origin in designer.ORIGINS:
            spec=copy.deepcopy(self.spec);spec['origin']=origin
            designer.validate(spec)
        self.spec['origin']='invented_source'
        with self.assertRaisesRegex(ValueError,'ORIGIN_INVALID'):
            designer.validate(self.spec)

class RetryLifecycleTests(unittest.TestCase):
    setUp=DesignerTests.setUp

    def test_transient_design_failure_retries_and_produces_without_manual_edit(self):
        designer.save(self.root/'design-intake'/'request.json',self.spec)
        with mock.patch.object(designer,'compile_recipe',side_effect=OSError('temporary I/O failure')):
            first=designer.cycle(self.root,now=100)
        self.assertEqual(first['requests_processed'],1)
        self.assertEqual(first['rework'][0]['return_to_stage'],1)
        with mock.patch.object(designer,'compile_recipe',side_effect=AssertionError('backoff')):
            self.assertEqual(designer.cycle(self.root,now=159)['requests_processed'],0)
        self.assertEqual(designer.cycle(self.root,now=161)['new_recipes'],1)

    def test_malformed_requests_cannot_exceed_per_cycle_budget(self):
        folder=self.root/'design-intake';folder.mkdir()
        for i in range(5):(folder/('%d.json'%i)).write_text('invalid JSON')
        result=designer.cycle(self.root,max_designs=1,now=100)
        self.assertEqual(result['requests_processed'],1)
        self.assertEqual(result['pending_requests'],4)
        self.assertEqual(len(result['rework']),1)
        second=designer.cycle(self.root,max_designs=1,now=101)
        self.assertEqual(second['requests_processed'],1)
        self.assertEqual(second['deferred_rework_requests'],1)

    def test_unsupported_request_remains_retryable_without_lifetime_limit(self):
        self.spec['family_id']='F12'
        designer.save(self.root/'design-intake'/'request.json',self.spec)
        result=designer.cycle(self.root,now=0)
        for n in range(1,35):result=designer.cycle(self.root,now=n*4000)
        self.assertEqual(result['rework'][0]['attempt'],35)
        self.assertIsNone(result['rework'][0]['lifetime_attempt_limit'])

    def test_database_outage_does_not_stop_local_seed_designs(self):
        result=designer.cycle(self.root,seed_file=SEEDS,database=self.root/'missing.db')
        self.assertEqual(result['new_recipes'],1)
        self.assertEqual(result['intake_failures'][0]['source'],'database')

    def test_broken_seed_does_not_stop_existing_intake(self):
        designer.save(self.root/'design-intake'/'request.json',self.spec)
        seed=self.root/'broken-seed.json';seed.write_text('invalid JSON')
        result=designer.cycle(self.root,seed_file=seed)
        self.assertEqual(result['new_recipes'],1)
        self.assertEqual(result['intake_failures'][0]['source'],'seed')
