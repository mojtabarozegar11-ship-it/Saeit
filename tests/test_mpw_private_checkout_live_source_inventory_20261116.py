"""Isolated offline checks: never touch the hosting root or use buyer data."""
from pathlib import Path
import importlib.util
import tempfile
import unittest

SOURCE = Path(__file__).resolve().parents[1] / 'scripts/mpw_private_checkout_live_source_inventory_20261116.py'
spec = importlib.util.spec_from_file_location('mpw_inventory', SOURCE)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class InventoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / 'fixture_checkout_root'
        self.root.mkdir()

    def tearDown(self):
        self.temp.cleanup()

    def write(self, relative, source):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(source, encoding='utf-8')
        return path

    def test_empty_fixture_does_not_claim_real_modules(self):
        r = module.inspect_root(self.root)
        self.assertTrue(r['root_valid'])
        self.assertFalse(r['four_customer_view_sources_present'])
        self.assertFalse(r['four_customer_view_exports_present'])

    def test_excludes_unknown_host_root(self):
        self.assertFalse(module.inspect_root(Path(self.temp.name))['root_valid'])

    def test_reports_exact_named_views(self):
        self.write('mpw_commerce/product_checkout_page.py', 'def product_checkout_page(request): pass\n')
        r = module.inspect_module(self.root, 'mpw_commerce/product_checkout_page.py', ('product_checkout_page',))
        self.assertTrue(all((r['present'], r['regular'], r['parseable'], r['exports_present'])))
        self.assertEqual(len(r['sha256']), 64)

    def test_reports_nonmatching_view(self):
        self.write('mpw_commerce/product_checkout_page.py', 'def wrong(): pass\n')
        r = module.inspect_module(self.root, 'mpw_commerce/product_checkout_page.py', ('product_checkout_page',))
        self.assertTrue(r['parseable'])
        self.assertFalse(r['exports_present'])

    def test_partial_exports_cannot_pass(self):
        self.write('mpw_commerce/checkout_views.py', 'def checkout_invoice(): pass\n')
        r = module.inspect_module(self.root, 'mpw_commerce/checkout_views.py', module.EXPECTED['mpw_commerce/checkout_views.py'])
        self.assertFalse(r['exports_present'])

    def test_rename_import_alias_recognized_without_execution(self):
        self.write('mpw_commerce/purchase_history.py', 'from .safe import purchases as purchased_downloads\n')
        self.assertTrue(module.inspect_module(self.root, 'mpw_commerce/purchase_history.py', ('purchased_downloads',))['exports_present'])

    def test_invalid_python_denies_parse(self):
        self.write('mpw_commerce/urls.py', 'def invalid(:\n')
        self.assertFalse(module.inspect_module(self.root, 'mpw_commerce/urls.py', ('urlpatterns',))['parseable'])

    def test_invalid_utf8_denies_parse(self):
        p = self.write('mpw_commerce/urls.py', 'urlpatterns=[]')
        p.write_bytes(b'\xff\xfe')
        self.assertFalse(module.inspect_module(self.root, 'mpw_commerce/urls.py', ('urlpatterns',))['parseable'])

    def test_oversize_denies_read(self):
        self.write('mpw_commerce/urls.py', 'x' * (module.MAX_BYTES + 3))
        r = module.inspect_module(self.root, 'mpw_commerce/urls.py', ('urlpatterns',))
        self.assertFalse(r['regular'])
        self.assertIsNone(r['sha256'])

    def test_symlink_file_rejected(self):
        outside = Path(self.temp.name) / 'outside.py'
        outside.write_text('def product_checkout_page(): pass\n')
        target = self.root / 'mpw_commerce/product_checkout_page.py'
        target.parent.mkdir()
        target.symlink_to(outside)
        self.assertFalse(module.inspect_module(self.root, 'mpw_commerce/product_checkout_page.py', ('product_checkout_page',))['present'])

    def test_symlink_parent_rejected(self):
        outside = Path(self.temp.name) / 'other'
        outside.mkdir()
        (outside / 'checkout_views.py').write_text('def checkout_invoice(): pass')
        (self.root / 'mpw_commerce').symlink_to(outside, target_is_directory=True)
        self.assertFalse(module.inspect_module(self.root, 'mpw_commerce/checkout_views.py', ('checkout_invoice',))['present'])

    def test_returns_only_bounded_source_metadata(self):
        self.write('mpw_commerce/policy.py', 'SECRET="test-only"\ndef order_snapshot(): pass\nclass CommercePolicyError(Exception): pass')
        result = module.inspect_root(self.root)
        serialized = repr(result)
        self.assertNotIn('test-only', serialized)
        self.assertFalse(result['application_modules_imported'])
        self.assertFalse(result['payment_or_invoice_created'])
        self.assertFalse(result['customer_data_read'])
        self.assertFalse(result['host_changed'])


if __name__ == '__main__':
    unittest.main()
