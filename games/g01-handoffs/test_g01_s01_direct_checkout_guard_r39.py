import importlib.util
import unittest
from pathlib import Path

p = Path(__file__).with_name('g01_s01_direct_checkout_guard_r39.py')
spec = importlib.util.spec_from_file_location('checkout_guard', p)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

class CheckoutGuardTests(unittest.TestCase):
    def test_direct_and_registration_next(self):
        html = '<a href="/accounts/register/?next=/store/product/72/checkout/">Register</a><a href="/store/product/72/checkout/">Buy</a>'
        self.assertTrue(mod.audit(html, '72')['passed'])
        self.assertEqual(mod.audit(html, '72')['direct_checkout_count'], 1)
    def test_wrong_sku_fails(self):
        self.assertIn('wrong_sku_direct_checkout', mod.audit('<a href="/store/product/225/checkout/">Buy</a>', '72')['issues'])
    def test_cross_origin_fails(self):
        self.assertIn('cross_origin_checkout', mod.audit('<a href="https://evil.example/store/product/72/checkout/">Buy</a>', '72')['issues'])
    def test_protocol_relative_cross_origin_fails(self):
        self.assertIn('cross_origin_checkout', mod.audit('<a href="//evil.example/store/product/72/checkout/">Buy</a>', '72')['issues'])
    def test_missing_direct_fails(self):
        self.assertIn('expected_direct_checkout_missing', mod.audit('<a href="/accounts/register/?next=/store/product/72/checkout/">Register</a>', '72')['issues'])
    def test_duplicate_direct_fails(self):
        self.assertIn('direct_checkout_count_not_one', mod.audit('<a href="/store/product/72/checkout/">Buy</a><a href="/store/product/72/checkout/">Again</a>', '72')['issues'])
    def test_query_direct_fails(self):
        self.assertIn('direct_checkout_has_query_or_fragment', mod.audit('<a href="/store/product/72/checkout/?debug=1">Buy</a>', '72')['issues'])

if __name__ == '__main__':
    unittest.main()
