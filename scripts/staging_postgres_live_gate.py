#!/usr/bin/env python3
"""Read-only staging gate: check live Django/PostgreSQL connectivity without printing secrets.

Run inside the existing staging venv, from the staging checkout after loading
its environment variables. Does not modify DB schema, products or evidence.
"""
import os
import sys

def main():
    if os.environ.get("SAEIT_ENV", "staging").lower() != "staging":
        print("STAGING_IDENTITY=FAIL")
        return 2
    if os.environ.get("DEBUG", "false").lower() not in {"false", "0"}:
        print("DEBUG_DISABLED=FAIL")
        return 2
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    try:
        import django
        django.setup()
        from django.conf import settings
        from django.db import connection
        # Django loads staging .env from config/settings.py; it need not be exported.
        if getattr(settings, "SAEIT_ENV", "") != "staging" or settings.DEBUG:
            print("DJANGO_STAGING_SETTINGS=FAIL")
            return 2
        print("DJANGO_STAGING_SETTINGS=PASS")
        if connection.vendor != "postgresql":
            print("DATABASE_BACKEND=FAIL")
            return 2
        print("DATABASE_BACKEND=PASS")
        with connection.cursor() as cursor:
            cursor.execute("SELECT current_database(), 1")
            database_name, value = cursor.fetchone()
        stage = str(getattr(settings, "STAGING_DB_IDENTITY", "") or "")
        production = str(getattr(settings, "PRODUCTION_DB_IDENTITY", "") or "")
        if not stage or not production or stage == production or database_name != stage or value != 1:
            print("STAGING_DB_ISOLATION=FAIL")
            return 2
        print("STAGING_DB_ISOLATION=PASS")
        print("LIVE_POSTGRES_READONLY_QUERY=PASS")
        return 0
    except Exception:
        # Intentionally suppress exception text: database errors may contain
        # usernames, hostnames or connection details.
        print("LIVE_POSTGRES_READONLY_QUERY=FAIL")
        return 2

if __name__ == "__main__":
    sys.exit(main())
