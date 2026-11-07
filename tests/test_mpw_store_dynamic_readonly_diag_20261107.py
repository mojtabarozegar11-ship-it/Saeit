"""Local-only redaction checks, no Django or production connections."""
import json, unittest
from scripts.mpw_store_dynamic_readonly_diag_20261107 import safe_error

class SafeDiagnosticTests(unittest.TestCase):
    def test_no_exception_message_or_buyer_data_in_output(self):
        result=safe_error("django_setup",ValueError("secret buyer address"))
        payload=json.dumps(result)
        self.assertEqual(result["exception_class"],"ValueError")
        self.assertNotIn("secret buyer address",payload)
        self.assertFalse(result["payments_created"])
        self.assertFalse(result["source_mutated"])

if __name__=="__main__": unittest.main()
