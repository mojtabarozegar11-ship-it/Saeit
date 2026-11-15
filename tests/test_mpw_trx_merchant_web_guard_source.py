"""Source-level regression: commercial endpoints must not bypass merchant ownership.

Pure, read-only check only. Real Django and payment integration must also pass
before release. This file does not publish, charge, send email or access RPC.
"""
from pathlib import Path
import ast
import unittest

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "services/mpw_trx_commercial_web.py"
BINDING = ROOT / "services/mpw_trx_merchant_binding.py"


class MerchantSourceIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = WEB.read_text(encoding="utf-8")
        cls.binding = BINDING.read_text(encoding="utf-8")
        tree = ast.parse(cls.source)
        cls.functions = {
            node.name: ast.get_source_segment(cls.source, node)
            for node in tree.body if isinstance(node, ast.FunctionDef)
        }

    def test_pending_invoice_lookup_validates_active_merchant(self):
        source = self.functions["_select_order"]
        self.assertIn("require_current_merchant_for_invoice(", source)
        self.assertIn("merchant_domain, claim", source)
        self.assertIn("except MerchantBindingRejected:", source)
        self.assertIn("continue", source)

    def test_owner_invoice_query_rejects_other_merchant_host(self):
        source = self.functions["_get_owner_invoice"]
        self.assertIn("require_same_invoice_host(", source)
        self.assertIn("request.get_host()", source)
        self.assertIn("raise Http404(", source)

    def test_paid_status_reconcile_and_download_all_pass_same_owner_gate(self):
        for name in ("_show_invoice", "_invoice_status", "_reconcile_invoice",
                     "_download_paid"):
            with self.subTest(endpoint=name):
                self.assertIn("_get_owner_invoice(request,invoice_id)",
                              self.functions[name])

    def test_merchant_registry_is_not_inferred_from_client_header(self):
        self.assertIn("MPW_TRX_MERCHANT_BINDINGS", self.binding)
        self.assertIn("record.get(\"enabled\") is not True", self.binding)
        self.assertIn("configured_recipient != recipient", self.binding)


if __name__ == "__main__":
    unittest.main()
