"""Source-level C119 regression: merchant admission must fail closed for new TRX requests.

Pure tests: no Django import, no network, no customer database, no payments.
"""
import ast
import sys
import types
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

SOURCE = Path(__file__).resolve().parents[1] / "services/mpw_trx_guest_commerce.py"
TEXT = SOURCE.read_text(encoding="utf-8")
TREE = ast.parse(TEXT)


def pure_canary_guard():
    helper = next(node for node in TREE.body if isinstance(node, ast.FunctionDef)
                  and node.name == "_new_trx_merchant_canary_is_true")
    ctx = {}
    exec(compile(ast.Module(body=[helper], type_ignores=[]), str(SOURCE), "exec"), ctx)
    return ctx[helper.name]


class NewTrxMerchantCanaryTests(unittest.TestCase):
    def test_01_exact_true_only(self):
        guard = pure_canary_guard()
        for status in (None, False, 0, 1, "true", "True", [], {}, object()):
            with self.subTest(status=status):
                self.assertFalse(guard(SimpleNamespace(
                    MPW_WALLETLESS_TRX_MERCHANT_CANARY_PASSED=status)))
        self.assertTrue(guard(SimpleNamespace(
            MPW_WALLETLESS_TRX_MERCHANT_CANARY_PASSED=True)))

    def test_02_missing_setting_defaults_deny(self):
        self.assertFalse(pure_canary_guard()(SimpleNamespace()))

    def test_03_checkout_get_guard_runs_before_db_import(self):
        fn = next(x for x in TREE.body if isinstance(x, ast.FunctionDef)
                  and x.name == "_checkout_page")
        calls = [n for n in ast.walk(fn) if isinstance(n, ast.Call)
                 and isinstance(n.func, ast.Name)
                 and n.func.id == "_new_trx_merchant_canary_is_true"]
        self.assertEqual(len(calls), 1)
        external_imports = [n for n in ast.walk(fn) if isinstance(n, ast.ImportFrom)
                            and n.module in ("django.db", "core.models",
                                             "services.mpw_trx_commercial_web")]
        self.assertTrue(external_imports)
        self.assertLess(calls[0].lineno, min(n.lineno for n in external_imports))

    def test_04_only_new_start_order_is_gated(self):
        fn = next(x for x in TREE.body if isinstance(x, ast.FunctionDef)
                  and x.name == "patch_commercial")
        targets = next(n for n in ast.walk(fn) if isinstance(n, ast.Assign)
                       and any(isinstance(t, ast.Name) and t.id == "targets"
                               for t in n.targets))
        keys = [k.value for k in targets.value.keys]
        self.assertEqual(set(keys), {"start_order", "show_invoice",
                                     "invoice_status", "reconcile_invoice",
                                     "download_paid"})
        wrapped = next(n for n in ast.walk(fn) if isinstance(n, ast.FunctionDef)
                       and n.name == "wrapped")
        call = next(n for n in ast.walk(wrapped) if isinstance(n, ast.Call)
                    and isinstance(n.func, ast.Name)
                    and n.func.id == "_new_trx_merchant_canary_is_true")
        identity = next(n for n in ast.walk(wrapped) if isinstance(n, ast.Call)
                        and isinstance(n.func, ast.Name)
                        and n.func.id == "_dispatch")
        self.assertLess(call.lineno, identity.lineno)
        surrounding = ast.get_source_segment(TEXT, wrapped) or ""
        self.assertIn('view_name == "start_order"', surrounding)

    def test_05_no_bypass_on_public_flag_or_old_paid_receipts(self):
        fn = next(x for x in TREE.body if isinstance(x, ast.FunctionDef)
                  and x.name == "_new_trx_merchant_canary_is_true")
        body = ast.get_source_segment(TEXT, fn) or ""
        self.assertNotIn("PUBLIC_ENABLED", body)
        self.assertNotIn("existing_payment", body)
        self.assertIn("is True", body)

    def test_06_no_paid_side_effects_in_guard(self):
        body = ast.get_source_segment(
            TEXT, next(x for x in TREE.body if isinstance(x, ast.FunctionDef)
                       and x.name == "_new_trx_merchant_canary_is_true")) or ""
        for forbidden in ("objects.create", "request.post", "sendrawtransaction",
                          "send_mail(", ".save(", "wallet", "invoice_create"):
            self.assertNotIn(forbidden, body)

    def test_07_guest_history_and_recovery_handlers_retained(self):
        self.assertIn('namespace["purchases"] = purchases', TEXT)
        self.assertIn('"show_invoice": ("_show_invoice"', TEXT)
        self.assertIn('"download_paid": ("_download_paid"', TEXT)

    def test_08_source_keeps_fail_closed_response_not_false_success(self):
        self.assertIn('Http404("New TRX checkout unavailable")', TEXT)
        self.assertIn('Http404("New TRX invoices unavailable")', TEXT)
        self.assertNotIn("MPW_WALLETLESS_TRX_MERCHANT_CANARY_PASSED = True", TEXT)


    def test_09_checkout_get_fails_before_db_without_verified_merchant(self):
        node = next(n for n in TREE.body if isinstance(n, ast.FunctionDef)
                    and n.name == "_checkout_page")
        scope = {"_new_trx_merchant_canary_is_true": pure_canary_guard(),
                 "Http404": LookupError}
        exec(compile(ast.Module(body=[node], type_ignores=[]),
                     str(SOURCE), "exec"), scope)
        conf = types.ModuleType("django.conf")
        conf.settings = SimpleNamespace(
            MPW_WALLETLESS_TRX_MERCHANT_CANARY_PASSED=False)
        with patch.dict(sys.modules, {"django": types.ModuleType("django"),
                                      "django.conf": conf}):
            with self.assertRaisesRegex(LookupError, "New TRX checkout unavailable"):
                scope["_checkout_page"](object(), 72, {})

    def test_10_start_order_denied_without_identity_or_invoice_dispatch(self):
        node = next(n for n in TREE.body if isinstance(n, ast.FunctionDef)
                    and n.name == "patch_commercial")
        dispatch = Mock(return_value=SimpleNamespace(status_code=201))
        scope = {"_new_trx_merchant_canary_is_true": pure_canary_guard(),
                 "Http404": LookupError, "_dispatch": dispatch}
        exec(compile(ast.Module(body=[node], type_ignores=[]),
                     str(SOURCE), "exec"), scope)
        fake = {"django": types.ModuleType("django"),
                "django.views": types.ModuleType("django.views"),
                "django.views.decorators": types.ModuleType("django.views.decorators"),
                "django.views.decorators.cache": types.ModuleType("django.views.decorators.cache"),
                "django.views.decorators.csrf": types.ModuleType("django.views.decorators.csrf"),
                "django.views.decorators.http": types.ModuleType("django.views.decorators.http"),
                "django.conf": types.ModuleType("django.conf")}
        for mod, key in (("django.views.decorators.cache", "never_cache"),
                         ("django.views.decorators.csrf", "csrf_protect"),
                         ("django.views.decorators.http", "require_GET"),
                         ("django.views.decorators.http", "require_POST")):
            setattr(fake[mod], key, lambda view: view)
        ns = {"_" + name: Mock() for name in (
            "start_order", "show_invoice", "invoice_status",
            "reconcile_invoice", "download_paid")}
        with patch.dict(sys.modules, fake):
            scope["patch_commercial"](ns)
            for flag in (False, None, 1, "true"):
                with self.subTest(flag=flag):
                    fake["django.conf"].settings = SimpleNamespace(
                        MPW_WALLETLESS_TRX_MERCHANT_CANARY_PASSED=flag)
                    with self.assertRaisesRegex(LookupError, "New TRX invoices unavailable"):
                        ns["start_order"](object(), product_id=72)
                    dispatch.assert_not_called()
            # Existing legitimate paid buyers must retain protected invoice
            # retrieval; no new identity is created in this path.
            fake["django.conf"].settings = SimpleNamespace(
                MPW_WALLETLESS_TRX_MERCHANT_CANARY_PASSED=False)
            ns["show_invoice"](object(), invoice_id=123)
            self.assertEqual(dispatch.call_count, 1)


if __name__ == "__main__":
    unittest.main()
