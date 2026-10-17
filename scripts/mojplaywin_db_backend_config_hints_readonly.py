#!/usr/bin/env python3
"""Sanitized read-only candidate Django DATABASE_URL backend hints.

No DB calls, no connection, no subprocess, no file writes or Passenger restart.
Only opens four tightly scoped .env files on the authorized hosting account.
Never prints configuration lines, credentials, paths, user data or URL values.
Does not claim to know effective Passenger runtime configuration.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

APP = Path("/home/zomorod2/Saeit-staging")
WEB = Path("/home/zomorod2/mojplaywin.com")
ALLOWED_NAMES = (".env", ".env.production", ".env.local")
MAX_BYTES = 65536


def safely_read(path: Path) -> str | None:
    try:
        if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_BYTES:
            return None
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None


def category(source: str) -> str | None:
    values = []
    for line in source.splitlines():
        match = re.match(r"^\s*(?:export\s+)?DATABASE_URL\s*=\s*(.*?)\s*$", line)
        if not match:
            continue
        raw = match.group(1).strip()
        if len(raw) >= 2 and raw[0] in ('"', "'") and raw[-1] == raw[0]:
            raw = raw[1:-1]
        scheme = re.match(r"^([a-zA-Z][a-zA-Z0-9+.-]*):", raw)
        if scheme is None:
            values.append("unrecognized")
            continue
        proto = scheme.group(1).lower()
        if proto in ("postgres", "postgresql", "postgis", "pgsql"):
            values.append("postgresql")
        elif proto in ("mysql", "mysql2", "mariadb"):
            values.append("mysql_mariadb")
        elif proto in ("sqlite", "sqlite3"):
            values.append("sqlite")
        else:
            values.append("other_unrecognized")
    if not values:
        return None
    return values[0] if len(set(values)) == 1 else "ambiguous"


def inspect(app: Path = APP, web: Path = WEB) -> dict:
    files = [app / key for key in ALLOWED_NAMES] + [web / ".env"]
    categories = []
    readable = 0
    for f in files:
        source = safely_read(f)
        if source is not None:
            readable += 1
            found = category(source)
            if found:
                categories.append(found)
    unique = set(categories)
    candidate = categories[0] if len(unique) == 1 else "ambiguous" if unique else None
    return {
        "classification": "READ_ONLY_DATABASE_BACKEND_CONFIGURATION_HINTS",
        "scoped_files_checked": len(files),
        "scoped_config_files_readable": readable,
        "scoped_config_files_with_database_url": len(categories),
        "candidate_backend_category": candidate,
        "effective_passenger_runtime_backend_confirmed": False,
        "actual_db_name_and_location_confirmed": False,
        "full_database_backup_created": False,
        "restore_test_verified": False,
        "release_permitted": False,
        "limitations": "Config-file hints are not proof of runtime environment; production may use dynamically injected settings or external databases.",
    }


if __name__ == "__main__":
    print(json.dumps(inspect(), sort_keys=True))
