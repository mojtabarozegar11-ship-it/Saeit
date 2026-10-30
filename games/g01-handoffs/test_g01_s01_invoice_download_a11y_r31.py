import unittest
from g01_s01_invoice_download_a11y_r31 import audit
class AuditTests(unittest.TestCase):
    def test_safe_receipt(self):
        self.assertEqual(audit('<main><h1>Invoice</h1><p role="status">Ready</p><a href="/account/invoices/42/download/">Download PDF</a></main>'),[])
    def test_reject_hidden_unnamed_and_external(self):
        e=audit('<h1>Invoice</h1><h1>Again</h1><a aria-hidden="true" href="https://evil.example/download?id=secret"></a>')
        for flag in ('H1_COUNT','NO_ACCESSIBLE_STATUS','HIDDEN_RECEIPT_LINK','UNNAMED_RECEIPT_LINK','EXTERNAL_OR_RELATIVE_RECEIPT_LINK'):self.assertIn(flag,e)
    def test_missing_receipt(self):
        self.assertIn('NO_RECEIPT_OR_DOWNLOAD_LINK',audit('<h1>Invoice</h1><p aria-live="polite">No file</p>'))
if __name__=='__main__':unittest.main()
