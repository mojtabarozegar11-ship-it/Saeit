"""Fail-closed source + pure-logic tests; never creates invoices or funds."""
import ast
from pathlib import Path
from types import SimpleNamespace
import unittest

from services.mpw_trx_commercial_context import rights_cleared_for_sale

ROOT = Path(__file__).resolve().parents[1]


def function_source(relative, function):
    source = (ROOT / relative).read_text(encoding="utf-8")
    tree = ast.parse(source, filename=relative)
    hits = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == function]
    if len(hits) != 1:
        raise AssertionError("Unexpected checkout handler topology")
    return ast.get_source_segment(source, hits[0])


class ExplicitRightsForSales(unittest.TestCase):
    def test_missing_or_non_boolean_rights_always_refused(self):
        for metadata in (
            None, [], "approved", {}, {"rights_cleared": False},
            {"rights_cleared": "true"}, {"rights_cleared": "approved"},
            {"rights_cleared": 1}, {"rights_cleared": []}
        ):
            with self.subTest(metadata=metadata):
                self.assertFalse(rights_cleared_for_sale(SimpleNamespace(metadata=metadata)))

    def test_rights_must_be_recorded_true(self):
        self.assertTrue(rights_cleared_for_sale(
            SimpleNamespace(metadata={"rights_cleared": True})))
        self.assertFalse(rights_cleared_for_sale(SimpleNamespace()))

    def test_public_catalog_checkout_and_invoice_all_enforce_gate(self):
        cases = (
            ("services/mpw_trx_public_pages.py", "public_shop", "rights_cleared_for_sale(p)"),
            ("services/mpw_trx_public_pages.py", "product_checkout", "rights_cleared_for_sale(product)"),
            ("services/mpw_trx_commercial_web.py", "_select_order", "rights_cleared_for_sale(product)"),
        )
        for path, function, needle in cases:
            with self.subTest(function=function):
                content = function_source(path, function)
                self.assertIn(needle, content)

    def test_existing_paid_download_and_order_recovery_remain_available(self):
        # New sale issuance is gated; older buyers must still be able to claim
        # a file after independent payment/accounting proof.
        for path, function in (
            ("services/mpw_trx_public_pages.py", "purchases"),
            ("services/mpw_trx_commercial_web.py", "_download_paid"),
            ("services/mpw_trx_commercial_web.py", "_reconcile_invoice"),
        ):
            with self.subTest(function=function):
                self.assertNotIn("rights_cleared_for_sale(", function_source(path, function))


if __name__ == "__main__":
    unittest.main()
