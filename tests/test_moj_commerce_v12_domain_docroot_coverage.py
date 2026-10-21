"""Synthetic-only tests for cPanel domain backup coverage classification."""
import unittest
from tools.moj_commerce_v12_domain_docroot_coverage import report_from_payload

class DomainCoverageTests(unittest.TestCase):
    def test_names_redacted_outside_docroot_not_certified(self):
        raw={'result':{'status':1,'data':{'main_domain':{
            'domain':'www.private.example', 'documentroot':'/home/zomorod2/mojplaywin.com'},
            'addon_domains':[{'domain':'secret.invalid','documentroot':'/home/zomorod2/another-site'}]}}}
        result=report_from_payload(raw)
        self.assertEqual(result['domains_with_docroot'],2)
        self.assertEqual(result['roots_in_known_backup_scope'],1)
        self.assertEqual(result['roots_outside_known_backup_scope'],1)
        self.assertFalse(result['all_docroots_in_backed_roots'])
        self.assertFalse(result['complete_tenant_backup_verified'])
        self.assertFalse(result['payment_release_allowed'])
        self.assertNotIn('secret.invalid',repr(result))
        self.assertNotIn('www.private.example',repr(result))

    def test_all_docroots_in_scope_does_not_establish_entire_backup(self):
        x={'result':{'status':1,'data':{'main_domain':{
            'documentroot':'/home/zomorod2/mojplaywin.com'}}}}
        r=report_from_payload(x)
        self.assertTrue(r['all_docroots_in_backed_roots'])
        self.assertFalse(r['complete_tenant_backup_verified'])

    def test_no_data_fails_closed(self):
        result=report_from_payload({'result':{'status':0}})
        self.assertFalse(result['all_docroots_in_backed_roots'])
        self.assertFalse(result['payment_release_allowed'])

if __name__ == '__main__':unittest.main()
