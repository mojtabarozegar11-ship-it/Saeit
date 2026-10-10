#!/usr/bin/env python3
"""Safe, read-only staging DB configuration preflight; never prints credentials."""
from pathlib import Path
from urllib.parse import urlsplit, unquote
import os
import sys

def load_env(path):
    values = {}
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip("\"'")
    return values

def check(values):
    url = values.get("DATABASE_URL", "")
    stage = values.get("STAGING_DB_IDENTITY", "")
    production = values.get("PRODUCTION_DB_IDENTITY", "")
    try:
        parsed = urlsplit(url)
        name = unquote(parsed.path.lstrip("/"))
        scheme_ok = parsed.scheme in ("postgres", "postgresql")
        # Literal @ in credentials must be percent-encoded in a PostgreSQL URL.
        authority = url.split("://", 1)[1].split("/", 1)[0] if "://" in url else ""
        authority_ok = authority.count("@") == 1
        identity_ok = bool(stage and production and name == stage and name != production)
        environment_ok = values.get("SAEIT_ENV", "").lower() == "staging"
        debug_ok = values.get("DEBUG", "").lower() in ("false", "0")
        host_ok = bool(parsed.hostname) and bool(parsed.username)
    except (ValueError, AttributeError):
        scheme_ok = authority_ok = identity_ok = environment_ok = debug_ok = host_ok = False
    checks = {
        "STAGING_ENV": environment_ok,
        "DEBUG_DISABLED": debug_ok,
        "POSTGRES_SCHEME": scheme_ok,
        "CREDENTIAL_URL_ENCODING": authority_ok,
        "STAGING_IDENTITY_ISOLATION": identity_ok,
        "HOST_AND_USERNAME_PRESENT": host_ok,
    }
    for key, valid in checks.items():
        print(f"{key}={'PASS' if valid else 'FAIL'}")
    return all(checks.values())

if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else ".env"
    try:
        sys.exit(0 if check(load_env(path)) else 2)
    except (OSError, UnicodeError):
        print("ENV_READ=FAIL")
        sys.exit(2)
