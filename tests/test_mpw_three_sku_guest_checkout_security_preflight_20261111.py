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
        self.assertFalse(report['buyer_email_before_invoice_source_indicators'])
        self.assertIsNone(report['commercial_email_block'])
        self.assertEqual(report['guest_email_policy'], 'no_buyer_email')
        self.assertFalse(report['guest_email_recovery_wiring_in_adapter'])
        self.assertEqual(report['email_based_recovery_end_to_end'], 'disabled_for_new_guest_orders')
        self.assertEqual(report['checkout_template_email_input'], 'not_examined')

    def test_unvalidated_email_capture_also_violates_no_email_policy(self):
        source = self.source.replace('def _new_user(request):',
            'def _new_user(request):\n    request.POST.get("buyer_email")\n    user.email = "unvalidated"')
        report = MODULE.audit_source(source)
        self.assertTrue(report['buyer_email_post_read_in_identity_source'])
        self.assertTrue(report['buyer_email_stored_in_identity_source'])
        self.assertFalse(report['buyer_email_before_invoice_source_indicators'])
        self.assertIsNotNone(report['commercial_email_block'])

    def test_validated_email_capture_still_violates_no_email_policy(self):
        helper = '''
def _submitted_purchase_email(request):
    from django.core.validators import validate_email
    posted = getattr(request, "POST", None)
    addresses = []
    for key in ("email", "buyer_email", "customer_email", "purchase_email", "purchaser_email"):
        for value in posted.getlist(key):
            validate_email(value)
            addresses.append(value)
    return addresses[0]
'''
        source = self.source.replace(
            '    _rate_limit(request)\n    Model = get_user_model()',
            '    submitted_email = _submitted_purchase_email(request)\n'
            '    _rate_limit(request)\n    Model = get_user_model()', 1)
        source = source.replace('    token = signing.dumps(',
                                '    user.email = submitted_email\n'
                                '    user.save(update_fields=["email"])\n'
                                '    token = signing.dumps(', 1)
        report = MODULE.audit_source(source + helper)
        self.assertTrue(report['buyer_email_validator_in_identity_source'])
        self.assertTrue(report['buyer_email_post_read_in_identity_source'])
        self.assertTrue(report['buyer_email_stored_in_identity_source'])
        self.assertTrue(report['buyer_email_before_invoice_source_indicators'])
        self.assertEqual(report['commercial_email_block'],
                         'GUEST_EMAIL_COLLECTION_OR_RECOVERY_WIRING')

    def test_unreachable_email_helper_never_clears_identity_gate(self):
        source = self.source + '''
def _unrelated_email_helper(request):
    from django.core.validators import validate_email
    validate_email(request.POST.get("email"))
    user.email = "not a checkout identity"
'''
        report = MODULE.audit_source(source)
        self.assertFalse(report['buyer_email_before_invoice_source_indicators'])
        self.assertIsNone(report['commercial_email_block'])

    def test_guest_recovery_import_in_adapter_is_rejected(self):
        altered = self.source.replace(
            'def patch_commercial(namespace):',
            'def patch_commercial(namespace):\n'
            '    from services.mpw_trx_email_recovery import bound_checkout')
        report = MODULE.audit_source(altered)
        self.assertTrue(report['guest_email_recovery_wiring_in_adapter'])
        self.assertEqual(report['commercial_email_block'],
                         'GUEST_EMAIL_COLLECTION_OR_RECOVERY_WIRING')

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
