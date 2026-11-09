#!/usr/bin/env python3
"""C32: route/feature-flag metadata only; never invoke Django HTTP views.

This is an offline-friendly cPanel deployment candidate. A URL resolver match
is only configuration evidence, not proof that checkout works or sells.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path("/home/zomorod2/Saeit-staging")
if not ROOT.is_dir() or ROOT.is_symlink():
    raise RuntimeError("UNEXPECTED_LIVE_RUNTIME_ROOT")
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django
django.setup()

from django.conf import settings
from django.urls import resolve, Resolver404


ROUTES = (
    "/accounts/login/", "/accounts/register/", "/store/",
    "/store/product/72/checkout/", "/commerce/book/72/",
    "/commerce/book/779/",
)
FLAG_NAMES = (
    "MPW_COMMERCE_RELEASE_READY", "MPW_COMMERCE_CUSTOMER_HTTP_ENABLED",
    "MPW_COMMERCE_INVOICING_ENABLED", "MPW_COMMERCE_SETTLEMENT_ENABLED",
    "MPW_COMMERCE_REAL_RPC_ENABLED", "MPW_COMMERCE_AUTORECONCILE_ENABLED",
    "MPW_COMMERCE_DOWNLOADS_ENABLED",
)


def route_coverage(resolver, paths):
    """Resolve paths without invoking any view or creating a Django Client."""
    results = []
    for path in paths:
        try:
            resolver(path)
            results.append(True)
        except (Resolver404, LookupError):
            results.append(False)
    return results


def run():
    coverage = route_coverage(resolve, ROUTES)
    flags = {name: getattr(settings, name, False) is True for name in FLAG_NAMES}
    print("MPW_RUNTIME_FLAGS_AGGREGATE_READONLY=" + json.dumps({
        "checkout_scope": "cryptocurrency_only",
        "payment_flow_assessment": "NOT_TESTED_BY_READ_ONLY_PROBE",
        "live_paid_end_to_end_verified_by_this_probe": False,
        "private_data_emitted": False,
        "crypto_runtime_feature_flags": flags,
        "route_count_checked": len(coverage),
        "route_count_resolved": sum(coverage),
        "http_view_invocations": 0,
    }, sort_keys=True))
    if not all(coverage):
        raise SystemExit("MPW_REQUIRED_ROUTES_UNRESOLVED")


if __name__ == "__main__":
    run()
