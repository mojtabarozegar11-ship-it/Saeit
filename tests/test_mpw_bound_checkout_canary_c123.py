"""No-network C123 regression: email-bound new invoice must deny a missing canary.

Pure source-function harness. No Django database, SMTP, real order, HTTP or wallet.
"""
import ast
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

SOURCE = Path(__file__).resolve().parents[1] / "services/mpw_trx_email_recovery.py"
TEXT = SOURCE.read_text(encoding="utf8")
AST = ast.parse(TEXT)


def extracted(*, canary, host=True):
    fn = next(n for n in AST.body if isinstance(n, ast.FunctionDef)
              and n.name == "bound_checkout")
    class Deny(Exception):
        pass
    post_email = Mock(side_effect=AssertionError("email parsed before merchant gate"))
    identity = Mock(side_effect=AssertionError("guest identity created"))
    views = Mock(side_effect=AssertionError("invoice handler executed"))
    cookie = Mock(side_effect=AssertionError("cookie granted"))
    env = {
        "_host": Mock(return_value=host),
        "settings": SimpleNamespace(MPW_WALLETLESS_TRX_MERCHANT_CANARY_PASSED=canary),
        "Http404": Deny,
        "_posted_email": post_email,
    }
    exec(compile(ast.Module(body=[fn], type_ignores=[]), str(SOURCE), "exec"), env)
    return env["bound_checkout"], Deny, (identity, views, cookie, post_email)


class MerchantCanaryAtBoundCheckout(unittest.TestCase):
    def test_01_false_canary_denies_without_side_effects(self):
        fn, Deny, checks = extracted(canary=False)
        with self.assertRaisesRegex(Deny, "New TRX merchant checkout unavailable"):
            fn(object(), checks[1], checks[0], checks[2], (), {})
        for m in checks:
            m.assert_not_called()

    def test_02_missing_or_truthy_canary_fails_closed(self):
        for val in (None, 0, 1, "true", "True", [], {}, object()):
            with self.subTest(value=str(val)):
                fn, Deny, checks = extracted(canary=val)
                with self.assertRaises(Deny):
                    fn(object(), checks[1], checks[0], checks[2], (), {})
                for m in checks:
                    m.assert_not_called()

    def test_03_invalid_host_denies_even_when_canary_true(self):
        fn, Deny, checks = extracted(canary=True, host=False)
        with self.assertRaises(Deny):
            fn(object(), checks[1], checks[0], checks[2], (), {})
        for m in checks:
            m.assert_not_called()

    def test_04_gate_before_email_and_atomic_db_transaction(self):
        node = next(n for n in AST.body if isinstance(n, ast.FunctionDef)
                    and n.name == "bound_checkout")
        statements = node.body
        guarded = next(n for n in ast.walk(node) if isinstance(n, ast.Raise)
                       and "New TRX merchant checkout unavailable" in
                       (ast.get_source_segment(TEXT, n) or ""))
        email = next(n for n in ast.walk(node) if isinstance(n, ast.Call)
                     and isinstance(n.func, ast.Name) and n.func.id == "_posted_email")
        atomic = next(n for n in ast.walk(node) if isinstance(n, ast.Call)
                      and isinstance(n.func, ast.Attribute) and n.func.attr == "atomic")
        self.assertLess(guarded.lineno, email.lineno)
        self.assertLess(guarded.lineno, atomic.lineno)

    def test_05_canary_is_literal_true_not_public_flag(self):
        node = next(n for n in AST.body if isinstance(n, ast.FunctionDef)
                    and n.name == "bound_checkout")
        src = ast.get_source_segment(TEXT, node) or ""
        self.assertIn('"MPW_WALLETLESS_TRX_MERCHANT_CANARY_PASSED", False) is not True', src)
        self.assertNotIn("MPW_WALLETLESS_TRX_PUBLIC_ENABLED", src)
        self.assertNotIn("merchant_canary = True", src)

    def test_06_historical_download_and_recovery_unmodified(self):
        self.assertIn("def recovery_request(request)", TEXT)
        self.assertIn("def recovery_verify(request)", TEXT)
        self.assertIn("def recovery_orders(request)", TEXT)
        self.assertIn("def recovery_download(request, invoice_id)", TEXT)
        self.assertIn("def bound_checkout(", TEXT)
        self.assertIn("GuestOrderEmail.objects.create(", TEXT)
        self.assertIn("Checkout email ownership binding unavailable", TEXT)

    def test_07_default_missing_setting_denies(self):
        node = next(n for n in AST.body if isinstance(n, ast.FunctionDef)
                    and n.name == "bound_checkout")
        class Deny(Exception): pass
        env = {"_host": lambda request: True, "settings": SimpleNamespace(),
               "Http404": Deny, "_posted_email": Mock()}
        exec(compile(ast.Module(body=[node], type_ignores=[]), str(SOURCE), "exec"), env)
        with self.assertRaises(Deny):
            env["bound_checkout"](object(), Mock(), Mock(), Mock(), (), {})
        env["_posted_email"].assert_not_called()

    def test_08_no_prod_side_effect_in_new_gate(self):
        src = ast.get_source_segment(
            TEXT, next(n for n in AST.body if isinstance(n, ast.FunctionDef)
                       and n.name == "bound_checkout")) or ""
        guard = src.split("if getattr(settings, \"MPW_WALLETLESS_TRX_MERCHANT_CANARY_PASSED\"", 1)[1].split("try:\n        email", 1)[0]
        for forbidden in ("send_mail", ".save(", "objects.create", "txid", "broadcast", "transaction.atomic"):
            self.assertNotIn(forbidden, guard)


if __name__ == "__main__":
    unittest.main()
