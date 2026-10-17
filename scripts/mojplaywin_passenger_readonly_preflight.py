#!/usr/bin/env python3
"""READ ONLY cPanel Passenger isolation preflight for MojPlayWin MAIN.

Run on the authorized cPanel host as the deployment account via the existing
pinned GitHub-to-VPS SSH relay. Prints no secrets or WSGI source content.
Never creates/changes files, reloads Passenger, changes the database, or
touches any independent child site.

A shared Saeit-staging Passenger process is an automatic NO-GO.
Absence of that marker is NOT proof of independent-site safety; an operator
must still verify DB/media domains, protected route checks, and rollback.
"""
from __future__ import annotations

import json
from pathlib import Path

DOCROOT = Path("/home/zomorod2/mojplaywin.com")
SHARED_APP_MARKER = "Saeit-staging"


def audit() -> dict:
    checks = {}
    wsgi = DOCROOT / "passenger_wsgi.py"
    conf = DOCROOT / ".htaccess"
    checks["docroot_exists"] = DOCROOT.is_dir() and not DOCROOT.is_symlink()
    checks["wsgi_exists"] = wsgi.is_file() and not wsgi.is_symlink()
    checks["htaccess_exists"] = conf.is_file() and not conf.is_symlink()
    checks["shared_app_reference_found"] = None
    checks["route_isolation_proven"] = False
    checks["payment_inventory_backups_verified"] = False
    checks["release_permitted"] = False
    if checks["wsgi_exists"]:
        try:
            source = wsgi.read_text(encoding="utf-8", errors="replace")
            checks["shared_app_reference_found"] = SHARED_APP_MARKER in source
        except OSError:
            checks["shared_app_reference_found"] = None
    if checks["shared_app_reference_found"]:
        checks["blocker"] = "MojPlayWin Passenger WSGI references shared Saeit-staging application; restart may affect other sites"
    else:
        checks["blocker"] = "Passenger, database, protected routes and rollback not independently verified; fail closed"
    return checks


def main():
    result = audit()
    print(json.dumps({"classification": "READ_ONLY_NOT_DEPLOYABLE", **result}, sort_keys=True))
    raise SystemExit(0 if result["release_permitted"] else 3)


if __name__ == "__main__":
    main()
