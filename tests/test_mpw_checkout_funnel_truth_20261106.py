"""Offline checkout-event accuracy checks; never create orders or send mail."""
from __future__ import annotations

import ast
from pathlib import Path
import re
import sys
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import patch


SOURCE = Path(__file__).resolve().parents[1] / "services/mpw_trx_guest_commerce.py"


class Response(dict):
    def __init__(self, status, location=""):
        super().__init__(Location=location)
        self.status_code = status


class FunnelTruth(unittest.TestCase):
    def setUp(self):
        tree = ast.parse(SOURCE.read_text("utf-8"))
        selected = [node for node in tree.body if isinstance(node, ast.FunctionDef)
                    and node.name in ("_dispatch", "_is_invoice_redirect")]
        self.assertEqual(len(selected), 2)
        conf = ModuleType("django.conf")
        self.settings = SimpleNamespace(MPW_GUEST_EMAIL_CLAIM_CAPTURE_ENABLED=False,
                                        MPW_GUEST_RECOVERY_ENABLED=False)
        conf.settings = self.settings
        recovery = ModuleType("services.mpw_trx_email_recovery")
        recovery.bound_checkout = lambda request, view, identity, install, args, kwargs: view(
            request, *args, **kwargs)
        self.modules = patch.dict(sys.modules, {
            "django": ModuleType("django"), "django.conf": conf,
            "services.mpw_trx_email_recovery": recovery,
        })
        self.modules.start()
        self.addCleanup(self.modules.stop)
        self.events = []
        self.space = {
            "re": re,
            "INVOICE_LOCATION": re.compile(r"\A/commerce/trx-easy/invoice/[1-9][0-9]*/\Z"),
            "_identity": lambda request, create=False: (object(), "cookie"),
            "_install_cookie": lambda response, cookie: response,
            "_count_checkout_event": lambda *args: self.events.append(args[1]),
        }
        exec(compile(ast.Module(body=selected, type_ignores=[]), str(SOURCE), "exec"),
             self.space)
        self.request = SimpleNamespace()

    def checkout(self, response):
        return self.space["_dispatch"](
            self.request, lambda request: response, (), {}, create=True)

    def test_valid_invoice_redirect_counts_once(self):
        self.checkout(Response(302, "/commerce/trx-easy/invoice/123/"))
        self.assertEqual(self.events, ["order_start_accepted"])

    def test_validation_page_or_failure_redirect_does_not_count(self):
        for response in (Response(200), Response(302, "/store/"),
                         Response(302, None),
                         Response(303, "/commerce/trx-easy/invoice/0/"),
                         Response(307, "/commerce/trx-easy/invoice/10/"),
                         Response(302, "https://other.example/invoice/10/")):
            with self.subTest(response=response):
                self.checkout(response)
        self.assertEqual(self.events, [])

    def test_claim_capture_branch_uses_same_invoice_gate(self):
        self.settings.MPW_GUEST_EMAIL_CLAIM_CAPTURE_ENABLED = True
        self.checkout(Response(302, "/store/"))
        self.assertEqual(self.events, [])
        self.checkout(Response(303, "/commerce/trx-easy/invoice/222/"))
        self.assertEqual(self.events, ["order_start_accepted"])

    def test_existing_purchase_views_never_count_order_creation(self):
        self.space["_dispatch"](self.request, lambda request: Response(302,
            "/commerce/trx-easy/invoice/123/"), (), {}, create=False)
        self.assertEqual(self.events, [])


if __name__ == "__main__":
    unittest.main()
