#!/usr/bin/env python3
"""One-time zero-customer isolated MOJ PROP private DB creation/recovery drill.

DOES NOT TOUCH the giant MojPlayWin production DB, document root, or server
network. Uses separately staged verified source, zero customer payment, no
website activation. Never deletes existing files, does not repeat migration
on an unexpected existing database and refuses symlinks.
"""
from pathlib import Path
import json
import os
import sqlite3
import stat
import sys

ROOT=Path("/home/zomorod2")
STAGE=ROOT/".mojprop-private-payment-stage-44223002898"
PRIVATE=ROOT/".mojprop-native-v141-isolated-20261118"
SQLITE=PRIVATE/"merchant.sqlite3"
BACKUP=PRIVATE/"merchant-initial-snapshot.sqlite3"
RESTORED=PRIVATE/"recovery-verification.sqlite3"
REQUIRED=(
    "prop_firm/models.py","prop_firm/migrations/0012_v141_native_trx_receipt.py",
    "prop_firm/consent_guard_queryset.py",
    "prop_firm/plan1_v141_native_checkout.py",
)
report={
    "schema":"mojprop.v141.private_sqlite_first_install.recovery.v1",
    "separate_private_store":False,
    "source_pin":"a07c6a69847732087fefd3116806a2b2a57037b0",
    "independent_auth_models":False,
    "sqlite_migrations_through_0012":False,
    "merchant_order_table_present":False,
    "settlement_unique_index_present":False,
    "db_integrity_check_passed":False,
    "initial_snapshot_verified":False,
    "isolated_restore_test_passed":False,
    "private_permissions":False,
    "db_size_kib":0,
    "production_mariadb_accessed":False,
    "live_application_modified":False,
    "production_payments_enabled":False,
    "customer_data_accessed":False,
    "money_transferred":False,
}
try:
    if os.environ.get("DJANGO_SETTINGS_MODULE"):
        raise RuntimeError("Inherited unsafe production settings")
    if not (STAGE.is_dir() and not STAGE.is_symlink() and
            all((STAGE/x).is_file() and not (STAGE/x).is_symlink()
                for x in REQUIRED)):
        raise RuntimeError("Pinned private stage missing or unsafe")
    if PRIVATE.is_symlink() or any(
            p.is_symlink() for p in (SQLITE,BACKUP,RESTORED)):
        raise RuntimeError("Symlink candidate refused")
    if PRIVATE.exists():
        raise RuntimeError("Private store already exists: never overwrite")
    st=os.statvfs(ROOT)
    if st.f_bavail*st.f_frsize < 30*1024*1024:
        raise RuntimeError("Insufficient local free disk for independent ledger")
    PRIVATE.mkdir(mode=0o700)
    os.chmod(PRIVATE,0o700)
    report["separate_private_store"]=True
    sys.path.insert(0,str(STAGE))
    from django.conf import settings
    settings.configure(
        SECRET_KEY="zero-customer-first-install-only-not-for-website",
        DEBUG=False, USE_TZ=True, TIME_ZONE="UTC",
        INSTALLED_APPS=[
            "django.contrib.auth","django.contrib.contenttypes",
            "django.contrib.sessions","prop_firm.apps.MojPropConfig"
        ],
        DATABASES={"default":{
            "ENGINE":"django.db.backends.sqlite3","NAME":str(SQLITE),
            "OPTIONS":{"timeout":10},
        }},
        MIDDLEWARE=[], DEFAULT_AUTO_FIELD="django.db.models.BigAutoField",
        MOJPROP_V141_NATIVE_TRX_RELEASE_ENABLED=False,
        MOJPROP_TRX_GLOBAL_LEDGER_RECONCILED=False,
        MOJPROP_TRX_AUTORECONCILE_ENABLED=False,
    )
    import django
    django.setup()
    from django.core.management import call_command
    from django.core.checks import run_checks
    if any(e.is_serious() for e in run_checks()):
        raise RuntimeError("Isolated Django checks unsuccessful")
    call_command("migrate",interactive=False,verbosity=0)
    report["sqlite_migrations_through_0012"]=True
    from django.apps import apps
    report["independent_auth_models"]=(
        apps.get_model("auth","User") is not None)
    from prop_firm.plan1_v141_native_checkout import _release_enabled
    if _release_enabled() is not False:
        raise RuntimeError("Payment erroneously enabled")
    from django.db import connection
    connection.close()
    with sqlite3.connect(str(SQLITE)) as c:
        tables={r[0] for r in c.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
        needed={
            "prop_firm_propv141nativeorder",
            "prop_firm_propglobaltrxsettlement",
            "prop_firm_propv141nativereceipt",
            "prop_firm_propv141simstate",
            "prop_firm_propv141virtualbook",
        }
        report["merchant_order_table_present"]=needed <= tables
        indexes=[r for r in c.execute(
            "PRAGMA index_list('prop_firm_propglobaltrxsettlement')")]
        report["settlement_unique_index_present"]=any(
            (r[2]==1 for r in indexes))
        report["db_integrity_check_passed"]=(
            c.execute("PRAGMA integrity_check").fetchone()==("ok",))
        count_original={t:c.execute(
            'SELECT count(*) FROM "'+t+'"').fetchone()[0] for t in needed}
        # Empty paid model tables only; there is NO new customer or invoice.
        if any(count_original.values()):
            raise RuntimeError("Unexpected existing customer/payment in new isolated database")
        # API-backed consistent SQLite snapshot, not filesystem copy of open DB.
        with sqlite3.connect(str(BACKUP)) as b:
            c.backup(b)
    report["initial_snapshot_verified"]=BACKUP.is_file()
    with sqlite3.connect(str(BACKUP)) as b, sqlite3.connect(str(RESTORED)) as r:
        b.backup(r)
        restored_tables={x[0] for x in r.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
        counts_recovered={t:r.execute(
            'SELECT count(*) FROM "'+t+'"').fetchone()[0] for t in needed}
        report["isolated_restore_test_passed"]=(
            needed <= restored_tables
            and counts_recovered==count_original
            and r.execute("PRAGMA integrity_check").fetchone()==("ok",))
    for path in (SQLITE,BACKUP,RESTORED):
        if not path.is_file() or path.is_symlink():
            raise RuntimeError("Private SQLite store file absent or symlink")
        path.chmod(0o600)
    report["private_permissions"]=all(
        stat.S_IMODE(path.stat().st_mode)==0o600
        for path in (SQLITE,BACKUP,RESTORED)
    ) and stat.S_IMODE(PRIVATE.stat().st_mode)==0o700
    report["db_size_kib"]=int((SQLITE.stat().st_size+1023)//1024)
    if not all((report[k] for k in (
        "sqlite_migrations_through_0012","merchant_order_table_present",
        "settlement_unique_index_present","db_integrity_check_passed",
        "isolated_restore_test_passed","private_permissions"
    ))):
        raise RuntimeError("Unfulfilled isolated DB safety proof")
except Exception as exc:
    report["error_kind"]=type(exc).__name__
    report["error_summary"]=str(exc).replace(str(ROOT),"<private-root>")[:150]
finally:
    print("MOJPROP_PRIVATE_DB_FIRST_INSTALL="+json.dumps(report,sort_keys=True))
if not report["isolated_restore_test_passed"]:
    raise SystemExit(1)
