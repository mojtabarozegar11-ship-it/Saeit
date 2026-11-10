#!/usr/bin/env python3
"""Read-only production evidence for MojPlayWin guest checkout.

Queries only Django's migration history and database table names. Does not
read customer/order rows, issue invoices, send mail, run migrations, or deploy.
Not a certification of paid commerce, ownership, or recovery delivery.

Run only in the authorized cPanel Python environment, with SAEIT_ENV=production.
"""
from __future__ import annotations

import hashlib
import json
import os
import pwd
import re
import sys
from pathlib import Path

APP = Path("/home/zomorod2/Saeit-staging")
PUBLIC = Path("/home/zomorod2/mojplaywin.com")
MIGRATIONS = (
    ("core", "0049_mpw_guest_email_recovery",
     ("core_guestorderemail", "core_guestrecoverytoken", "core_guestrecoveryrate")),
    ("mpw_commerce", "0004_guesttrxdelivery", ("mpw_commerce_guesttrxdelivery",)),
)
FEATURE_FLAGS = (
    "MPW_GUEST_EMAIL_SEND_APPROVED",
    "MPW_GUEST_RECOVERY_EMAIL_APPROVED",
)
SOURCE_PATHS = (
    "services/mpw_trx_guest_commerce.py",
    "services/mpw_trx_email_recovery.py",
    "services/mpw_trx_commercial_web.py",
    "services/mpw_trx_commercial_context.py",
    "services/mpw_trx_public_catalog.py",
    "services/mpw_trx_guest_delivery.py",
    "services/mpw_trx_public_pages.py",
    "config/urls.py",
)


def stop(code: str) -> None:
    print(json.dumps({"probe": "mpw_guest_runtime_readiness",
                      "read_only": True, "status": "blocked", "reason": code},
                     sort_keys=True))
    raise SystemExit(2)


def registered_passenger_root(text: str) -> bool:
    """Validate the declared Passenger root, without trusting a bootstrap alone.

    A checked-in or stale passenger_wsgi.py is not proof that .htaccess is
    configured to serve it. Require a single unambiguous PassengerAppRoot.
    """
    roots = re.findall(r"(?im)^[ \t]*PassengerAppRoot[ \t]+([^\r\n#]+)", text)
    if len(roots) != 1:
        return False
    value = roots[0].strip()
    if len(value) >= 2 and value[0] in ("'", '"') and value[-1] == value[0]:
        value = value[1:-1]
    elif "'" in value or '"' in value:
        return False
    return value.rstrip("/") in (str(PUBLIC), "mojplaywin.com")


def main() -> None:
    if pwd.getpwuid(os.geteuid()).pw_name != "zomorod2":
        stop("WRONG_CPANEL_USER")
    for root in (APP, PUBLIC):
        if root.is_symlink() or not root.is_dir() or root.resolve() != root:
            stop("UNSAFE_APPLICATION_ROOT")
    bootstrap = PUBLIC / "passenger_wsgi.py"
    if (bootstrap.is_symlink() or not bootstrap.is_file()
            or "APP='/home/zomorod2/Saeit-staging'"
            not in bootstrap.read_text(encoding="utf-8", errors="replace")):
        stop("PUBLIC_BOOTSTRAP_MISMATCH")
    htaccess = PUBLIC / ".htaccess"
    if (htaccess.is_symlink() or not htaccess.is_file()
            or htaccess.stat().st_size > 100000):
        stop("PUBLIC_PASSENGER_ROOT_UNSAFE")
    if not registered_passenger_root(
            htaccess.read_text(encoding="utf-8", errors="replace")):
        stop("PUBLIC_PASSENGER_ROOT_MISMATCH")
    if os.environ.get("SAEIT_ENV") != "production":
        stop("PRODUCTION_ENV_NOT_EXPLICIT")
    if os.environ.get("DJANGO_SETTINGS_MODULE") not in (None, "config.settings"):
        stop("UNEXPECTED_DJANGO_SETTINGS")
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    sys.path.insert(0, str(APP))
    os.chdir(APP)

    try:
        import django
        django.setup()
        from django.conf import settings
        from django.db import connections
        from django.urls import resolve

        connection = connections["default"]
        with connection.cursor() as cursor:
            present_tables = {name.lower()
                              for name in connection.introspection.table_names(cursor)}
            history = set()
            if "django_migrations" in present_tables:
                # Migration metadata ONLY; no query touches Order/Payment/Email tables.
                cursor.execute(
                    "SELECT app, name FROM django_migrations WHERE "
                    "(app = %s AND name = %s) OR (app = %s AND name = %s)",
                    [MIGRATIONS[0][0], MIGRATIONS[0][1],
                     MIGRATIONS[1][0], MIGRATIONS[1][1]],
                )
                history = set(cursor.fetchall())

        migration_evidence = {}
        for app, name, tables in MIGRATIONS:
            filename = APP / app / "migrations" / (name + ".py")
            migration_evidence[f"{app}.{name}"] = {
                "source_exists": filename.is_file() and not filename.is_symlink(),
                "recorded_as_applied": (app, name) in history,
                "required_tables_present": {
                    table: table.lower() in present_tables for table in tables
                },
            }

        route_evidence = {}
        for path in ("/commerce/book/879/", "/commerce/trx-easy/start/879/"):
            match = resolve(path)
            route_evidence[path] = {
                "resolved": True,
                "handler_module": getattr(match.func, "__module__", "unknown"),
                "handler_name": getattr(match.func, "__name__", "unknown"),
            }

        fingerprints = {}
        for relative in SOURCE_PATHS:
            p = APP / relative
            if p.is_symlink() or not p.is_file() or p.stat().st_size > 300000:
                fingerprints[relative] = "unavailable"
            else:
                fingerprints[relative] = hashlib.sha256(p.read_bytes()).hexdigest()

        flags = {name: getattr(settings, name, False) is True
                 for name in FEATURE_FLAGS}
        all_schemas = all(
            item["source_exists"] and item["recorded_as_applied"]
            and all(item["required_tables_present"].values())
            for item in migration_evidence.values()
        )
        payload = {
            "probe": "mpw_guest_runtime_readiness",
            "read_only": True,
            "status": "evidence_collected",
            "scope": "passenger_schema_route_flags_and_source_fingerprints_only",
            "passenger_registered_root_matches_public": True,
            "migration_evidence": migration_evidence,
            "route_evidence": route_evidence,
            "feature_flags_boolean": flags,
            "source_sha256": fingerprints,
            "source_inventory_complete": all(
                digest != "unavailable" for digest in fingerprints.values()
            ),
            "schema_consistent": all_schemas,
            "recovery_email_currently_approved": flags[
                "MPW_GUEST_RECOVERY_EMAIL_APPROVED"
            ],
            "commercial_release_certified": False,
            "customer_rows_read": 0,
            "orders_created": 0,
            "payments_created": 0,
            "emails_sent": 0,
        }
        print(json.dumps(payload, sort_keys=True, ensure_ascii=True))
        raise SystemExit(0 if all_schemas else 3)
    except SystemExit:
        raise
    except Exception:
        # Deliberately do not print exceptions, DB names, settings or credentials.
        stop("RUNTIME_METADATA_UNAVAILABLE")


if __name__ == "__main__":
    main()
