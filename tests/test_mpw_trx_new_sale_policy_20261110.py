"""Offline contracts for the true guest TRX start route; no orders or mail."""
import ast
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import unittest

ROOT = Path(__file__).resolve().parents[1]
POLICY = ROOT / "services/mpw_trx_new_sale_policy.py"
ADAPTER = ROOT / "services/mpw_trx_guest_commerce.py"
PAID = ROOT / "mpw_guest_trx_20261020/guest_download.py"

spec = importlib.util.spec_from_file_location("_mpw_new_sale_policy_test", POLICY)
policy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(policy)


def product(sku=72, *, active=True, updates=None):
    metadata = {
        "asset_verified": True,
        "license_verified": True,
        "quality_approved": True,
        "factory_publication_permission": True,
        "checkout_enabled": True,
        "rights_cleared": True,
        "publication_approved": True,
        "rights_review_status": "independently_cleared",
    }
    metadata.update(updates or {})
    return SimpleNamespace(pk=sku, active=active, metadata=metadata)


class NewSaleRightsPolicyTests(unittest.TestCase):
    def test_each_public_offer_requires_independent_status(self):
        for sku in (72, 225, 879):
            with self.subTest(sku=sku):
                self.assertTrue(policy.reviewed_for_new_sale(product(sku)))

    def test_any_unrelated_sku_is_blocked(self):
        for sku in (0, 50, 779, 880, 999, None):
            with self.subTest(sku=sku):
                self.assertFalse(policy.reviewed_for_new_sale(product(sku)))

    def test_pending_review_never_passes(self):
        for value in (None, "", "pending", "independent_evidence_pending", True, 1):
            with self.subTest(value=value):
                self.assertFalse(policy.reviewed_for_new_sale(
                    product(updates={"rights_review_status": value})))

    def test_every_flag_must_be_exact_true(self):
        for flag in policy.REQUIRED_FLAGS:
            for value in (False, None, 1, "true"):
                with self.subTest(flag=flag, value=value):
                    self.assertFalse(policy.reviewed_for_new_sale(
                        product(updates={flag: value})))

    def test_nonexistent_or_inactive_product_never_passes(self):
        self.assertFalse(policy.reviewed_for_new_sale(None))
        self.assertFalse(policy.reviewed_for_new_sale(product(active=False)))

    def test_non_dictionary_metadata_fails_closed(self):
        for data in (None, "reviewed", [], True):
            with self.subTest(data=data):
                self.assertFalse(policy.reviewed_for_new_sale(
                    SimpleNamespace(pk=72, active=True, metadata=data)))

    def test_helper_has_no_payment_or_django_side_effects(self):
        source = POLICY.read_text("utf8")
        for forbidden in ("issue(", "create_order(", "FileResponse", "from django", "import django"):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, source)

    def test_checkout_page_and_invoice_start_use_shared_policy(self):
        source = ADAPTER.read_text("utf8")
        tree = ast.parse(source)
        funcs = {node.name: node for node in tree.body
                 if isinstance(node, ast.FunctionDef)}
        checker = ast.get_source_segment(source, funcs["_require_new_sale_rights"])
        checkout = ast.get_source_segment(source, funcs["_checkout_page"])
        dispatch = ast.get_source_segment(source, funcs["_dispatch"])
        self.assertIn("reviewed_for_new_sale(product)", checker)
        self.assertIn("rights_cleared_for_sale(product)", checker)
        self.assertIn("_eligible(product)", checker)
        self.assertIn("_require_new_sale_rights(product_id)", checkout)
        self.assertIn("if require_new_sale:", dispatch)
        self.assertIn("_require_new_sale_rights(product_id)", dispatch)

    def test_start_gate_precedes_existing_authoritative_invoice_handler(self):
        tree = ast.parse(ADAPTER.read_text("utf8"))
        dispatch = next(node for node in tree.body
                        if isinstance(node, ast.FunctionDef) and node.name == "_dispatch")
        guard = next(node for node in dispatch.body
                     if isinstance(node, ast.If)
                     and isinstance(node.test, ast.Name)
                     and node.test.id == "require_new_sale")
        target = next(node for node in ast.walk(guard)
                      if isinstance(node, ast.Call)
                      and isinstance(node.func, ast.Name)
                      and node.func.id == "_require_new_sale_rights")
        invoice = next(node for node in ast.walk(dispatch)
                       if isinstance(node, ast.Call)
                       and isinstance(node.func, ast.Name)
                       and node.func.id == "view")
        self.assertLess(target.lineno, invoice.lineno)

    def test_only_start_order_sets_new_sale_flag(self):
        source = ADAPTER.read_text("utf8")
        tree = ast.parse(source)
        calls = [node for node in ast.walk(tree)
                 if isinstance(node, ast.Call)
                 and isinstance(node.func, ast.Name)
                 and node.func.id == "_dispatch"]
        guarded = [node for node in calls
                   if any(k.arg == "require_new_sale" for k in node.keywords)]
        self.assertEqual(len(guarded), 1)
        kw = next(k.value for k in guarded[0].keywords if k.arg == "require_new_sale")
        self.assertIsInstance(kw, ast.Compare)
        self.assertEqual(kw.left.id, "view_name")
        self.assertEqual(kw.comparators[0].value, "start_order")
        self.assertIn("download_paid", source)
        self.assertIn("reconcile_invoice", source)
        self.assertNotIn("_require_new_sale_rights", PAID.read_text("utf8"))


if __name__ == "__main__":
    unittest.main()
