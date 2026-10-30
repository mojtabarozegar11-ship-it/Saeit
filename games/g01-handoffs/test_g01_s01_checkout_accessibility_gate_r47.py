import unittest
from g01_s01_checkout_accessibility_gate_r47 import audit_html


class AuditTests(unittest.TestCase):
    def test_explicit_label(self):
        self.assertEqual(audit_html('<label for="e">Email</label><input id="e"><button><span>Pay later</span></button>')['status'], 'PASS')

    def test_id_without_label_is_not_accessible(self):
        self.assertIn('input missing associated label/accessible name', audit_html('<input id="email">')['issues'])

    def test_implicit_label(self):
        self.assertEqual(audit_html('<label>Email <input></label>')['status'], 'PASS')

    def test_aria_label(self):
        self.assertEqual(audit_html('<input aria-label="Email">')['status'], 'PASS')

    def test_unlabeled_select(self):
        self.assertIn('select missing associated label/accessible name', audit_html('<select><option>One</option></select>')['issues'])

    def test_nested_accessible_name(self):
        self.assertEqual(audit_html('<button>Save <span><strong>invoice</strong></span></button>')['status'], 'PASS')

    def test_bad_anchor(self):
        self.assertIn('anchor has placeholder href', audit_html('<a href="#">Download</a>')['issues'])

    def test_unsafe_form(self):
        self.assertIn('unsafe form action', audit_html('<form action="javascript:alert(1)"></form>')['issues'])

    def test_decorative_image_alt(self):
        self.assertEqual(audit_html('<img src="x" alt="">')['status'], 'PASS')

    def test_missing_image_alt(self):
        self.assertIn('img missing alt', audit_html('<img src="x">')['issues'])


if __name__ == '__main__':
    unittest.main()
