"""Read-only fingerprint of the *actual connected* Moj Prop MariaDB.

Binds separately signed restore evidence to the configured database AND the
database selected by a real read-only SELECT DATABASE() query. Never emits
credentials, connects in tests, executes DDL, or proves restore by itself.
"""
from __future__ import annotations

import hashlib
import json
import os


def database_identity_digest(settings: dict, selected_database: str) -> str:
    if type(settings) is not dict:
        raise RuntimeError("Moj Prop database settings unavailable")
    engine = settings.get("ENGINE")
    if engine != "django.db.backends.mysql":
        raise RuntimeError("Moj Prop commercial release requires MariaDB/MySQL")
    name = str(settings.get("NAME") or "").strip()
    user = str(settings.get("USER") or "").strip()
    actual = str(selected_database or "").strip()
    if not name or not user or not actual or actual != name:
        raise RuntimeError("actual connected database does not match release settings")
    # Passwords, DSNs and secrets are intentionally excluded.
    public_identity = {
        "engine": engine,
        "name": actual,
        "host": str(settings.get("HOST") or "localhost").strip().lower(),
        "port": str(settings.get("PORT") or "default").strip(),
        "user": user,
    }
    canonical = json.dumps(
        public_identity, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("ascii")
    return hashlib.sha256(b"MOJPROP_CONNECTED_DB_V1\n" + canonical).hexdigest()


def live_connected_database_identity_sha256() -> str:
    """Read one actual connected database identity, without mutating anything."""
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    import django
    django.setup()
    from django.db import connections
    connection = connections["default"]
    if connection.vendor != "mysql":
        raise RuntimeError("unapproved live DB engine for Moj Prop commercial release")
    with connection.cursor() as cursor:
        cursor.execute("SELECT DATABASE()")
        row = cursor.fetchone()
    if not row or type(row[0]) is not str:
        raise RuntimeError("could not verify selected live database")
    return database_identity_digest(connection.settings_dict, row[0])


if __name__ == "__main__":
    # A read-only runtime fingerprint; never print URL/password/username.
    print(live_connected_database_identity_sha256())
