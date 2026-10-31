#!/usr/bin/env python3
"""Read-only connectivity check using the checkout's Passenger-loaded Django settings.

This does not load the WSGI application or app models, run migrations, read rows,
or claim that the query ran inside an already-running Passenger worker.
"""
import json
import os
from pathlib import Path

EXPECTED_APP_ROOT = Path("/home/zomorod2/Saeit-staging")
EXPECTED_DATABASE_NAME = "zomorod2_sites_main"


def readonly_select1(connection, engine, database_name, expected_name=EXPECTED_DATABASE_NAME):
    result = {
        "app_settings_readonly_select1_verified": False,
        "passenger_worker_db_authority_verified": False,
        "database_name_matches_expected": database_name == expected_name,
        "engine_family": "unknown",
        "failure_class": None,
        "customer_rows_read": 0,
        "business_rows_read": 0,
        "query_kind": "constant_select_1",
        "database_modified": False,
        "migrations_run": False,
    }
    if database_name != expected_name:
        result["failure_class"] = "database_scope_mismatch"
        return result

    engine = str(engine or "").lower()
    if engine.endswith(".mysql") or "mysql" in engine or "mariadb" in engine:
        family = "mysql"
        statements = ("START TRANSACTION READ ONLY", "SELECT 1")
    elif engine.endswith(".sqlite3") or "sqlite" in engine:
        family = "sqlite"
        statements = ("PRAGMA query_only = ON", "BEGIN", "SELECT 1")
    else:
        result["failure_class"] = "unsupported_database_backend"
        return result
    result["engine_family"] = family

    cursor = None
    transaction_started = False
    try:
        cursor = connection.cursor()
        for statement in statements:
            cursor.execute(statement)
            if statement.startswith("START TRANSACTION") or statement == "BEGIN":
                transaction_started = True
            if statement == "SELECT 1":
                row = cursor.fetchone()
                if row != (1,):
                    raise RuntimeError("unexpected_select_result")
        cursor.execute("ROLLBACK")
        transaction_started = False
        result["app_settings_readonly_select1_verified"] = True
    except Exception as exc:
        result["failure_class"] = type(exc).__name__
        if cursor is not None and transaction_started:
            try:
                cursor.execute("ROLLBACK")
            except Exception:
                pass
    finally:
        if cursor is not None:
            try:
                cursor.close()
            except Exception:
                pass
    return result


def load_passenger_env(env_path):
    if not env_path.is_file():
        return
    for raw in env_path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key, value = key.strip(), value.strip()
        if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
            value = value[1:-1]
        if key:
            os.environ.setdefault(key, value)


def main():
    try:
        os.chdir(EXPECTED_APP_ROOT)
        load_passenger_env(EXPECTED_APP_ROOT / ".env")
        os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
        from django.conf import settings
        from django.db import connection

        config = settings.DATABASES.get("default", {})
        active = connection.settings_dict
        same_config = (
            str(config.get("ENGINE", "")) == str(active.get("ENGINE", ""))
            and str(config.get("NAME", "")) == str(active.get("NAME", ""))
        )
        if not same_config:
            result = {
                "scope": "S01_PASSENGER_APP_SETTINGS_READONLY_DB_PROBE",
                "app_root_matches_expected": True,
                "app_settings_readonly_select1_verified": False,
                "passenger_worker_db_authority_verified": False,
                "database_name_matches_expected": False,
                "engine_family": "unknown",
                "failure_class": "settings_connection_mismatch",
                "customer_rows_read": 0,
        "business_rows_read": 0,
        "query_kind": "constant_select_1",
                "database_modified": False,
                "migrations_run": False,
            }
        else:
            result = readonly_select1(
                connection,
                active.get("ENGINE"),
                active.get("NAME"),
            )
            result.update({
                "scope": "S01_PASSENGER_APP_SETTINGS_READONLY_DB_PROBE",
                "app_root_matches_expected": True,
            })
    except Exception as exc:
        result = {
            "scope": "S01_PASSENGER_APP_SETTINGS_READONLY_DB_PROBE",
            "app_root_matches_expected": False,
            "app_settings_readonly_select1_verified": False,
            "passenger_worker_db_authority_verified": False,
            "database_name_matches_expected": False,
            "engine_family": "unknown",
            "failure_class": type(exc).__name__,
            "customer_rows_read": 0,
        "business_rows_read": 0,
        "query_kind": "constant_select_1",
            "database_modified": False,
            "migrations_run": False,
        }
    print("S01_PASSENGER_APP_CONFIG_DB_READONLY=" + json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
