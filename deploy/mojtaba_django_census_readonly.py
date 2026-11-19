"""Minimal registry/task census. No app startup, task execution or raw payload output."""
import argparse
from collections import Counter
from contextlib import closing
import hashlib
import json
import os
from pathlib import Path
import pwd
import sqlite3
import sys

KNOWN = frozenset(("mojtaba-bot-ai", "economic-master-agent", "moj_1ro_1",
    "core_research", "newsletter-specialist", "newsletter-company-news",
    "newsletter-world-watch", "newsletter-unit-reports", "company-activity-intelligence",
    "content-director", "knowledge-content-director", "content-research",
    "factory-market-research-agent", "factory-opportunity-validation-agent"))
TERMINAL = frozenset(("completed", "failed", "cancelled"))
STATUS = TERMINAL | {"queued", "running", "blocked"}
ROLES = {"vps": ("githubops", "factory-runtime/django-app"),
         "cpanel": ("zomorod2", "Saeit")}
SCHEMA = "mojtaba.bot.ai.django-census.v1"
QUERIES = (
    "SELECT id, code, active FROM core_agent ORDER BY id LIMIT 10001",
    "SELECT agent_id, status, COUNT(*) FROM core_agenttask GROUP BY agent_id, status LIMIT 100001",
)


def collect(cursor):
    cursor.execute(QUERIES[0])
    agents = cursor.fetchall()
    if len(agents) > 10000:
        raise ValueError("registry_bound")
    rows = {}
    for pk, code, active in agents:
        if type(active) not in (bool, int) or active not in (0, 1):
            raise ValueError("invalid_active")
        label = code if code in KNOWN else "unknown:" + hashlib.sha256(str(code).encode()).hexdigest()[:16]
        rows[pk] = {"code": label, "enabled_registry_record": bool(active), "tasks": {}}
    cursor.execute(QUERIES[1])
    groups = cursor.fetchall()
    if len(groups) > 100000:
        raise ValueError("task_group_bound")
    orphans = 0
    for pk, status, count in groups:
        if type(count) is not int or count < 0:
            raise ValueError("invalid_count")
        if pk not in rows:
            orphans += count
            continue
        counts = rows[pk]["tasks"]
        name = status if status in STATUS else "unknown_nonterminal"
        counts[name] = counts.get(name, 0) + count
    for row in rows.values():
        row["nonterminal_tasks"] = sum(n for k, n in row["tasks"].items() if k not in TERMINAL)
    values = list(rows.values())
    return {"registry_records": len(values),
            "enabled_registry_records": sum(r["enabled_registry_record"] for r in values),
            "nonterminal_tasks": sum(r["nonterminal_tasks"] for r in values),
            "orphan_task_records": orphans, "agents": values}


def sqlite_census(name, app):
    path = Path(name)
    if not path.is_absolute():
        raise ValueError("relative_db_name")
    if (not path.is_file() or path.is_symlink()
            or not path.resolve().is_relative_to(app.resolve())
            or any(Path(str(path) + suffix).exists() for suffix in ("-wal", "-journal", "-shm"))):
        raise ValueError("sqlite_snapshot_unavailable")
    with closing(sqlite3.connect(path.resolve().as_uri() + "?mode=ro&immutable=1", uri=True, timeout=5)) as db:
        db.execute("PRAGMA query_only=ON")
        result = collect(db.cursor())
    # Do not certify an immutable snapshot if a writer's sidecar appeared.
    if any(Path(str(path) + suffix).exists() for suffix in ("-wal", "-journal", "-shm")):
        raise ValueError("sqlite_snapshot_changed")
    return result


def server_census(connection):
    if connection.vendor not in ("mysql", "postgresql"):
        raise ValueError("unsupported_backend")
    try:
        connection.ensure_connection()
        if not connection.get_autocommit():
            raise ValueError("unexpected_transaction")
        with connection.cursor() as cursor:
            if connection.vendor == "mysql":
                cursor.execute("SET TRANSACTION READ ONLY")
                cursor.execute("START TRANSACTION")
            else:
                cursor.execute("BEGIN READ ONLY")
            try:
                return collect(cursor)
            finally:
                cursor.execute("ROLLBACK")
    finally:
        connection.close()


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--role", choices=ROLES, required=True)
    role = p.parse_args().role
    user, relative = ROLES[role]
    base = {"schema": SCHEMA, "host": role, "state": "unknown",
            "verified_live_agents": None, "retirement_authorized": False,
            "registry_records": None, "enabled_registry_records": None,
            "nonterminal_tasks": None, "agents": []}
    try:
        if pwd.getpwuid(os.geteuid()).pw_name != user:
            raise ValueError("wrong_user")
        app = Path(pwd.getpwuid(os.geteuid()).pw_dir) / relative
        if Path.cwd().resolve() != app.resolve() or not (app / "manage.py").is_file():
            raise ValueError("wrong_app")
        sys.path.insert(0, str(app))
        os.environ["DJANGO_SETTINGS_MODULE"] = "config.settings"
        from django.db import connections
        connection = connections["default"]
        if connection.vendor == "sqlite":
            data = sqlite_census(connection.settings_dict["NAME"], app)
        else:
            data = server_census(connection)
        base.update(data, state="registry_snapshot_only",
                    backend=connection.vendor, read_only_database_transaction=True)
    except Exception:
        # Never output exception text, SQL credentials, connection URLs or payloads.
        base["state"] = "database_or_schema_unavailable"
    print("MOJTABA_DJANGO_CENSUS=" + json.dumps(base, sort_keys=True))

if __name__ == "__main__":
    main()
