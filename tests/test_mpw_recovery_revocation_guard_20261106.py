"""Offline safety contract: disabling recovery withdraws all access paths.

No Django installation, SMTP, orders, downloads or production database needed.
"""
from __future__ import annotations

import ast
from pathlib import Path
from types import SimpleNamespace
import unittest


SOURCE = Path(__file__).resolve().parents[1] / "services/mpw_trx_email_recovery.py"


class Http404(Exception):
    pass


class RecoveryRevocationGuard(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        tree = ast.parse(SOURCE.read_text("utf-8"))
        names = {"_recovery_active", "recovery_verify", "recovery_orders", "recovery_download"}
        functions = [node for node in tree.body
                     if isinstance(node, ast.FunctionDef) and node.name in names]
        assert {node.name for node in functions} == names
        # Isolate actual functions without Django's decorator imports.
        for fn in functions:
            fn.decorator_list = []
        cls.code = compile(ast.Module(body=functions, type_ignores=[]), str(SOURCE), "exec")

    def run_views(self, recovery_enabled, email_approved):
        settings = SimpleNamespace(
            MPW_GUEST_RECOVERY_ENABLED=recovery_enabled,
            MPW_GUEST_RECOVERY_EMAIL_APPROVED=email_approved,
        )
        touched = []

        def sensitive_scope(request):
            touched.append("customer_scope")
            raise RuntimeError("reached gated customer scope")

        env = {
            "settings": settings,
            "Http404": Http404,
            "_host": lambda request: True,
            "_scope": sensitive_scope,
            "_eligible_orders": lambda digest: [],
            "_form": lambda *args: "form",
            "_page": lambda *args, **kwargs: "page",
            "ROOT": "/commerce/trx-easy/recover/",
        }
        exec(self.code, env)
        request = SimpleNamespace(method="GET")
        return env, touched, request

    def test_both_switches_must_be_enabled(self):
        for enabled, approved in ((False, False), (False, True), (True, False)):
            with self.subTest(enabled=enabled, approved=approved):
                env, touched, req = self.run_views(enabled, approved)
                self.assertFalse(env["_recovery_active"]())
                with self.assertRaises(Http404):
                    env["recovery_verify"](req)
                with self.assertRaises(Http404):
                    env["recovery_orders"](req)
                with self.assertRaises(Http404):
                    env["recovery_download"](req, 99)
                self.assertEqual(touched, [])

    def test_approved_routes_remain_reachable(self):
        env, touched, req = self.run_views(True, True)
        self.assertTrue(env["_recovery_active"]())
        self.assertEqual(env["recovery_verify"](req), "page")
        with self.assertRaisesRegex(RuntimeError, "reached gated customer scope"):
            env["recovery_orders"](req)
        with self.assertRaisesRegex(RuntimeError, "reached gated customer scope"):
            env["recovery_download"](req, 99)
        self.assertEqual(touched, ["customer_scope", "customer_scope"])


if __name__ == "__main__":
    unittest.main()
