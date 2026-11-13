"""Offline verification of MojPlayWin paid intent SKU scope classification.

No Django setup, database, blockchain connection, customer data or funds.
"""
import ast
from pathlib import Path
import unittest

SOURCE = (Path(__file__).resolve().parents[1]
          / "scripts/mpw_paid_provenance_readonly_20261105.py")
tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
definitions = [n for n in tree.body if isinstance(n, ast.FunctionDef)
               and n.name == "paid_sku_scope"]
assert len(definitions) == 1
namespace = {}
exec(compile(ast.Module(body=definitions, type_ignores=[]), str(SOURCE), "exec"),
     namespace)
scope = namespace["paid_sku_scope"]


class ProvenanceScopeTests(unittest.TestCase):
    def test_trial_never_nontrial(self):
        self.assertEqual(scope([779], [72, 225, 779]), "historical_trial_779")

    def test_mixed_trial_never_nontrial(self):
        self.assertEqual(scope([72, 779], [72, 225]), "mixed_with_trial_779")

    def test_allowed_nontrial(self):
        self.assertEqual(scope([72, 225], [72, 225, 879, 779]),
                         "configured_nontrial_public_sku")

    def test_nonpublic_is_not_commercial(self):
        self.assertEqual(scope([72, 404], [72, 225, 879]),
                         "other_or_unconfigured_sku")

    def test_missing_config_unknown_not_sale(self):
        self.assertEqual(scope([72], None), "configured_public_skus_unknown")

    def test_empty_products_unknown(self):
        self.assertEqual(scope([], [72]), "no_valid_products")

    def test_bool_cannot_masquerade_as_int_id(self):
        self.assertEqual(scope([True], [72]), "no_valid_products")
        self.assertEqual(scope([72], [True]), "configured_public_skus_unknown")

    def test_empty_allowlist_unknown(self):
        self.assertEqual(scope([72], []), "configured_public_skus_unknown")

    def test_no_paid_claim_in_source_contract(self):
        source = SOURCE.read_text(encoding="utf-8")
        self.assertIn('"confirmed_current_commercial_sales": None', source)
        self.assertIn('"independent_mainnet_recheck_performed": False', source)
        self.assertIn('"customer_download_e2e_performed": False', source)


if __name__ == "__main__":
    unittest.main()
