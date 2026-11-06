#!/usr/bin/env python3
"""Sanitized, read-only inventory of the effective Saeit Django interpreter.

Run from the Saeit project root with the SAME virtualenv interpreter used by
Passenger, for example:
  /home/zomorod2/virtualenv/Saeit/3.10/bin/python -B scripts/zomorod_runtime_inventory.py

Does not connect to the database, execute migrations, install dependencies,
restart Passenger, or print environment variables, DATABASE_URL, or secrets.
Only the known top-level config.settings module is imported to inspect its
already-resolved DATABASES and INSTALLED_APPS settings.
"""

import importlib
import json
import sys
from importlib import metadata

sys.dont_write_bytecode = True

DIST_NAMES = ("Django", "Pillow", "psycopg", "cryptography")
ENGINE_FAMILIES = {
    "django.db.backends.sqlite3": "sqlite",
    "django.db.backends.mysql": "mysql_or_mariadb",
    "django.db.backends.postgresql": "postgresql",
    "django.db.backends.oracle": "oracle",
}


def inventory():
    result = {
        "schema": 1,
        "python_version": ".".join(str(value) for value in sys.version_info[:3]),
        "package_versions": {},
        "settings_status": "unavailable",
        "database_backend": "unknown",
        "gis_enabled": None,
    }

    for name in DIST_NAMES:
        try:
            result["package_versions"][name] = metadata.version(name)
        except metadata.PackageNotFoundError:
            result["package_versions"][name] = None

    try:
        # Do not use django.setup(): the database connection is not needed.
        settings = importlib.import_module("config.settings")
        databases = getattr(settings, "DATABASES", None)
        if not isinstance(databases, dict):
            raise TypeError("invalid databases mapping")
        default = databases.get("default")
        if not isinstance(default, dict):
            raise TypeError("invalid default database")
        engine = default.get("ENGINE", "")
        result["database_backend"] = ENGINE_FAMILIES.get(engine, "unrecognized")
        apps = getattr(settings, "INSTALLED_APPS", ())
        result["gis_enabled"] = "django.contrib.gis" in apps
        result["settings_status"] = "loaded"
    except Exception as error:
        # Exception messages may embed credentials. Never print them.
        result["settings_error_class"] = type(error).__name__

    return result


def main():
    result = inventory()
    print(json.dumps(result, ensure_ascii=True, sort_keys=True))
    if result["settings_status"] != "loaded":
        return 2
    if result["package_versions"]["Django"] is None:
        return 2
    if result["database_backend"] in ("unknown", "unrecognized"):
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
