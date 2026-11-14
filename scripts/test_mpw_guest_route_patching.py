#!/usr/bin/env python3
"""Offline, read-only validation of the actual guest route patch function."""
from __future__ import annotations
import ast
import sys
import types
from pathlib import Path

def load():
    path = Path(__file__).resolve().parents[1] / "services/mpw_trx_guest_commerce.py"
    functions = [x for x in ast.parse(path.read_text(encoding="utf-8")).body
                 if isinstance(x, ast.FunctionDef) and x.name == "patch_commercial"]
    assert len(functions) == 1
    for name in ("django", "django.views", "django.views.decorators",
                 "django.views.decorators.cache", "django.views.decorators.csrf",
                 "django.views.decorators.http"):
        sys.modules.setdefault(name, types.ModuleType(name))
    identity = lambda x: x
    sys.modules["django.views.decorators.cache"].never_cache = identity
    sys.modules["django.views.decorators.csrf"].csrf_protect = identity
    sys.modules["django.views.decorators.http"].require_GET = identity
    sys.modules["django.views.decorators.http"].require_POST = identity
    # The real installer registers read-only recovery URLs.  Stub their
    # handlers without importing Django, email backends or production modules.
    sys.modules.setdefault("services", types.ModuleType("services"))
    sys.modules["services"].__path__ = []
    recovery = types.ModuleType("services.mpw_trx_email_recovery")
    for name in ("recovery_request", "recovery_verify", "recovery_orders",
                 "recovery_download"):
        setattr(recovery, name, old)
    sys.modules["services.mpw_trx_email_recovery"] = recovery
    variables = {}
    exec(compile(ast.Module(body=functions, type_ignores=[]), "<isolated-guest-patch>", "exec"),
         variables)
    return variables["patch_commercial"]

def old(*_args, **_kwargs):
    return None

def routes():
    return (
        ("/commerce/trx-easy/start/<int:product_id>/", old),
        ("/commerce/trx-easy/invoice/<str:invoice_id>/", old),
        ("/commerce/trx-easy/invoice/<str:invoice_id>/status/", old),
        ("/commerce/trx-easy/invoice/<str:invoice_id>/reconcile/", old),
        ("/commerce/trx-easy/download/<str:receipt_id>/", old),
        ("/commerce/trx-easy/catalogue/", old),
    )

def candidate(items):
    result = {"COMMERCIAL_URLPATTERNS": items}
    for name in ("_start_order", "_show_invoice", "_invoice_status",
                 "_reconcile_invoice", "_download_paid"):
        result[name] = old
    return result

def rejected_without_mutation(patch, items):
    value = candidate(items)
    initial = dict(value)
    try:
        patch(value)
    except RuntimeError:
        pass
    else:
        raise AssertionError("Unsafe route drift accepted")
    assert value == initial, "Route drift caused partial mutation"
    assert "_mpw_guest_checkout_installed" not in value

def main():
    patch = load()
    original = routes()
    value = candidate(original)
    patch(value)
    expected = ("start_order", "show_invoice", "invoice_status",
                "reconcile_invoice", "download_paid")
    mapped = dict(value["COMMERCIAL_URLPATTERNS"])
    for (path, _), name in zip(original[:5], expected):
        assert mapped[path] is value[name], name
        assert mapped[path] is not old
    assert mapped[original[5][0]] is old
    recovery = (
        "commerce/trx-easy/recover/",
        "commerce/trx-easy/recover/verify/",
        "commerce/trx-easy/recover/orders/",
        "commerce/trx-easy/recover/download/<int:invoice_id>/",
    )
    for route in recovery:
        assert route in mapped and mapped[route] is old
    saved = value["COMMERCIAL_URLPATTERNS"]
    patch(value)
    assert value["COMMERCIAL_URLPATTERNS"] is saved
    rejected_without_mutation(patch, None)
    rejected_without_mutation(patch, list(original))
    rejected_without_mutation(patch, original[:4] + original[5:])
    rejected_without_mutation(patch, original[:2] + (original[1],) + original[2:])
    rejected_without_mutation(patch, original[:3] + (("/bad/route/", None),) + original[3:])
    # An existing recovery route must fail without touching any handler.
    rejected_without_mutation(patch, original + (("commerce/trx-easy/recover/", old),))
    print("MPW_GUEST_ROUTE_CONTRACT=PASS;NO_SERVER_IO=TRUE")

if __name__ == "__main__":
    main()
