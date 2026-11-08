"""Source-backed isolation tests; no network, database or buyer order writes."""
import ast
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import Mock, patch


SOURCE = (Path(__file__).resolve().parents[1] / "services/mpw_trx_guest_commerce.py")


def source_function(name, namespace=None):
    source = ast.parse(SOURCE.read_text(encoding="utf8"))
    node = next(n for n in source.body if isinstance(n, ast.FunctionDef) and n.name == name)
    scope = dict(namespace or {})
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(SOURCE), "exec"), scope)
    return scope[name]


def stub_modules(record, product):
    names = (
        "django", "django.views", "django.views.decorators", "django.views.decorators.cache",
        "django.views.decorators.csrf", "django.views.decorators.http", "core", "core.models",
        "core.commerce_funnel",
    )
    result = {name: types.ModuleType(name) for name in names}
    identity = lambda view: view
    result["django.views.decorators.cache"].never_cache = identity
    result["django.views.decorators.csrf"].csrf_protect = identity
    result["django.views.decorators.http"].require_GET = identity
    result["django.views.decorators.http"].require_POST = identity
    result["core.models"].Product = product
    result["core.commerce_funnel"].record_funnel_event = record
    return result


class CheckoutTelemetryIsolationTests(unittest.TestCase):
    def test_optional_analytics_failure_does_not_raise_or_reveal_exception(self):
        secret = "buyer-private-order-token"
        record = Mock(side_effect=RuntimeError(secret))
        with patch.dict(sys.modules, stub_modules(record, object())):
            helper = source_function("_record_funnel_event_best_effort")
            self.assertFalse(helper(object(), "invoice_created", object()))
        record.assert_called_once()

    def test_missing_analytics_module_does_not_block_checkout(self):
        modules = stub_modules(Mock(), object())
        modules["core.commerce_funnel"] = None
        with patch.dict(sys.modules, modules):
            helper = source_function("_record_funnel_event_best_effort")
            self.assertFalse(helper(object(), "begin_checkout", object()))

    def test_invoice_response_preserved_when_telemetry_or_lookup_fails(self):
        response = object()
        request = object()
        product = object()
        product_model = types.SimpleNamespace(objects=types.SimpleNamespace(
            filter=Mock(return_value=types.SimpleNamespace(first=lambda: product))))
        record = Mock(side_effect=RuntimeError("buyer-sensitive-detail"))
        modules = stub_modules(record, product_model)
        dispatch = Mock(return_value=response)
        with patch.dict(sys.modules, modules):
            helper = source_function("_record_funnel_event_best_effort")
            installer = source_function("patch_commercial", {
                "_dispatch": dispatch, "_record_funnel_event_best_effort": helper,
            })
            namespace = {"_" + name: (lambda *args, **kwargs: response) for name in (
                "start_order", "show_invoice", "invoice_status",
                "reconcile_invoice", "download_paid",
            )}
            installer(namespace)
            self.assertIs(namespace["start_order"](request, product_id=72), response)
            self.assertTrue(namespace["_mpw_guest_checkout_installed"])
            self.assertEqual(record.call_count, 1)
            product_model.objects.filter.side_effect = RuntimeError("query unavailable")
            self.assertIs(namespace["start_order"](request, product_id=72), response)
            self.assertEqual(dispatch.call_count, 2)


if __name__ == "__main__":
    unittest.main()
