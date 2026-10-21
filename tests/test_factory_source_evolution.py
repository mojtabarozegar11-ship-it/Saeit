"""Real source modification, measured acceptance, idempotence and rollback for F27/F28.

This intentionally simulates an *older valid product source*, not a fake
passing verdict. A repaired candidate must implement more useful behavior
and complete a real product QA run before replacing it.
"""
import copy
import importlib.util
import json
from pathlib import Path
import re
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]

def load(name):
    spec=importlib.util.spec_from_file_location(name,ROOT/'scripts'/(name+'.py'))
    mod=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

designer=load('factory_recipe_designer')
maker=load('factory_product_maker')

def make_legacy_source(source):
    """Reproduce a genuinely functioning older revision with no batch feature."""
    calculator=source/'calculator.py'
    body=calculator.read_text(encoding='utf8')
    start=body.index('# BATCH_API_V2_START')
    end=body.index('# BATCH_API_V2_END',start)+len('# BATCH_API_V2_END')
    body=body[:start]+body[end:]
    newer="""    incoming=json.load(sys.stdin)
    print(json.dumps(calculate_batch(incoming) if isinstance(incoming,list)
                     else calculate(incoming), sort_keys=True))"""
    older="""    print(json.dumps(calculate(json.load(sys.stdin)), sort_keys=True))"""
    assert newer in body
    body=body.replace(newer,older)
    calculator.write_text(body,encoding='utf8')
    tests=source/'test_calculator.py'
    cases=tests.read_text(encoding='utf8')
    # Remove both imported batch capability and its two acceptance tests.
    cases=re.sub(r'(?ms)^# BATCH_TESTS_V2_START\n.*?^# BATCH_TESTS_V2_END\n','',cases)
    cases=re.sub(r'(?ms)^    # BATCH_TESTS_V2_START\n.*?^    # BATCH_TESTS_V2_END\n','',cases)
    assert 'calculate_batch' not in cases
    tests.write_text(cases,encoding='utf8')
    receipt=source/'design_receipt.json'
    evidence=json.loads(receipt.read_text(encoding='utf8'))
    assert evidence.pop('generator_capability_revision')=='verified-batch-v2'
    receipt.write_text(json.dumps(evidence,sort_keys=True,indent=2)+'\n',encoding='utf8')
    return body

class SourceEvolutionTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        requests=json.loads((ROOT/'factory_config/design_opportunities.json').read_text())['requests']
        self.spec=next(q for q in requests if q['family_id']=='F28')
        self.recipes=self.root/'generated-product-recipes'
        created=designer.compile_recipe(self.spec,self.recipes)
        self.name=created['recipe']
        self.source=self.recipes/self.name

    def test_existing_product_gains_real_batch_feature_and_new_customer_tests(self):
        old_code=make_legacy_source(self.source)
        maker.verify_recipe(self.source)
        before=maker.source_digest(self.source,maker.inspect_recipe(self.source)[1])
        result=designer.evolve_recipe(self.name,self.recipes)
        self.assertTrue(result['changed'])
        self.assertEqual(result['previous_source_sha256'],before)
        self.assertEqual(result['implemented_feature'],'bounded_atomic_customer_batch_1_to_100')
        self.assertNotEqual(result['previous_source_sha256'],result['revised_source_sha256'])
        self.assertIn('def calculate_batch', (self.source/'calculator.py').read_text())
        retained=Path(result['previous_source_retained'])
        self.assertEqual((retained/'calculator.py').read_text(),old_code)
        self.assertGreaterEqual(result['measured_acceptance']['successful_tests'],5)
        self.assertFalse(result['quality_1000_certified'])
        self.assertFalse(result['commercial_release'])
        build=maker.manufacture(self.name,self.recipes,self.root/'digital-products')
        self.assertTrue(build['changed'])
        self.assertTrue(Path(build['private_artifact']).is_file())
        again=designer.evolve_recipe(self.name,self.recipes)
        self.assertFalse(again['changed'])
        self.assertEqual(again['reason'],'already_evolved')

    def test_owner_modified_or_unknown_extra_files_cannot_be_silently_replaced(self):
        make_legacy_source(self.source)
        (self.source/'custom_license.txt').write_text('unverified authored addon')
        with self.assertRaisesRegex(ValueError,'FILESET_CHANGE_REQUIRES_REVIEW'):
            designer.evolve_recipe(self.name,self.recipes)
        self.assertNotIn('def calculate_batch', (self.source/'calculator.py').read_text())
        self.assertFalse((self.root/'generated-source-revisions').exists())

    def test_source_request_tampering_blocks_evolution_without_loss(self):
        make_legacy_source(self.source)
        source=self.source/'design_request.json'
        data=json.loads(source.read_text())
        data['title']='Unauthorized changed provenance'
        source.write_text(json.dumps(data))
        with self.assertRaisesRegex(ValueError,'PROVENANCE_MISMATCH'):
            designer.evolve_recipe(self.name,self.recipes)
        self.assertFalse((self.root/'generated-source-revisions').exists())

    def test_bad_candidate_quality_never_overwrites_existing_source(self):
        original=make_legacy_source(self.source)
        original_compile=designer.compile_recipe
        def corrupted_compile(spec,root):
            output=original_compile(spec,root)
            target=Path(root)/output['recipe']/'calculator.py'
            target.write_text('raise RuntimeError("bad generated source")\n')
            return output
        from unittest import mock
        with mock.patch.object(designer,'compile_recipe',side_effect=corrupted_compile):
            with self.assertRaises(RuntimeError):
                designer.evolve_recipe(self.name,self.recipes)
        self.assertEqual((self.source/'calculator.py').read_text(),original)
        self.assertFalse((self.root/'generated-source-revisions').exists())

    def test_uncertified_static_recipe_never_enters_generated_evolution(self):
        with self.assertRaisesRegex(ValueError,'COMPILER_OWNED_RECIPE'):
            designer.evolve_recipe('greenhouse_crop_margin',self.recipes)

if __name__=='__main__':
    unittest.main()
