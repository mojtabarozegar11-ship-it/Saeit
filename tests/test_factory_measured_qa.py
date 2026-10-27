"""Execute deliberately invalid recipes and verify measurable admission gates."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'scripts' / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

maker = load('factory_product_maker')
warehouse = load('factory_production_warehouse')
customer = load('factory_verified_customer_cycle_20261021')

class MeasuredQualityTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.source = Path(self.tmp.name) / 'recipes' / 'sample_product'
        self.source.mkdir(parents=True)
        (self.source / 'README.md').write_text('# Sample product\n')

    def write_test(self, text):
        (self.source / 'test_product.py').write_text(text)

    def test_zero_tests_rejected_even_with_ok_log(self):
        self.write_test("import sys\nprint('OK', file=sys.stderr)\n")
        with self.assertRaisesRegex(RuntimeError, 'PRODUCT_QA_FAILED'):
            maker.verify_recipe(self.source)

    def test_all_skipped_rejected(self):
        self.write_test("import unittest\nclass T(unittest.TestCase):\n @unittest.skip('pending')\n def test_pending(self): pass\n")
        with self.assertRaisesRegex(RuntimeError, 'PRODUCT_QA_FAILED'):
            maker.verify_recipe(self.source)

    def test_expected_failure_is_not_successful_test(self):
        self.write_test("import unittest\nclass T(unittest.TestCase):\n @unittest.expectedFailure\n def test_pending(self): self.fail('pending')\n")
        with self.assertRaisesRegex(RuntimeError, 'PRODUCT_QA_FAILED'):
            maker.verify_recipe(self.source)

    def test_minimum_and_measurements(self):
        self.write_test("import unittest\nclass T(unittest.TestCase):\n def test_real(self): self.assertEqual(2+2,4)\n")
        evidence = {}
        maker.verify_recipe(self.source, evidence=evidence)
        self.assertEqual(evidence['successful_tests'], 1)
        self.assertEqual(evidence['tests_run'], 1)
        with self.assertRaisesRegex(RuntimeError, 'PRODUCT_QA_FAILED'):
            maker.verify_recipe(self.source, minimum_tests=2)

    def test_premature_exit_cannot_look_successful(self):
        self.write_test("import os\nos._exit(0)\n")
        with self.assertRaisesRegex(RuntimeError, 'MISSING_TEST_MEASUREMENTS'):
            maker.verify_recipe(self.source)

    def test_timeout_becomes_rework_compatible_failure(self):
        self.write_test("import time\ntime.sleep(5)\n")
        with self.assertRaisesRegex(RuntimeError, 'PRODUCT_QA_FAILED:TEST_TIMEOUT'):
            maker.verify_recipe(self.source, timeout=0.05)

    def test_source_modified_by_tests_is_rejected(self):
        self.write_test("import unittest\nfrom pathlib import Path\nclass T(unittest.TestCase):\n def test_mutation(self): Path('README.md').write_text('# changed')\n")
        with self.assertRaisesRegex(RuntimeError, 'SOURCE_CHANGED_DURING_TESTS'):
            maker.manufacture('sample_product', self.source.parent, Path(self.tmp.name)/'out')

    def test_legacy_cached_pass_requires_new_qa(self):
        self.write_test("import unittest\nclass T(unittest.TestCase):\n def test_real(self): pass\n")
        out = Path(self.tmp.name)/'out'
        maker.manufacture('sample_product', self.source.parent, out)
        manifest = out/'sample_product'/'manufacturing_manifest.json'
        doc = json.loads(manifest.read_text())
        doc.pop('qa_measurements')
        manifest.write_text(json.dumps(doc))
        result = maker.manufacture('sample_product', self.source.parent, out)
        self.assertFalse(result['changed'])
        self.assertTrue(result['qa_refreshed'])
        self.assertEqual(json.loads(manifest.read_text())['qa_measurements']['successful_tests'],1)

    def test_nested_package_enters_warehouse(self):
        self.write_test("import unittest\nclass T(unittest.TestCase):\n def test_real(self): pass\n")
        (self.source/'assets').mkdir()
        (self.source/'assets'/'data.json').write_text('{}')
        root = Path(self.tmp.name)/'private'
        maker.manufacture('sample_product', self.source.parent, root/'digital-products')
        receipt = customer.inspect_product(root/'digital-products'/'sample_product', 'sample_product')
        customer.persist_pending(root, receipt)
        artifact, manifest = warehouse.inspect_source(root, 'sample_product')
        self.assertTrue(artifact.is_file())
        self.assertIn('assets/data.json', manifest['files'])

    def test_unsafe_member_names_rejected(self):
        for name in ('../a', '/a', 'a//b', 'a/../b', 'a/./b', 'a\\b', '', 'a/'):
            with self.subTest(name=name):
                self.assertFalse(warehouse.safe_member_name(name))
        self.assertTrue(warehouse.safe_member_name('assets/data.json'))

class DiscoveryIsolationTests(unittest.TestCase):
    def test_bad_recipe_does_not_hide_good_recipe(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            good = root/'good_recipe'
            good.mkdir()
            (good/'README.md').write_text('# Good')
            (good/'test_real.py').write_text('import unittest')
            (root/'broken_recipe').mkdir()
            errors = []
            found = maker.discover_recipes(root, errors=errors)
            self.assertEqual(list(found), ['good_recipe'])
            self.assertEqual(errors[0]['recipe'], 'broken_recipe')
            with self.assertRaises(RuntimeError):
                maker.discover_recipes(root)

class RecipeInventoryReplacementTests(unittest.TestCase):
    def test_removed_and_changed_sources_quarantined_without_touching_goods(self):
        import os
        import shutil
        import subprocess
        import sys
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            repo = root/'checkout'
            stage = root/'runtime'
            scripts = stage/'scripts'
            scripts.mkdir(parents=True)
            shutil.copy(ROOT/'scripts'/'factory_product_maker.py', scripts)
            old = stage/'product_recipes'
            (old/'retired_recipe').mkdir(parents=True)
            (old/'retired_recipe'/'precious.txt').write_text('retain me')
            new = repo/'product_recipes'/'new_recipe'
            new.mkdir(parents=True)
            (new/'README.md').write_text('# New')
            (new/'test_real.py').write_text('import unittest')
            ops = root/'ops'
            (ops/'backups').mkdir(parents=True)
            goods = root/'finished.zip'
            goods.write_bytes(b'existing artifact')
            installer = (ROOT/'deploy'/'install_autonomous_factory_products.sh').read_text()
            block = installer.split('incoming="$(mktemp',1)[1].split('# Verify the exact reviewed flagship',1)[0]
            block = 'incoming="$(mktemp' + block
            env = dict(os.environ, repo=str(repo), stage=str(stage), scripts=str(scripts),
                       recipes=str(old), ops=str(ops), python=sys.executable, stamp='test')
            result = subprocess.run(['bash','-euc',block], env=env, capture_output=True, text=True)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertFalse((old/'retired_recipe').exists())
            self.assertTrue((old/'new_recipe'/'README.md').is_file())
            self.assertEqual((ops/'backups'/'product-recipes-before-test'/'retired_recipe'/'precious.txt').read_text(),'retain me')
            self.assertEqual(goods.read_bytes(),b'existing artifact')
