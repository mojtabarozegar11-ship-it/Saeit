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
        # A real invoice-start success redirects to an owned invoice URL.
        response = types.SimpleNamespace(
            status_code=302,
            get=lambda key, default="": (
                "/commerce/trx-easy/invoice/57/" if key == "Location" else default
            ),
        )
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
            # The commercial adapter must only install over a complete,
            # unambiguous tuple of real buyer-facing routes.
            namespace["COMMERCIAL_URLPATTERNS"] = (
                ("commerce/trx-easy/start/<int:product_id>/", lambda *a, **k: response),
                ("commerce/trx-easy/invoice/<int:invoice_id>/", lambda *a, **k: response),
                ("commerce/trx-easy/invoice/<int:invoice_id>/status/", lambda *a, **k: response),
                ("commerce/trx-easy/invoice/<int:invoice_id>/reconcile/", lambda *a, **k: response),
                ("commerce/trx-easy/download/<int:invoice_id>/", lambda *a, **k: response),
            )
            installer(namespace)
            self.assertIs(namespace["start_order"](request, product_id=72), response)
            self.assertTrue(namespace["_mpw_guest_checkout_installed"])
            self.assertEqual(record.call_count, 1)
            # Failed validation must never count as an issued invoice.
            error_response = types.SimpleNamespace(
                status_code=400, get=lambda key, default="": "/commerce/trx-easy/invoice/57/"
            )
            dispatch.return_value = error_response
            self.assertIs(namespace["start_order"](request, product_id=72), error_response)
            self.assertEqual(record.call_count, 1)
            # External or arbitrary redirects do not prove an invoice either.
            external = types.SimpleNamespace(
                status_code=302,
                get=lambda key, default="": "https://example.org/commerce/trx-easy/invoice/57/"
            )
            dispatch.return_value = external
            self.assertIs(namespace["start_order"](request, product_id=72), external)
            self.assertEqual(record.call_count, 1)
            # Even when the product DB is unavailable, an existing invoice
            # redirect is returned unchanged and telemetry remains optional.
            dispatch.return_value = response
            product_model.objects.filter.side_effect = RuntimeError("query unavailable")
            self.assertIs(namespace["start_order"](request, product_id=72), response)
            self.assertEqual(dispatch.call_count, 4)

    def test_guest_invoice_routes_are_exact_and_unrelated_routes_unchanged(self):
        """Prevent silent ownership-wrapper installation on unrelated or drifted URLs."""
        response = types.SimpleNamespace(status_code=400, get=lambda *args: "")
        modules = stub_modules(Mock(), object())
        dispatch = Mock(return_value=response)
        with patch.dict(sys.modules, modules):
            installer = source_function("patch_commercial", {
                "_dispatch": dispatch,
                "_record_funnel_event_best_effort": lambda *args: False,
            })
            base = (
                ("commerce/trx-easy/start/<int:product_id>/", lambda *a, **k: response),
                ("commerce/trx-easy/invoice/<int:invoice_id>/", lambda *a, **k: response),
                ("commerce/trx-easy/invoice/<int:invoice_id>/status/", lambda *a, **k: response),
                ("commerce/trx-easy/invoice/<int:invoice_id>/reconcile/", lambda *a, **k: response),
                ("commerce/trx-easy/download/<int:invoice_id>/", lambda *a, **k: response),
            )
            handlers = {
                "_" + name: (lambda *args, **kwargs: response)
                for name in ("start_order", "show_invoice", "invoice_status",
                             "reconcile_invoice", "download_paid")
            }
            for route in (
                "commerce/trx-easy/start/72/",
                "commerce/trx-easy/start/<str:product_id>/",
                "commerce/trx-easy/start/<int:product_id>/extra/",
                "commerce/trx-easy/invoice/<int:invoice_id>/download/",
                "//commerce/trx-easy/start/<int:product_id>/",
            ):
                with self.subTest(route=route):
                    namespace = dict(handlers, COMMERCIAL_URLPATTERNS=base + (
                        (route, lambda *a, **k: response),))
                    before = dict(namespace)
                    with self.assertRaisesRegex(RuntimeError,
                                                "Unrecognized guest commercial route"):
                        installer(namespace)
                    self.assertEqual(namespace, before)
                    self.assertNotIn("_mpw_guest_checkout_installed", namespace)

            # The original server contract uses a leading slash plus string
            # invoice/receipt IDs; an unrelated catalogue route stays intact.
            legacy = (
                ("/commerce/trx-easy/start/<int:product_id>/", lambda *a, **k: response),
                ("/commerce/trx-easy/invoice/<str:invoice_id>/", lambda *a, **k: response),
                ("/commerce/trx-easy/invoice/<str:invoice_id>/status/", lambda *a, **k: response),
                ("/commerce/trx-easy/invoice/<str:invoice_id>/reconcile/", lambda *a, **k: response),
                ("/commerce/trx-easy/download/<str:receipt_id>/", lambda *a, **k: response),
                ("/commerce/trx-easy/catalogue/", lambda *a, **k: "catalogue"),
            )
            namespace = dict(handlers, COMMERCIAL_URLPATTERNS=legacy)
            installer(namespace)
            self.assertTrue(namespace["_mpw_guest_checkout_installed"])
            self.assertIs(namespace["COMMERCIAL_URLPATTERNS"][-1][1], legacy[-1][1])

            # A superficially similar path outside the commerce namespace is
            # never rebound to a payment or download handler.
            unrelated = ("other/start/<int:product_id>/",
                         lambda *args, **kwargs: "unrelated")
            namespace = dict(handlers, COMMERCIAL_URLPATTERNS=base + (unrelated,))
            installer(namespace)
            self.assertTrue(namespace["_mpw_guest_checkout_installed"])
            self.assertIs(namespace["COMMERCIAL_URLPATTERNS"][-1][1],
                          unrelated[1])
            self.assertEqual(namespace["COMMERCIAL_URLPATTERNS"][-1][1](), "unrelated")

            # A duplicate privileged route fails before any namespace mutation.
            namespace = dict(handlers, COMMERCIAL_URLPATTERNS=base + (base[0],))
            with self.assertRaisesRegex(RuntimeError, "Duplicate guest commercial route"):
                installer(namespace)
            self.assertNotIn("_mpw_guest_checkout_installed", namespace)



if __name__ == "__main__":
    unittest.main()
