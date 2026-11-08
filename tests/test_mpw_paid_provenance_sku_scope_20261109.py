"""Offline contract for trial/nontrial paid-provenance classification.

Extract only the pure function AST: never import live Django, inspect a
customer table, contact a chain provider, or read a runtime credential.
"""
from __future__ import annotations

import ast
import unittest
from pathlib import Path


PATH = Path(__file__).resolve().parents[1] / "scripts/mpw_paid_provenance_readonly_20261105.py"
parsed = ast.parse(PATH.read_text(encoding="utf-8"))
function = next(
    node for node in parsed.body
    if isinstance(node, ast.FunctionDef) and node.name == "paid_sku_scope"
)
namespace = {}
exec(compile(ast.Module(body=[function], type_ignores=[]), str(PATH), "exec"), namespace)
scope = namespace["paid_sku_scope"]


class PaidSkuScopeTests(unittest.TestCase):
    def test_historical_micro_trial_never_counts_as_nontrial_sale(self):
        self.assertEqual(scope([779], (72, 225, 779, 879)), "historical_trial_779")

    def test_mixed_cart_with_trial_is_separate(self):
        self.assertEqual(scope([72, 779], (72, 225, 879, 779)), "mixed_with_trial_779")

    def test_current_public_nontrial_sku_is_distinguished(self):
        self.assertEqual(scope([72], (72, 225, 879)), "configured_nontrial_public_sku")

    def test_current_public_multi_product_order_is_distinguished(self):
        self.assertEqual(scope([225, 879], (72, 225, 879)), "configured_nontrial_public_sku")

    def test_unpublished_sku_is_not_counted_as_public(self):
        self.assertEqual(scope([999], (72, 225, 879)), "outside_configured_public_sku")

    def test_missing_allowlist_is_unknown_not_eligible(self):
        self.assertEqual(scope([72], None), "public_allowlist_unavailable")

    def test_invalid_or_boolean_allowlist_is_unknown(self):
        self.assertEqual(scope([72], (72, True)), "public_allowlist_unavailable")

    def test_no_product_cannot_be_a_commercial_sale(self):
        self.assertEqual(scope([], (72, 225, 879)), "no_valid_products")

    def test_invalid_product_id_cannot_be_a_commercial_sale(self):
        self.assertEqual(scope([0], (72, 225, 879)), "no_valid_products")


if __name__ == "__main__":
    unittest.main()
