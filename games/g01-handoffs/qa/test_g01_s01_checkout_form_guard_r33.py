import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from g01_s01_checkout_form_guard_r33 import FormAudit

class CheckoutFormGuardR33(unittest.TestCase):
    def audit(self,html):
        parser=FormAudit();parser.feed(html);return parser.audit()
    def test_safe_labeled_get(self):
        r=self.audit('<form action="/search"><label for="q">Search</label><input id="q"></form>')
        self.assertEqual(r['issue_counts'],{})
    def test_sensitive_unlabelled_get(self):
        r=self.audit('<form><input type="email" name="email"></form>')
        self.assertEqual(r['issue_counts']['UNLABELLED_FORM_CONTROL'],1)
        self.assertEqual(r['issue_counts']['SENSITIVE_FIELD_IN_GET_FORM'],1)
    def test_post_requires_manual_staging(self):
        r=self.audit('<form method="POST"><label>Email <input type="email"></label></form>')
        self.assertEqual(r['issue_counts'],{'POST_REQUIRES_AUTHENTICATED_STAGING_NO_SUBMIT':1})
        self.assertEqual(r['submissions'],0)
    def test_insecure_action_rejected(self):
        r=self.audit('<form action="javascript:alert(1)"><input aria-label="x"></form><form action="http://example.test"><input aria-label="y"></form>')
        self.assertEqual(r['issue_counts']['UNSAFE_ACTION_SCHEME'],1)
        self.assertEqual(r['issue_counts']['INSECURE_HTTP_ACTION'],1)
    def test_never_discloses_values(self):
        r=self.audit('<form><input value="PRIVATE CUSTOMER" aria-label="name"></form>')
        self.assertNotIn('PRIVATE CUSTOMER',str(r))

if __name__=='__main__':unittest.main()
