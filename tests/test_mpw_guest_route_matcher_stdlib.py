"""Stdlib-only regression gate for guest checkout URL binding.

Run: python -m unittest discover -s tests -p test_mpw_guest_route_matcher_stdlib.py
Uses the production helper's AST directly, so Django and payment credentials
are not required. This does not replace full Django integration testing.
"""
import ast
import unittest
from pathlib import Path

SOURCE = Path(__file__).resolve().parents[1] / "services/mpw_trx_guest_commerce.py"
tree = ast.parse(SOURCE.read_text(encoding="utf-8"), filename=str(SOURCE))
helpers = [node for node in tree.body if isinstance(node, ast.FunctionDef)
           and node.name == "_route_action"]
if len(helpers) != 1:
    raise RuntimeError("Exactly one _route_action helper required")
scope = {}
exec(compile(ast.Module(body=helpers, type_ignores=[]), str(SOURCE), "exec"), scope)
_route_action = scope["_route_action"]


class GuestRouteMatcherTests(unittest.TestCase):
    def test_real_start_after_action(self):
        self.assertEqual(_route_action("/commerce/trx-easy/start/72/"), "start_order")

    def test_real_invoice_after_action(self):
        self.assertEqual(_route_action("/commerce/trx-easy/invoice/1/"), "show_invoice")

    def test_django_converter_after_action(self):
        for name, expected in (("start", "start_order"), ("invoice", "show_invoice"),
                               ("status", "invoice_status"), ("reconcile", "reconcile_invoice"),
                               ("download", "download_paid")):
            with self.subTest(name=name):
                self.assertEqual(_route_action(
                    f"/commerce/trx-easy/{name}/<int:product_id>/"), expected)

    def test_legacy_action_at_end(self):
        self.assertEqual(_route_action("/commerce/trx-easy/72/start/"), "start_order")

    def test_unrelated_purchases_not_rebound(self):
        self.assertIsNone(_route_action("/commerce/trx-easy/purchases/"))

    def test_foreign_help_untouched(self):
        self.assertIsNone(_route_action("/other-service/help/"))

    def test_foreign_start_is_rejected(self):
        with self.assertRaisesRegex(RuntimeError, "outside checkout"):
            _route_action("/other-service/start/")

    def test_nested_route_is_rejected(self):
        with self.assertRaisesRegex(RuntimeError, "Ambiguous"):
            _route_action("/commerce/trx-easy/72/start/archive/")

    def test_nonterminal_action_is_rejected(self):
        with self.assertRaisesRegex(RuntimeError, "Ambiguous"):
            _route_action("/commerce/trx-easy/start/archive/")

    def test_multi_action_is_rejected(self):
        with self.assertRaisesRegex(RuntimeError, "Ambiguous"):
            _route_action("/commerce/trx-easy/start/invoice/")

    def test_unsafe_identifiers_rejected(self):
        for bad in ("/commerce/trx-easy/start/0/",
                    "/commerce/trx-easy/start/admin/",
                    "/commerce/trx-easy/start/<path:foo>/",
                    "/commerce/trx-easy/start/<int:_a>/"):
            with self.subTest(route=bad), self.assertRaisesRegex(RuntimeError, "Ambiguous"):
                _route_action(bad)

    def test_malformed_routes_rejected(self):
        for bad in ("commerce/trx-easy/start/72/",
                    "/commerce//trx-easy/start/72/",
                    "/commerce/trx-easy/start/72/?a=1"):
            with self.subTest(route=bad), self.assertRaisesRegex(RuntimeError, "Malformed"):
                _route_action(bad)


if __name__ == "__main__":
    unittest.main()
