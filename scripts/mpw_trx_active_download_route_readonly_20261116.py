#!/usr/bin/env python3
"""Owner-only read-only scan of effective live walletless TRX download routing.

No buyer session is created or used, no view is called, no invoice, no file
opened, no payment or network request. Django reverse/resolve metadata ONLY.
Never log customer IDs, URLs containing tokens, actual orders or private paths.
"""
from __future__ import annotations

import inspect
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path("/home/zomorod2/Saeit-staging")
BASE = "/commerce/trx-easy/"
PARAM = re.compile(r"<(?:int|str|slug):[a-zA-Z_][a-zA-Z_0-9]*>")


def expand_literal_route(route):
    """Read-only Django URL resolution candidate; no user-controlled paths."""
    if type(route) is not str or len(route) > 160:
        return None
    # Django path() registers relative patterns without an HTTP leading slash.
    canonical = "/" + route.lstrip("/")
    if (not canonical.startswith(BASE)
            or any(ch in canonical for ch in (chr(92), "?", "#"))):
        return None
    substituted = PARAM.sub("1", canonical)
    if ("<" in substituted or ">" in substituted or "//" in substituted
            or ".." in substituted or not substituted.endswith("/")):
        return None
    return substituted


def inspect_active_patterns(patterns, resolver, handlers):
    """Separate route declaration from *actual* active Django resolution."""
    state = {
        "schema": "mpw.trx.walletless.active.download.route.readonly.v1",
        "read_only": True,
        "declared_checkout_route": False,
        "declared_invoice_route": False,
        "declared_paid_download_route": False,
        "actual_paid_download_route_resolves": False,
        "resolved_download_is_current_registered_handler": False,
        "download_handler_callable": False,
        "untrusted_route_format_observed": False,
        "download_request_executed": False,
        "private_file_opened": False,
        "buyer_impersonated": False,
        "checkout_started": False,
        "payment_or_receipt_created": False,
    }
    if not isinstance(patterns, (list, tuple)):
        return state
    handler = handlers.get("download_paid")
    state["download_handler_callable"] = callable(handler)
    for item in patterns[:40]:
        if (not isinstance(item, (list, tuple)) or len(item) != 2
                or type(item[0]) is not str or not callable(item[1])):
            state["untrusted_route_format_observed"] = True
            continue
        path, registered = item
        candidate = expand_literal_route(path)
        if candidate is None:
            state["untrusted_route_format_observed"] = True
            continue
        state["declared_checkout_route"] |= "/checkout/" in candidate
        state["declared_invoice_route"] |= "/invoice/" in candidate
        if "/download/" not in candidate:
            continue
        state["declared_paid_download_route"] = True
        try:
            match = resolver(candidate)
            state["actual_paid_download_route_resolves"] = True
            active = match.func
            state["resolved_download_is_current_registered_handler"] |= (
                active is registered and (active is handler or
                                          inspect.unwrap(active) is inspect.unwrap(handler))
            ) if callable(handler) else False
        except Exception:
            continue
    return state


def run():
    result = {"schema": "mpw.trx.walletless.active.download.route.readonly.v1",
              "read_only": True,
              "production_files_changed": False,
              "inspection_available": False}
    if not ROOT.is_dir() or ROOT.is_symlink() or ROOT.resolve() != ROOT:
        result["error_type"] = "UntrustedTenant"
    else:
        try:
            os.chdir(ROOT)
            sys.path.insert(0, str(ROOT))
            os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
            import django
            django.setup()
            from django.urls import resolve
            from services import mpw_trx_commercial_web as web
            from services import mpw_trx_guest_commerce as guest
            registry = getattr(web, "COMMERCIAL_URLPATTERNS", None)
            handlers = {"download_paid": getattr(web, "download_paid", None)}
            result.update(inspect_active_patterns(registry, resolve, handlers))
            result["guest_cookie_scope_correct"] = (
                getattr(guest, "COOKIE_PATH", None) == BASE
                and getattr(guest, "COOKIE_AGE", None) == 30 * 86400
            )
            result["inspection_available"] = True
            result["error_type"] = None
        except Exception as exc:
            result["error_type"] = type(exc).__name__
    print("MPW_TRX_ACTUAL_DOWNLOAD_ROUTE_READONLY="
          + json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    run()
