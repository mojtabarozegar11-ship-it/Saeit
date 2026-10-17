#!/usr/bin/env python3
"""Read-only source database connection and filesystem size preflight.

Executed ONLY via pinned cPanel SSH by trusted-main workflow.
A DB URL is accessed locally but never printed; logs show only flags/aggregate
sizes. No SQL mutation, database dump, migration, backup, file write or restart.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import urllib.parse
from pathlib import Path

HOME = Path("/home/zomorod2")
APP = HOME / "Saeit-staging"
DOCROOT = HOME / "mojplaywin.com"
ENV_NAMES = (APP / ".env", APP / ".env.production", APP / ".env.local", DOCROOT / ".env")


def source_url(paths=ENV_NAMES):
    found = []
    for path in paths:
        try:
            if path.is_symlink() or not path.is_file() or path.stat().st_size > 65536:
                continue
            for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
                m = re.match(r"^\s*(?:export\s+)?DATABASE_URL\s*=\s*(.*?)\s*$", line)
                if m:
                    val = m.group(1).strip().strip('"').strip("'")
                    parsed = urllib.parse.urlsplit(val)
                    if parsed.scheme.lower() not in {"mysql", "mariadb", "mysql2"}:
                        return None
                    found.append(parsed)
        except (OSError, ValueError):
            continue
    if len(found) != 1:
        return None
    return found[0]


def cpanel_db_name_matches(name: str) -> bool:
    try:
        p = subprocess.run(
            ["uapi", "--output=json", "Mysql", "list_databases"],
            capture_output=True, timeout=15, check=False,
        )
        if p.returncode != 0 or len(p.stdout) > 300000:
            return False
        env = json.loads(p.stdout)
        data = env.get("result", {})
        return data.get("status") == 1 and isinstance(data.get("data"), list) and (
            len(data["data"]) == 1 and data["data"][0].get("database") == name
        )
    except (OSError, ValueError, subprocess.TimeoutExpired, TypeError, AttributeError):
        return False


def verify_connection(parsed) -> bool:
    try:
        db = urllib.parse.unquote(parsed.path.lstrip("/"))
        user = urllib.parse.unquote(parsed.username or "")
        password = urllib.parse.unquote(parsed.password or "")
        host = parsed.hostname or "localhost"
        if not db or not user or not password or not cpanel_db_name_matches(db):
            return False
        if shutil.which("mariadb") is None:
            return False
        args = ["mariadb", "--no-defaults", "--batch", "--skip-column-names",
                "--host="+host, "--user="+user, "--database="+db,
                "--connect-timeout=5", "--execute=SELECT 1"]
        if parsed.port is not None:
            args.append("--port="+str(parsed.port))
        env = dict(os.environ, MYSQL_PWD=password)
        p = subprocess.run(args, env=env, stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL, timeout=12, check=False)
        return p.returncode == 0
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return False


def path_size(path: Path) -> dict:
    if path.is_symlink() or not path.is_dir():
        return {"exists": False, "bytes": None, "measurement_complete": False}
    try:
        p = subprocess.run(["nice", "-n", "15", "du", "-skx", str(path)],
                           capture_output=True, timeout=15, check=False)
        if p.returncode != 0:
            return {"exists": True, "bytes": None, "measurement_complete": False}
        size_kib = int(p.stdout.split()[0])
        return {"exists": True, "bytes": size_kib * 1024, "measurement_complete": True}
    except (OSError, ValueError, IndexError, subprocess.TimeoutExpired):
        return {"exists": True, "bytes": None, "measurement_complete": False}


def inspect(paths=ENV_NAMES):
    parsed = source_url(paths)
    return {
        "classification": "READ_ONLY_MYSQL_CONNECTION_AND_FILESET_SIZING",
        "config_single_mysql_url": parsed is not None,
        "cPanel_account_has_same_single_database_and_connection_works":
            verify_connection(parsed) if parsed is not None else False,
        "document_root_size": path_size(DOCROOT),
        "shared_django_root_size": path_size(APP),
        "nontransactional_table_count_verified": False,
        "complete_media_inventory_verified": False,
        "backup_created": False,
        "release_permitted": False,
        "limitations": "Connection is read-only SELECT 1; actual live Passenger environment could still differ.",
    }


if __name__ == "__main__":
    try:
        print(json.dumps(inspect(), sort_keys=True))
    except Exception:
        print(json.dumps({"classification": "READ_ONLY_MYSQL_PREFLIGHT_ERROR",
                          "backup_created": False, "release_permitted": False}))
        raise SystemExit(1)
