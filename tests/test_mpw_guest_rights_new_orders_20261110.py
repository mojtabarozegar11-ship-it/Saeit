"""Offline release-gate regression tests; do not call checkout or touch orders."""
import ast
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import unittest

ROOT = Path(__file__).resolve().parents[1]
GATE = ROOT / "mpw_guest_trx_20261020/guest_rights.py"
VIEW = ROOT / "mpw_guest_trx_20261020/guest_checkout_view.py"
DOWNLOAD = ROOT / "mpw_guest_trx_20261020/guest_download.py"

spec = importlib.util.spec_from_file_location("_mpw_guest_rights_test", GATE)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def eligible_product(sku=72, **overrides):
    metadata = {
        "asset_verified": True,
        "license_verified": True,
        "quality_approved": True,
        "factory_publication_permission": True,
        "checkout_enabled": True,
        "rights_review_status": "independently_cleared",
    }
    metadata.update(overrides.pop("metadata", {}))
    return SimpleNamespace(pk=sku, active=True, metadata=metadata, **overrides)


class GuestRightsNewOrdersOnly(unittest.TestCase):
    def test_both_books_require_explicit_clearance(self):
        self.assertTrue(module.may_start_new_order(eligible_product(72)))
        self.assertTrue(module.may_start_new_order(eligible_product(225)))

    def test_unrelated_products_cannot_use_this_legacy_invoice_path(self):
        for sku in (0, 779, 879, 999):
            with self.subTest(sku=sku):
                self.assertFalse(module.may_start_new_order(eligible_product(sku)))

    def test_missing_or_unverified_rights_status_is_fail_closed(self):
        for value in (None, "", "independent_evidence_pending", "pending_independent_review", True, 1):
            with self.subTest(value=value):
                item = eligible_product(metadata={"rights_review_status": value})
                self.assertFalse(module.may_start_new_order(item))

    def test_each_release_flag_must_be_exactly_true(self):
        for flag in module.REQUIRED_RELEASE_FLAGS:
            for value in (False, None, "true", 1):
                with self.subTest(flag=flag, value=value):
                    item = eligible_product(metadata={flag: value})
                    self.assertFalse(module.may_start_new_order(item))

    def test_no_product_inactive_or_non_mapping_metadata(self):
        self.assertFalse(module.may_start_new_order(None))
        self.assertFalse(module.may_start_new_order(SimpleNamespace(pk=72, active=False, metadata={})))
        for value in (None, [], "approved", True):
            with self.subTest(metadata=value):
                self.assertFalse(module.may_start_new_order(SimpleNamespace(pk=72, active=True, metadata=value)))

    def test_new_invoice_start_guard_dominates_issue_call(self):
        tree = ast.parse(VIEW.read_text("utf-8"))
        checkout = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "checkout")
        start_branch = next(node for node in ast.walk(checkout) if
            isinstance(node, ast.If) and
            isinstance(node.test, ast.Compare) and
            isinstance(node.test.left, ast.Name) and node.test.left.id == "action" and
            any(isinstance(c, ast.Constant) and c.value == "start" for c in node.test.comparators))
        guard = start_branch.body[0]
        self.assertIsInstance(guard, ast.If)
        self.assertIsInstance(guard.test, ast.UnaryOp)
        self.assertIsInstance(guard.test.op, ast.Not)
        self.assertIsInstance(guard.test.operand, ast.Call)
        self.assertEqual(guard.test.operand.func.id, "may_start_new_order")
        blocked_calls = [n for stmt in guard.body for n in ast.walk(stmt) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "issue"]
        allowed_calls = [n for stmt in guard.orelse for n in ast.walk(stmt) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "issue"]
        self.assertEqual(blocked_calls, [])
        self.assertEqual(allowed_calls, [])
        self.assertNotIn("from .guest_orders import issue", VIEW.read_text("utf-8"))
        self.assertIn("cannot bind your email", VIEW.read_text("utf-8"))

    def test_prior_paid_download_and_verification_are_not_new_invoice_gated(self):
        source = DOWNLOAD.read_text("utf-8")
        checkout_source = VIEW.read_text("utf-8")
        self.assertNotIn("may_start_new_order", source)
        self.assertIn('order["status"]!="paid"', source)
        self.assertIn('elif action=="verify"', checkout_source)
        self.assertIn("confirm(order,", checkout_source)

    def test_gate_is_pure_and_cannot_issue_or_download_files(self):
        source = GATE.read_text("utf-8")
        self.assertNotIn("issue(", source)
        self.assertNotIn("from django", source)
        self.assertNotIn("import django", source)
        self.assertNotIn("FileResponse", source)


if __name__ == "__main__":
    unittest.main()
