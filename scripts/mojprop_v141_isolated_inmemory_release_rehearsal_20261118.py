#!/usr/bin/env python3
"""Test owner-cPanel Python+MOJPROP model lineage using IN-MEMORY SQLite only.

No connection to merchant DB, customer records, wallet, .env, host secrets.
No persistent database, production migrations, money or public routes.
"""
import json
import os
from pathlib import Path
import sys

STAGE = Path("/home/zomorod2/.mojprop-private-payment-stage-44220183128")
REQUIRED = (
    "prop_firm/models.py",
    "prop_firm/migrations/0012_v141_native_trx_receipt.py",
    "prop_firm/plan1_v141_native_checkout.py",
    "prop_firm/plan1_v141_native_watcher.py",
    "prop_firm/management/commands/mojprop_reconcile_native_trx.py",
    "services/mojprop_commercial_lanes.py",
)
report = {
    "schema": "mojprop.private.cpanel.inmemory.v1",
    "private_stage_exists": STAGE.is_dir() and not STAGE.is_symlink(),
    "all_sources_regular": False,
    "django_setup_ok": False,
    "model_check_ok": False,
    "in_memory_migrations_ok": False,
    "models_present": False,
    "native_payment_disabled": None,
    "production_database_touched": False,
    "customer_record_read": False,
    "wallet_broadcast": False,
    "public_files_modified": False,
    "persistent_test_db_created": False,
}
try:
    assert report["private_stage_exists"], "No known private owner stage"
    assert all((STAGE / f).is_file() and not (STAGE/f).is_symlink()
               for f in REQUIRED), "Required staged source absent"
    report["all_sources_regular"] = True
    sys.path.insert(0,str(STAGE))
    from django.conf import settings
    assert not settings.configured, "Unexpected imported production settings"
    settings.configure(
        SECRET_KEY="not-a-production-key-for-memory-only-check",
        DEBUG=False, USE_TZ=True, TIME_ZONE="UTC",
        INSTALLED_APPS=[
            "django.contrib.auth",
            "django.contrib.contenttypes",
            "django.contrib.sessions",
            "prop_firm.apps.MojPropConfig",
        ],
        DATABASES={"default":{"ENGINE":"django.db.backends.sqlite3",
                              "NAME":":memory:"}},
        MIDDLEWARE=[], DEFAULT_AUTO_FIELD="django.db.models.BigAutoField",
        PASSWORD_HASHERS=["django.contrib.auth.hashers.PBKDF2PasswordHasher"],
        MOJPROP_V141_NATIVE_TRX_RELEASE_ENABLED=False,
        MOJPROP_TRX_GLOBAL_LEDGER_RECONCILED=False,
        MOJPROP_TRX_AUTORECONCILE_ENABLED=False,
    )
    import django
    django.setup()
    report["django_setup_ok"] = True
    from django.core.management import call_command
    from django.core.management.base import CommandError
    from django.core.checks import run_checks
    issues=[e for e in run_checks() if e.is_serious()]
    if issues:
        raise RuntimeError("Django model checks failed: "+str([e.id for e in issues]))
    report["model_check_ok"] = True
    # Only memory-bound SQLite connection, no host DB creds or open production URL.
    call_command("migrate", database="default", interactive=False,
                 verbosity=0, run_syncdb=True)
    report["in_memory_migrations_ok"] = True
    from django.apps import apps
    for name in ("PropV141NativeOrder", "PropV141NativeReceipt",
                 "PropGlobalTRXSettlement", "PropV141SimState",
                 "PropV141VirtualBook"):
        assert apps.get_model("prop_firm",name)
    report["models_present"] = True
    from prop_firm.plan1_v141_native_checkout import _release_enabled
    assert not _release_enabled()
    report["native_payment_disabled"] = True
    from django.core.management import call_command
    from io import StringIO
    try:
        call_command("mojprop_reconcile_native_trx", stdout=StringIO())
    except CommandError:
        pass
    else:
        raise RuntimeError("Watcher command did not fail closed")
except Exception as exc:
    report["error_kind"]=type(exc).__name__
    report["error_summary"]=str(exc)[:170].replace(str(STAGE),"<private-stage>")
finally:
    print("MOJPROP_CPANEL_MEMORY_REHEARSAL="+json.dumps(report,sort_keys=True))
if not all(report[k] for k in (
   "private_stage_exists","all_sources_regular",
   "django_setup_ok","model_check_ok","in_memory_migrations_ok",
   "models_present","native_payment_disabled")):
    raise SystemExit(1)
