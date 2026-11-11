"""Offline, non-transactional checks for the exact guest checkout security route."""
import importlib.util
from pathlib import Path
import unittest


BASE = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    'mpw_guest_security_preflight',
    BASE / 'scripts/mpw_three_sku_guest_checkout_security_preflight_20261111.py')
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class GuestCheckoutSecurityTests(unittest.TestCase):
    def setUp(self):
        self.source = (BASE / 'services/mpw_trx_guest_commerce.py').read_text('utf8')

    def test_actual_guest_checkout_source_has_strict_protections(self):
        report = MODULE.audit_source(self.source)
        self.assertTrue(report['strict_guest_csp'])
        self.assertTrue(report['rights_gate_checked'])
        self.assertEqual(report['orders_created'], 0)

    def test_missing_rights_gate_fails_closed(self):
        changed = self.source.replace('rights_cleared_for_sale(product)', 'True')
        with self.assertRaisesRegex(RuntimeError, 'rights_cleared_for_sale'):
            MODULE.audit_source(changed)

    def test_rights_function_called_without_denial_is_not_sufficient(self):
        changed = self.source.replace(
            'or not rights_cleared_for_sale(product):',
            'or rights_cleared_for_sale(product):')
        with self.assertRaisesRegex(RuntimeError, 'RIGHTS_DENIAL_GUARD'):
            MODULE.audit_source(changed)

    def test_unsafe_csp_fails_closed(self):
        changed = self.source.replace("script-src 'none'", "script-src 'self' 'unsafe-inline'")
        with self.assertRaisesRegex(RuntimeError, 'CSP_SECURITY_DIRECTIVES'):
            MODULE.audit_source(changed)

    def test_duplicate_handler_fails_closed(self):
        changed = self.source + '\ndef _checkout_page(request, product_id, pages_namespace):\n    return None\n'
        with self.assertRaisesRegex(RuntimeError, 'MISSING_OR_DUPLICATED'):
            MODULE.audit_source(changed)

    def test_dynamic_csp_fails_closed(self):
        changed = self.source.replace(
            'response["Content-Security-Policy"] = (',
            'response["Content-Security-Policy"] = str(',
        )
        with self.assertRaisesRegex(RuntimeError, 'NOT_STATIC_AND_AUDITABLE'):
            MODULE.audit_source(changed)


if __name__ == '__main__':
    unittest.main()
