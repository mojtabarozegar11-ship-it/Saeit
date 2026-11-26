#!/usr/bin/env python3
"""Read-only runtime preflight for the Signal Desk subscription contract.

This command never migrates, creates orders, issues invoices, changes settings,
or enables a public payment route. It is intended to run before an owner-approved
runtime migration.
"""
from __future__ import annotations

import json
import os
import sys


EXPECTED_TERMS = {
    "education-weekly": 1,
    "education-monthly": 4,
    "education-quarterly": 12,
}
RELEASE_FLAGS = (
    "MPW_WALLETLESS_TRX_PUBLIC_ENABLED",
    "MPW_WALLETLESS_TRX_MERCHANT_CANARY_PASSED",
    "MPW_COMMERCE_RELEASE_READY",
)


def collect_report() -> dict:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    import django

    django.setup()

    from django.apps import apps
    from django.conf import settings
    from django.db import connection
    from django.db.migrations.recorder import MigrationRecorder
    from mpw_commerce.signal_subscriptions import TERMS
    from services.mojtaba_signal_catalog import PLANS

    applied = MigrationRecorder(connection).migration_qs.filter(
        app="mpw_commerce", name="0005_align_weekly_signal_terms"
    ).exists()
    model = apps.get_model("mpw_commerce", "SignalSubscription")
    table_names = set(connection.introspection.table_names())
    terms = dict(TERMS)
    catalog_prices = {
        plan_id: format(plan.price_usd, "f")
        for plan_id, plan in PLANS.items()
    }
    return {
        "read_only": True,
        "database_alias": connection.alias,
        "database_vendor": connection.vendor,
        "signal_subscription_table": model._meta.db_table,
        "signal_subscription_table_exists": model._meta.db_table in table_names,
        "weekly_terms_migration_applied": applied,
        "terms_match_expected": terms == EXPECTED_TERMS,
        "catalog_plan_ids_match_terms": set(PLANS) == set(TERMS),
        "catalog_prices_usd": catalog_prices,
        "payment_flags": {
            name: getattr(settings, name, None) for name in RELEASE_FLAGS
        },
        "public_signal_subscription_enabled": False,
        "note": "Source/schema preflight only; no payment or delivery is authorized.",
    }


def main() -> int:
    report = collect_report()
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    required = (
        report["signal_subscription_table_exists"],
        report["weekly_terms_migration_applied"],
        report["terms_match_expected"],
        report["catalog_plan_ids_match_terms"],
    )
    return 0 if all(required) else 2


if __name__ == "__main__":
    sys.exit(main())
