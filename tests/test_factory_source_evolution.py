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
    start=body.index('# DISTRIBUTION_API_V4_START')
    end=body.index('# DISTRIBUTION_API_V4_END',start)+len('# DISTRIBUTION_API_V4_END')
    body=body[:start]+body[end:]
    start=body.index('# GROUPED_STATISTICS_API_V5_START')
    end=body.index('# GROUPED_STATISTICS_API_V5_END',start)+len('# GROUPED_STATISTICS_API_V5_END')
    body=body[:start]+body[end:]
    start=body.index('# SENSITIVITY_API_V6_START')
    end=body.index('# SENSITIVITY_API_V6_END',start)+len('# SENSITIVITY_API_V6_END')
    body=body[:start]+body[end:]
    start=body.index('# STATS_API_V3_START')
    end=body.index('# STATS_API_V3_END',start)+len('# STATS_API_V3_END')
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
    cases=re.sub(r'(?ms)^# STATS_TESTS_V3_START\n.*?^# STATS_TESTS_V3_END\n','',cases)
    cases=re.sub(r'(?ms)^    # STATS_TESTS_V3_START\n.*?^    # STATS_TESTS_V3_END\n','',cases)
    assert 'calculate_batch' not in cases
    cases=re.sub(r'(?ms)^# DISTRIBUTION_TESTS_V4_START\n.*?^# DISTRIBUTION_TESTS_V4_END\n','',cases)
    cases=re.sub(r'(?ms)^    # DISTRIBUTION_TESTS_V4_START\n.*?^    # DISTRIBUTION_TESTS_V4_END\n','',cases)
    cases=re.sub(r'(?ms)^# GROUPED_STATISTICS_TESTS_V5_START\n.*?^# GROUPED_STATISTICS_TESTS_V5_END\n','',cases)
    cases=re.sub(r'(?ms)^    # GROUPED_STATISTICS_TESTS_V5_START\n.*?^    # GROUPED_STATISTICS_TESTS_V5_END\n','',cases)
    assert 'calculate_statistics' not in cases
    assert 'calculate_distribution' not in cases
    cases=re.sub(r'(?ms)^# SENSITIVITY_TESTS_V6_START\n.*?^# SENSITIVITY_TESTS_V6_END\n','',cases)
    cases=re.sub(r'(?ms)^    # SENSITIVITY_TESTS_V6_START\n.*?^    # SENSITIVITY_TESTS_V6_END\n','',cases)
    assert 'calculate_sensitivity' not in cases
    tests.write_text(cases,encoding='utf8')
    receipt=source/'design_receipt.json'
    evidence=json.loads(receipt.read_text(encoding='utf8'))
    assert evidence.pop('generator_capability_revision')=='verified-grouped-statistics-v5'
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
        self.assertEqual(result['implemented_feature'],'verified_decimal_one_step_input_sensitivity_analysis_v6')
        self.assertNotEqual(result['previous_source_sha256'],result['revised_source_sha256'])
        self.assertIn('def calculate_batch', (self.source/'calculator.py').read_text())
        self.assertIn('def calculate_statistics', (self.source/'calculator.py').read_text())
        self.assertIn('def calculate_distribution', (self.source/'calculator.py').read_text())
        self.assertIn('def calculate_grouped_statistics', (self.source/'calculator.py').read_text())
        self.assertIn('def calculate_sensitivity', (self.source/'calculator.py').read_text())
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

    def test_v2_existing_product_upgrades_to_v4_without_relabeling_as_new_recipe(self):
        calculator=self.source/'calculator.py'
        code=calculator.read_text(encoding='utf8')
        first=code.index('# DISTRIBUTION_API_V4_START')
        last=code.index('# DISTRIBUTION_API_V4_END',first)+len('# DISTRIBUTION_API_V4_END')
        code=code[:first]+code[last:]
        first=code.index('# STATS_API_V3_START')
        last=code.index('# STATS_API_V3_END',first)+len('# STATS_API_V3_END')
        code=code[:first]+code[last:]
        first=code.index('# GROUPED_STATISTICS_API_V5_START')
        last=code.index('# GROUPED_STATISTICS_API_V5_END',first)+len('# GROUPED_STATISTICS_API_V5_END')
        code=code[:first]+code[last:]
        first=code.index('# SENSITIVITY_API_V6_START')
        last=code.index('# SENSITIVITY_API_V6_END',first)+len('# SENSITIVITY_API_V6_END')
        calculator.write_text(code[:first]+code[last:],encoding='utf8')
        tests=self.source/'test_calculator.py'
        content=tests.read_text(encoding='utf8')
        content=re.sub(r'(?ms)^# DISTRIBUTION_TESTS_V4_START\n.*?^# DISTRIBUTION_TESTS_V4_END\n','',content)
        content=re.sub(r'(?ms)^    # DISTRIBUTION_TESTS_V4_START\n.*?^    # DISTRIBUTION_TESTS_V4_END\n','',content)
        content=re.sub(r'(?ms)^# STATS_TESTS_V3_START\n.*?^# STATS_TESTS_V3_END\n','',content)
        content=re.sub(r'(?ms)^    # STATS_TESTS_V3_START\n.*?^    # STATS_TESTS_V3_END\n','',content)
        content=re.sub(r'(?ms)^# GROUPED_STATISTICS_TESTS_V5_START\n.*?^# GROUPED_STATISTICS_TESTS_V5_END\n','',content)
        content=re.sub(r'(?ms)^    # GROUPED_STATISTICS_TESTS_V5_START\n.*?^    # GROUPED_STATISTICS_TESTS_V5_END\n','',content)
        content=re.sub(r'(?ms)^# SENSITIVITY_TESTS_V6_START\n.*?^# SENSITIVITY_TESTS_V6_END\n','',content)
        content=re.sub(r'(?ms)^    # SENSITIVITY_TESTS_V6_START\n.*?^    # SENSITIVITY_TESTS_V6_END\n','',content)
        tests.write_text(content,encoding='utf8')
        receipt=self.source/'design_receipt.json'
        data=json.loads(receipt.read_text(encoding='utf8'))
        data['generator_capability_revision']='verified-batch-v2'
        receipt.write_text(json.dumps(data,sort_keys=True),encoding='utf8')
        maker.verify_recipe(self.source,minimum_tests=5)
        old_digest=maker.source_digest(self.source,maker.inspect_recipe(self.source)[1])
        change=designer.evolve_recipe(self.name,self.recipes)
        self.assertTrue(change['changed'])
        self.assertEqual(change['previous_source_sha256'],old_digest)
        self.assertTrue(Path(change['previous_source_retained']).is_dir())
        self.assertEqual(json.loads((self.source/'design_receipt.json').read_text())['generator_capability_revision'],
                         'verified-one-percent-sensitivity-v6')
        maker.verify_recipe(self.source,minimum_tests=7)
        self.assertFalse(designer.evolve_recipe(self.name,self.recipes)['changed'])

    def test_real_v3_source_gains_v4_distribution_with_retained_old_bytes(self):
        calculator=self.source/'calculator.py'
        code=calculator.read_text(encoding='utf8')
        start=code.index('# DISTRIBUTION_API_V4_START')
        finish=code.index('# DISTRIBUTION_API_V4_END',start)+len('# DISTRIBUTION_API_V4_END')
        code=code[:start]+code[finish:]
        start=code.index('# SENSITIVITY_API_V6_START')
        finish=code.index('# SENSITIVITY_API_V6_END',start)+len('# SENSITIVITY_API_V6_END')
        calculator.write_text(code[:start]+code[finish:],encoding='utf8')
        tests=self.source/'test_calculator.py'
        prior=tests.read_text(encoding='utf8')
        prior=re.sub(r'(?ms)^# DISTRIBUTION_TESTS_V4_START\n.*?^# DISTRIBUTION_TESTS_V4_END\n','',prior)
        prior=re.sub(r'(?ms)^    # DISTRIBUTION_TESTS_V4_START\n.*?^    # DISTRIBUTION_TESTS_V4_END\n','',prior)
        prior=re.sub(r'(?ms)^# GROUPED_STATISTICS_TESTS_V5_START\n.*?^# GROUPED_STATISTICS_TESTS_V5_END\n','',prior)
        prior=re.sub(r'(?ms)^    # GROUPED_STATISTICS_TESTS_V5_START\n.*?^    # GROUPED_STATISTICS_TESTS_V5_END\n','',prior)
        prior=re.sub(r'(?ms)^# SENSITIVITY_TESTS_V6_START\n.*?^# SENSITIVITY_TESTS_V6_END\n','',prior)
        prior=re.sub(r'(?ms)^    # SENSITIVITY_TESTS_V6_START\n.*?^    # SENSITIVITY_TESTS_V6_END\n','',prior)
        tests.write_text(prior,encoding='utf8')
        receipt=self.source/'design_receipt.json'
        data=json.loads(receipt.read_text())
        data['generator_capability_revision']='verified-summary-v3'
        receipt.write_text(json.dumps(data,sort_keys=True),encoding='utf8')
        maker.verify_recipe(self.source,minimum_tests=7)
        before=maker.source_digest(self.source,maker.inspect_recipe(self.source)[1])
        evolved=designer.evolve_recipe(self.name,self.recipes)
        self.assertTrue(evolved['changed'])
        self.assertEqual(evolved['previous_source_sha256'],before)
        self.assertIn('def calculate_distribution',calculator.read_text())
        self.assertIn('def calculate_sensitivity',calculator.read_text())
        self.assertIn('def calculate_distribution',
                      (self.source/'calculator.py').read_text())
        prior_source=Path(evolved['previous_source_retained'])
        self.assertNotIn('def calculate_distribution',
                         (prior_source/'calculator.py').read_text())
        self.assertGreaterEqual(evolved['measured_acceptance']['successful_tests'],9)
        self.assertFalse(designer.evolve_recipe(self.name,self.recipes)['changed'])
        self.assertFalse(evolved['commercial_release'])

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
