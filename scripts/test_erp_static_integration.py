#!/usr/bin/env python3
"""Ensure optional ERP modules remain wired behind existing auth/CSRF routes."""
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parent.parent

class IntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=(ROOT/'content/zomorod-business/app.php').read_text()
        cls.html=(ROOT/'content/zomorod-business/index.php').read_text()
    def test_private_optional_imports_and_routes(self):
        for module,page in [('industry_operations.php','industry_ops'),('finance_audit.php','finance_audit')]:
            self.assertEqual(self.app.count(f"is_file($private.'/{module}')"),1)
            self.assertIn(f"$page==='{page}'",self.app)
    def test_finance_separate_access(self):
        i=self.app.index("$page==='finance_audit'")
        self.assertIn("authorize('account')",self.app[i:i+270])
    def test_posts_remain_csrf_gated(self):
        i=self.app.index('if($post){')
        self.assertIn('verifyCsrf();',self.app[i:i+60])
        self.assertIn("'industry_create'",self.app)
        self.assertIn("'industry_advance'",self.app)
    def test_read_only_audit_implementation(self):
        s=(ROOT/'content/zomorod-business/finance_audit.php').read_text()
        for term in ('DELETE FROM','INSERT INTO','UPDATE journal_entries','UPDATE invoices'):
            self.assertNotIn(term,s)
        self.assertIn('PRAGMA foreign_key_check',s)
        self.assertIn('SUM(debit)',s)
    def test_payment_and_inventory_safe_rollback(self):
        payment=self.app[self.app.index("$action==='payment'"):self.app.index("$action==='inventory'")]
        stock=self.app[self.app.index("$action==='stock'"):self.app.index("$action==='employee'")]
        for block in (payment,stock):
            self.assertIn('beginTransaction()',block)
            self.assertIn('inTransaction()',block)
            self.assertIn('rollBack()',block)
            self.assertIn('commit()',block)
    def test_public_entrypoint_separate(self):
        self.assertIn("/.private/zomorod-business/app.php", self.html)
        self.assertNotIn('company-workflow.sqlite3',self.html)
        self.assertNotIn('industry-operations.sqlite3',self.html)

if __name__=='__main__':unittest.main(verbosity=2)
