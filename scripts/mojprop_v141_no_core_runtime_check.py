#!/usr/bin/env python3
"""Production-fidelity standalone Django app import/migrate contract.

This script is safe only when launched as a separate fresh process with
DJANGO_SETTINGS_MODULE absent. Its SQLITE database is ONLY ':memory:'.
It does not inspect, connect to, or write owner production data.
"""
import json
import os
import sys
from pathlib import Path

assert not os.environ.get("DJANGO_SETTINGS_MODULE"), "Must not import live settings"
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from django.conf import settings

settings.configure(
    SECRET_KEY="offline-only-not-for-any-customer-use",
    DEBUG=False, USE_TZ=True, TIME_ZONE="UTC",
    INSTALLED_APPS=[
        "django.contrib.auth", "django.contrib.contenttypes",
        "django.contrib.sessions", "prop_firm.apps.MojPropConfig",
    ],
    DATABASES={"default": {"ENGINE":"django.db.backends.sqlite3","NAME":":memory:"}},
    MIDDLEWARE=[], DEFAULT_AUTO_FIELD="django.db.models.BigAutoField",
    MOJPROP_V141_NATIVE_TRX_RELEASE_ENABLED=False,
    MOJPROP_TRX_GLOBAL_LEDGER_RECONCILED=False,
    MOJPROP_TRX_AUTORECONCILE_ENABLED=False,
)
import django
django.setup()
from django.core.checks import run_checks
errors=[x.id for x in run_checks() if x.is_serious()]
assert not errors, ("Django isolated model checks failed", errors)
from django.core.management import call_command
call_command("migrate", verbosity=0, interactive=False)
from django.apps import apps
assert all(apps.get_model("prop_firm", m) is not None for m in (
    "PropV141NativeOrder","PropGlobalTRXSettlement",
    "PropV141NativeReceipt","PropV141SimState","PropV141VirtualBook",
))
from prop_firm.plan1_v141_native_checkout import _release_enabled
assert _release_enabled() is False
print(json.dumps({"isolated_django_app":True,
    "core_app_not_installed":not apps.is_installed("core"),
    "all_native_payment_schema_migrated_in_memory":True,
    "all_default_payment_gates_off":True,
    "production_database_touched":False,
    "customer_data_read":False},sort_keys=True))
