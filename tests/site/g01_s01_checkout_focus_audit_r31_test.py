import importlib.util
from pathlib import Path
import unittest

SOURCE = Path(__file__).resolve().parents[2] / "games/g01-handoffs/g01_s01_checkout_focus_audit_r30.py"
spec = importlib.util.spec_from_file_location("g01_audit", SOURCE)
audit_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit_module)

class CheckoutFormActionTests(unittest.TestCase):
    def audit(self, attrs):
        return audit_module.audit('<button '+attrs+'>Buy now</button>', 'https://mojplaywin.com')
    def test_external_submit_override_is_flagged(self):
        result=self.audit('formaction="https://attacker.example/pay" type="submit"')
        self.assertIn('CTA_0_FORM_ACTION_OFF_ORIGIN',result['issues'])
    def test_script_submit_override_is_flagged(self):
        result=self.audit('formaction="javascript:alert(1)" type="submit"')
        self.assertIn('CTA_0_FORM_ACTION_OFF_ORIGIN',result['issues'])
    def test_protocol_relative_override_is_flagged(self):
        result=self.audit('formaction="//other.example/pay" type="submit"')
        self.assertIn('CTA_0_FORM_ACTION_OFF_ORIGIN',result['issues'])
    def test_same_origin_override_not_misclassified(self):
        result=self.audit('formaction="/store/123/checkout/" type="submit"')
        self.assertNotIn('CTA_0_FORM_ACTION_OFF_ORIGIN',result['issues'])
        self.assertIn('CTA_0_SUBMIT_REQUIRES_AUTHORIZED_STAGING_ONLY',result['issues'])
    def test_button_without_formaction_is_not_flagged_as_external(self):
        result=self.audit('type="button"')
        self.assertNotIn('CTA_0_FORM_ACTION_OFF_ORIGIN',result['issues'])
    def test_no_snapshot_text_in_output(self):
        result=self.audit('formaction="https://secret.example/customer-123"')
        self.assertNotIn('customer-123',str(result))
if __name__ == '__main__':
    unittest.main()
