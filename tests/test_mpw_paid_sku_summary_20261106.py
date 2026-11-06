"""Prove store sales rollups stay anonymous, scoped and evidence-aware."""

import ast
from pathlib import Path
import unittest


SOURCE = Path(__file__).resolve().parents[1] / "scripts/mpw_paid_provenance_readonly_20261105.py"


def load_summary_without_live_django():
    tree = ast.parse(SOURCE.read_text("utf-8"))
    nodes = [node for node in tree.body if (
        isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == "TRACKED_SKUS"
            for target in node.targets)
        or isinstance(node, ast.FunctionDef) and node.name == "tracked_sku_paid_summary"
    )]
    if len(nodes) != 2:
        raise AssertionError("Paid summary source contract changed")
    scope = {}
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(SOURCE), "exec"), scope)
    return scope["tracked_sku_paid_summary"]


class TrackedSkuPaidSummaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.summarize = staticmethod(load_summary_without_live_django())

    def test_two_walletless_paid_intents_only_appear_for_trial_sku(self):
        rows = [
            {"products": [779], "persisted_walletless_credit_verified": True,
             "fulfillment": {"ready": 1}, "products_truncated": False},
            {"products": [779], "persisted_walletless_credit_verified": True,
             "fulfillment": {"ready": 1}, "products_truncated": False},
        ]
        report = self.summarize(rows, 2)
        self.assertTrue(report["sample_complete"])
        self.assertEqual(report["paid_intents_containing_sku"],
                         {"72": 0, "225": 0, "779": 2, "879": 0})
        self.assertEqual(report["persisted_walletless_credit_intents_containing_sku"]["779"], 2)
        self.assertEqual(report["paid_intents_with_any_ready_fulfillment_containing_sku"]["779"], 2)
        self.assertFalse(report["independent_mainnet_payment_reverified"])
        self.assertFalse(report["authenticated_buyer_download_verified"])
        self.assertNotIn("email", str(report))

    def test_duplicate_product_in_one_intent_is_counted_once(self):
        rows = [{"products": [72, 72, 879, 999, True],
                 "persisted_walletless_credit_verified": False,
                 "fulfillment": {"ready": True}}]
        report = self.summarize(rows, 1)
        self.assertEqual(report["paid_intents_containing_sku"]["72"], 1)
        self.assertEqual(report["paid_intents_containing_sku"]["879"], 1)
        self.assertEqual(report["persisted_walletless_credit_intents_containing_sku"]["72"], 0)
        self.assertEqual(report["paid_intents_with_any_ready_fulfillment_containing_sku"]["72"], 0)

    def test_incomplete_samples_never_certify_global_zero_sales(self):
        report = self.summarize([{"products": [779]}], 105)
        self.assertFalse(report["sample_complete"])
        report = self.summarize([{"products": [72], "products_truncated": True}], 1)
        self.assertFalse(report["sample_complete"])


if __name__ == "__main__":
    unittest.main()
