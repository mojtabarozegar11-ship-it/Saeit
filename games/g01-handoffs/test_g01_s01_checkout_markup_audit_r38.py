import unittest
from g01_s01_checkout_markup_audit_r38 import audit

class TestMarkup(unittest.TestCase):
    def test_valid(self):
        self.assertTrue(audit('<label for="email">Email</label><input id="email"><a href="/checkout/72/">Buy book</a>')['passed'])
    def test_missing_label_and_name(self):
        result=audit('<input id="email"><a href="/checkout/72/"></a>')
        self.assertFalse(result['passed'])
        self.assertIn('unlabelled_form_control',result['issues'])
        self.assertIn('unnamed_checkout',result['issues'])
    def test_external_and_unsafe(self):
        result=audit('<a href="javascript:alert(1)">Bad</a><a href="/checkout/72/" target="_blank">Buy</a>')
        self.assertIn('unsafe_or_empty_link',result['issues'])
        self.assertIn('external_tab_missing_noopener',result['issues'])

if __name__ == '__main__': unittest.main()
