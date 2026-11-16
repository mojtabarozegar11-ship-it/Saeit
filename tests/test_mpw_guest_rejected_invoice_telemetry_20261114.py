"""Rejected invoice responses must never be counted as created invoices."""
import ast
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

SOURCE = Path(__file__).resolve().parents[1] / "services/mpw_trx_guest_commerce.py"

def load_patch(dispatch, record):
    tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
    node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "patch_commercial")
    guard = next(n for n in tree.body if isinstance(n, ast.FunctionDef)
                 and n.name == "_new_trx_merchant_canary_is_true")
    scope = {"_dispatch": dispatch, "_record_funnel_event_best_effort": record,
             "Http404": LookupError}
    exec(compile(ast.Module(body=[guard, node], type_ignores=[]), str(SOURCE), "exec"), scope)
    return scope["patch_commercial"]

class RejectedInvoiceTelemetryTests(unittest.TestCase):
    def test_rejected_invoice_is_not_recorded(self):
        modules = {}
        for name in ("django", "django.views", "django.views.decorators",
                     "django.views.decorators.cache", "django.views.decorators.csrf",
                     "django.views.decorators.http", "django.conf"):
            modules[name] = types.ModuleType(name)
        for module, names in (
            ("django.views.decorators.cache", ("never_cache",)),
            ("django.views.decorators.csrf", ("csrf_protect",)),
            ("django.views.decorators.http", ("require_GET", "require_POST")),
        ):
            for name in names:
                setattr(modules[module], name, lambda view: view)
        # Isolated telemetry tests explicitly model a VERIFIED merchant.
        # Fail-closed canary=False cases are covered by C119 security tests.
        modules["django.conf"].settings = types.SimpleNamespace(
            MPW_WALLETLESS_TRX_MERCHANT_CANARY_PASSED=True)
        for status in (400, 403, 404, 429, 500):
            with self.subTest(status=status), patch.dict(sys.modules, modules):
                response = types.SimpleNamespace(status_code=status)
                record = Mock()
                dispatch = Mock(return_value=response)
                namespace = {"_" + name: Mock() for name in (
                    "start_order", "show_invoice", "invoice_status",
                    "reconcile_invoice", "download_paid")}
                load_patch(dispatch, record)(namespace)
                self.assertIs(namespace["start_order"](object(), product_id=72), response)
                record.assert_not_called()

if __name__ == "__main__":
    unittest.main()
