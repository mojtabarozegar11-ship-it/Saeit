import unittest
from g01_s01_checkout_accessibility_gate_r46 import audit_html


class OfflineGateTests(unittest.TestCase):
    def test_good_checkout_markup(self):
        html = '<form action="/checkout/"><label for="email">Email</label><input id="email"><button>Review order</button><a href="/invoices/">Invoices</a><img src="x" alt=""></form>'
        self.assertEqual(audit_html(html)['status'], 'PASS')

    def test_unlabeled_action(self):
        self.assertIn('button missing accessible name', audit_html('<button><span></span></button>')['issues'])

    def test_bad_anchor(self):
        self.assertIn('anchor has empty/placeholder href', audit_html('<a href="#">Download</a>')['issues'])

    def test_bad_form_action(self):
        self.assertIn('unsafe form action', audit_html('<form action="javascript:alert(1)"></form>')['issues'])

    def test_missing_alt(self):
        self.assertIn('img missing alt text (empty alt is valid for decoration)', audit_html('<img src="x">')['issues'])


if __name__ == '__main__':
    unittest.main()
