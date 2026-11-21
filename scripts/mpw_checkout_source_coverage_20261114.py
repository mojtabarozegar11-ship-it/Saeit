#!/usr/bin/env python3
"""Fail-closed SOURCE MANIFEST for the MojPlayWin real buyer TRX checkout.

This tool has NO live-site, database, email or payment access. It prevents a
reviewed GitHub tree with missing buyer modules/routes from being advertised
as a complete deployable checkout. Separate cPanel deployments may differ.
"""
from __future__ import annotations

import ast
import json
import stat
from pathlib import Path

SCHEMA = "mojtaba.bot.ai.mpw-buyer-source-coverage.v1"
ROOT = Path(__file__).resolve().parents[1]
MAX_BYTES = 300_000
REQUIRED = (
    "config/settings.py",
    "config/urls.py",
    "core/commerce_views.py",
    "core/mojplaywin_views.py",
    "core/templates/mojplaywin/store.html",
    "services/mpw_trx_guest_commerce.py",
    "services/mpw_trx_email_recovery.py",
    "mpw_commerce/buyer_orders.py",
    "mpw_commerce/product_checkout_page.py",
    "mpw_commerce/templates/mpw_commerce/product_checkout.html",
    "core/migrations/0049_mpw_guest_email_recovery.py",
)
EXPLICIT_ROUTES = (
    "store/",
    "store/product/<int:product_id>/checkout/",
    "commerce/book/<int:product_id>/",
    "commerce/trx-easy/start/<int:product_id>/",
)
MIDDLEWARE_PATH = (
    "core.mpw_checkout_security_middleware.MojPlayWinCheckoutSecurityMiddleware"
)


def safe_read(root: Path, relative: str):
    """Read only known small regular repo files, never symlink targets."""
    if type(relative) is not str or relative not in REQUIRED:
        return None
    if root.is_symlink() or not root.is_dir():
        return None
    target = root / relative
    cursor = target
    try:
        while cursor != root:
            if cursor.is_symlink():
                return None
            cursor = cursor.parent
        meta = target.stat()
        if not stat.S_ISREG(meta.st_mode) or not 0 < meta.st_size <= MAX_BYTES:
            return None
        with target.open("rb") as file:
            content = file.read(MAX_BYTES + 1)
        if len(content) > MAX_BYTES:
            return None
        return content
    except (ValueError, OSError, UnicodeError):
        return None


def _parsed_python(content):
    try:
        return ast.parse(content.decode("utf-8", "strict"))
    except (ValueError, UnicodeError, SyntaxError, RecursionError):
        return None


def _literal_paths(tree):
    """Only static path('literal/', ...) calls are observed, not runtime URLs."""
    if tree is None:
        return set()
    result = set()
    for node in ast.walk(tree):
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                and node.func.id == "path" and node.args):
            label = node.args[0]
            if isinstance(label, ast.Constant) and type(label.value) is str:
                result.add(label.value)
    return result


def _middleware_installed(tree):
    if tree is None:
        return False
    for node in tree.body:
        if (isinstance(node, ast.Assign) and
                any(isinstance(t, ast.Name) and t.id == "MIDDLEWARE"
                    for t in node.targets) and isinstance(node.value, (ast.List, ast.Tuple))):
            return any(isinstance(el, ast.Constant)
                       and el.value == MIDDLEWARE_PATH for el in node.value.elts)
    return False


def _commerce_app_installed(tree):
    if tree is None:
        return False
    for node in tree.body:
        if (isinstance(node, ast.Assign) and
                any(isinstance(t, ast.Name) and t.id == "INSTALLED_APPS"
                    for t in node.targets) and isinstance(node.value, (ast.List, ast.Tuple))):
            return any(isinstance(el, ast.Constant)
                       and type(el.value) is str
                       and el.value in ("mpw_commerce", "mpw_commerce.apps.MpwCommerceConfig")
                       for el in node.value.elts)
    return False


def audit(root: Path = ROOT):
    """Does not mutate anything or infer live effective Passenger code."""
    if type(root) is not Path and not isinstance(root, Path):
        raise ValueError("invalid root")
    statuses = {name: "present_regular_bounded" if safe_read(root, name) is not None
                else "missing_or_unsafe" for name in REQUIRED}
    settings = _parsed_python(safe_read(root, "config/settings.py") or b"")
    routes = _literal_paths(_parsed_python(safe_read(root, "config/urls.py") or b""))
    flags = {name: name in routes for name in EXPLICIT_ROUTES}
    source_count = sum(status == "present_regular_bounded"
                       for status in statuses.values())
    exact_route_count = sum(flags.values())
    commerce_installed = _commerce_app_installed(settings)
    middleware_installed = _middleware_installed(settings)
    complete = (
        source_count == len(REQUIRED)
        and exact_route_count == len(EXPLICIT_ROUTES)
        and commerce_installed and middleware_installed
    )
    return {
        "schema": SCHEMA,
        "canonical_bot": "mojtaba.bot.ai",
        "files": statuses,
        "source_files_present": source_count,
        "source_files_required": len(REQUIRED),
        "explicit_source_routes": flags,
        "explicit_source_routes_count": exact_route_count,
        "explicit_source_routes_required": len(EXPLICIT_ROUTES),
        "commerce_app_installed_in_reviewed_settings_source": commerce_installed,
        "exact_checkout_csp_middleware_installed_in_settings_source": middleware_installed,
        "complete_versioned_buyer_checkout_source_candidate": complete,
        "missing_components_are_not_proof_of_absence_on_cpanel": True,
        "effective_passenger_app_verified": False,
        "live_checkout_csp_verified": False,
        "live_dynamic_store_verified": False,
        "actual_payment_verified": False,
        "paid_delivery_verified": False,
        "actual_collected_revenue": None,
        "release_permitted": False,
        "network_access": False,
        "customer_data_read": False,
        "files_modified": False,
    }


if __name__ == "__main__":
    print("MPW_BUYER_SOURCE_COVERAGE=" +
          json.dumps(audit(), separators=(",", ":"), sort_keys=True))
