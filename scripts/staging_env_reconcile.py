#!/usr/bin/env python3
"""Read-only, credential-redacted staging configuration reconciliation.

Usage: python scripts/staging_env_reconcile.py .env .env.backup.*
Does not connect to databases, modify files, or print any credentials/DB names.
"""
import sys
from pathlib import Path
from urllib.parse import urlsplit, unquote


def read_values(path):
    result = {}
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        result[key.strip()] = value.strip().strip("\\\"'")
    return result


def inspect(values):
    url = values.get("DATABASE_URL", "")
    try:
        parsed = urlsplit(url)
        authority = url.split("://", 1)[1].split("/", 1)[0]
        dbname = unquote(parsed.path.lstrip("/").split("?", 1)[0])
        return {
            "postgres": parsed.scheme in ("postgresql", "postgres"),
            "authority_encoded": authority.count("@") == 1,
            "local": parsed.hostname in ("127.0.0.1", "localhost"),
            "db_matches_stage": bool(dbname and dbname == values.get("STAGING_DB_IDENTITY")),
            "db_differs_prod": bool(dbname and values.get("PRODUCTION_DB_IDENTITY") and dbname != values["PRODUCTION_DB_IDENTITY"]),
            "stage_identity": values.get("STAGING_DB_IDENTITY", ""),
            "staging": values.get("SAEIT_ENV", "").lower() == "staging",
            "debug_off": values.get("DEBUG", "").lower() in ("false", "0"),
        }
    except (ValueError, IndexError, AttributeError):
        return {key: False for key in ("postgres", "authority_encoded", "local", "db_matches_stage", "db_differs_prod", "staging", "debug_off")} | {"stage_identity": ""}


def main(paths):
    if len(paths) < 2:
        print("USAGE: staging_env_reconcile.py CURRENT_ENV BACKUP_ENV [BACKUP_ENV ...]")
        return 2
    try:
        current = inspect(read_values(paths[0]))
        for index, path in enumerate(paths[1:], 1):
            candidate = inspect(read_values(path))
            same_identity = bool(candidate["stage_identity"] and candidate["stage_identity"] == current["stage_identity"])
            for key in ("postgres", "authority_encoded", "local", "db_matches_stage", "db_differs_prod", "staging", "debug_off"):
                print(f"CANDIDATE_{index}_{key.upper()}={'PASS' if candidate[key] else 'FAIL'}")
            print(f"CANDIDATE_{index}_MATCHES_CURRENT_STAGING_ID={'PASS' if same_identity else 'FAIL'}")
            print(f"CANDIDATE_{index}_AUTHENTICATED_DB_OWNERSHIP=UNVERIFIED")
            print(f"CANDIDATE_{index}_AUTOMATIC_RESTORE=BLOCKED")
        return 0
    except (OSError, UnicodeError):
        print("CONFIG_READ=FAIL")
        return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
