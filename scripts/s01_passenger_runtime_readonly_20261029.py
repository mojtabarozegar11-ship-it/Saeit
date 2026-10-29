#!/usr/bin/env python3
"""S-01 bounded read-only Passenger process probe. Never disclose environment values.

Process metadata cannot prove effective in-process Django database authority.
No process signals, DB queries, writes, orders, payments, or service restarts.
"""
import json
import os
import re
from pathlib import Path

APP_MARKER = b"/home/zomorod2/Saeit-staging"
MAX_PROCESSES = 1024
MAX_CMDLINE = 4096
MAX_ENVIRON = 65536


def read_bounded(path, limit):
    with open(path, "rb") as stream:
        data = stream.read(limit + 1)
    if len(data) > limit:
        raise ValueError("process metadata exceeds bound")
    return data


def entries(blob):
    return [x for x in blob.split(b"\0") if x]


def probe(proc_root=Path("/proc"), owner_uid=None):
    if owner_uid is None:
        owner_uid = os.getuid()
    result = {
        "scope": "S01_PASSENGER_PROCESS_METADATA_READONLY",
        "proc_readable": False, "scanned_own_processes": 0,
        "matching_app_processes": 0, "passenger_like_processes": 0,
        "matching_django_settings_env": 0,
        "matching_db_configuration_key_env": 0,
        "permission_denied": False,
        "passenger_db_authority_verified": False,
        "production_source_modified": False, "database_modified": False,
        "orders_created": 0, "payments_created": 0,
    }
    try:
        children = sorted(
            (p for p in proc_root.iterdir() if re.fullmatch(r"[0-9]+", p.name)),
            key=lambda p: int(p.name),
        )
        result["proc_readable"] = True
    except OSError:
        return result
    for process in children[:MAX_PROCESSES]:
        try:
            if process.stat().st_uid != owner_uid:
                continue
            result["scanned_own_processes"] += 1
            cmd = read_bounded(process / "cmdline", MAX_CMDLINE)
            env = read_bounded(process / "environ", MAX_ENVIRON)
            try:
                cwd = os.readlink(process / "cwd").encode("utf-8", "replace")
            except OSError:
                cwd = b""
            env_items = entries(env)
            dedicated = b"PASSENGER_APP_ROOT=" + APP_MARKER in env_items
            if not (APP_MARKER in cmd or APP_MARKER in cwd or dedicated):
                continue
            result["matching_app_processes"] += 1
            if b"passenger" in cmd.lower() or b"lswsgi" in cmd.lower():
                result["passenger_like_processes"] += 1
            keys = {item.partition(b"=")[0] for item in env_items if b"=" in item}
            if b"DJANGO_SETTINGS_MODULE" in keys:
                result["matching_django_settings_env"] += 1
            if keys.intersection({
                b"DATABASE_URL", b"DB_ENGINE", b"MYSQL_DATABASE",
                b"PGDATABASE", b"SQLITE_PATH",
            }):
                result["matching_db_configuration_key_env"] += 1
        except PermissionError:
            result["permission_denied"] = True
        except (OSError, ValueError):
            continue
    # Deliberately fail closed: process titles/env key presence cannot prove
    # the effective ORM connection in a live Passenger worker.
    return result


if __name__ == "__main__":
    print("S01_PASSENGER_RUNTIME_READONLY=" + json.dumps(probe(), sort_keys=True))
