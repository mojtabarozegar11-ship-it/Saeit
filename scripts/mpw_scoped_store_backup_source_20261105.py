#!/usr/bin/env python3
"""Low-priority, consistent, read-only scoped MariaDB backup from live cPanel.

`plan` emits metadata only. `stream` emits GZIP bytes only; NEVER attach its
stdout to logs or artifacts. No customer record is inspected in Python.
This scope is NOT a full database/tenant backup.
"""
from __future__ import annotations

import gzip
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path("/home/zomorod2/Saeit-staging")
MARKER = b"\n-- MPW-STORE-SCOPED-20261105-COMPLETE --\n"
MAX_SQL_BYTES = 4 * 1024**3
MAX_ALLOCATED_BYTES = 2_300_000_000
SCOPED_TABLES = frozenset({
    "auth_user", "core_factoryrun", "core_guestorderemail",
    "core_guestrecoveryrate", "core_guestrecoverytoken",
    "core_knowledgearticle", "core_ledgerentry", "core_order",
    "core_orderitem", "core_paymentintent", "core_paymentwebhookevent",
    "core_product", "core_report", "core_researchproject",
    "mpw_commerce_commercefulfillment", "django_migrations",
})
SEEDS = frozenset({
    "core_order", "core_orderitem", "core_paymentintent",
    "core_paymentwebhookevent", "core_ledgerentry", "core_guestorderemail",
    "core_guestrecoverytoken", "core_guestrecoveryrate",
    "mpw_commerce_commercefulfillment",
})


def fk_parent_closure(seeds, relations):
    parents = {}
    for child, parent in relations:
        parents.setdefault(child, set()).add(parent)
    all_needed = set(seeds)
    todo = list(seeds)
    while todo:
        for parent in parents.get(todo.pop(), ()):
            if parent not in all_needed:
                all_needed.add(parent)
                todo.append(parent)
    return frozenset(all_needed)


def prepare():
    if ROOT.is_symlink() or not ROOT.is_dir():
        raise RuntimeError("UNTRUSTED_RUNTIME_ROOT")
    os.chdir(ROOT)
    sys.path.insert(0, str(ROOT))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    import django
    django.setup()
    from django.db import connection

    if connection.vendor != "mysql":
        raise RuntimeError("NOT_MARIADB")
    with connection.cursor() as c:
        c.execute("""
            SELECT TABLE_NAME, COALESCE(DATA_LENGTH,0)+COALESCE(INDEX_LENGTH,0), ENGINE
            FROM information_schema.TABLES
            WHERE TABLE_SCHEMA=DATABASE() AND TABLE_TYPE='BASE TABLE'
        """)
        entries = c.fetchall()
        c.execute("""
            SELECT TABLE_NAME, REFERENCED_TABLE_NAME
            FROM information_schema.KEY_COLUMN_USAGE
            WHERE TABLE_SCHEMA=DATABASE() AND REFERENCED_TABLE_NAME IS NOT NULL
        """)
        relations = [(str(a), str(b)) for a, b in c.fetchall()]
        c.execute("SELECT DATABASE()")
        actual_db = c.fetchone()[0]

    tables = {}
    for name, size, engine in entries:
        name = str(name)
        if not re.fullmatch(r"[a-zA-Z0-9_]{1,100}", name):
            raise RuntimeError("UNSAFE_TABLE_NAME")
        tables[name] = (int(size), engine)
    if not (SEEDS <= tables.keys() and SCOPED_TABLES <= tables.keys()):
        raise RuntimeError("SCOPED_TABLE_MISSING")
    closure = fk_parent_closure(SEEDS, relations)
    if closure | {"django_migrations"} != SCOPED_TABLES:
        raise RuntimeError("SCOPED_FK_CLOSURE_CHANGED")
    if any(a not in tables or b not in tables for a, b in relations):
        raise RuntimeError("EXTERNAL_FK_REFERENCE")
    allocated = sum(tables[name][0] for name in SCOPED_TABLES)
    if allocated > MAX_ALLOCATED_BYTES:
        raise RuntimeError("SCOPED_VOLUME_GATE")
    if any(tables[name][1] != "InnoDB" for name in SCOPED_TABLES):
        raise RuntimeError("SCOPED_NONTRANSACTIONAL_TABLE")
    settings = connection.settings_dict
    if actual_db != settings["NAME"] or not actual_db:
        raise RuntimeError("DATABASE_IDENTITY_MISMATCH")
    return settings, {
        "table_count": len(SCOPED_TABLES),
        "allocated_bytes_estimate": allocated,
        "fk_parent_closure_verified": True,
        "all_tables_transactional": True,
        "full_database_backup": False,
        "customer_rows_logged": False,
        "production_writes": False,
    }


def stream(settings):
    if not shutil.which("mariadb-dump"):
        raise RuntimeError("DUMP_CLIENT_MISSING")
    args = [
        "nice", "-n", "15", "mariadb-dump", "--no-defaults",
        "--single-transaction", "--quick", "--skip-lock-tables",
        "--skip-add-drop-table", "--hex-blob", "--no-tablespaces",
        "--default-character-set=utf8mb4", "--host=" + (settings["HOST"] or "localhost"),
        "--user=" + settings["USER"],
    ]
    if settings.get("PORT"):
        args.append("--port=" + str(settings["PORT"]))
    args += [settings["NAME"], *sorted(SCOPED_TABLES)]
    env = dict(os.environ, MYSQL_PWD=settings["PASSWORD"])
    process = subprocess.Popen(args, stdout=subprocess.PIPE,
                               stderr=subprocess.DEVNULL, env=env)
    size = 0
    try:
        with gzip.GzipFile(fileobj=sys.stdout.buffer, mode="wb",
                           compresslevel=1, mtime=0) as encoded:
            assert process.stdout is not None
            while block := process.stdout.read(65536):
                size += len(block)
                if size > MAX_SQL_BYTES:
                    raise RuntimeError("SCOPED_SQL_STREAM_LIMIT")
                encoded.write(block)
            if process.wait(timeout=40):
                raise RuntimeError("SCOPED_DUMP_FAILED")
            if size < 1024:
                raise RuntimeError("SCOPED_SQL_UNEXPECTEDLY_EMPTY")
            encoded.write(MARKER)
    finally:
        if process.poll() is None:
            process.kill()
            process.wait()
    print("MPW_SCOPED_SOURCE_STREAM_COMPLETE", file=sys.stderr, flush=True)


if __name__ == "__main__":
    try:
        if len(sys.argv) < 2 or sys.argv[-1] not in ("plan", "stream"):
            raise RuntimeError("UNKNOWN_OPERATION")
        settings, plan = prepare()
        if sys.argv[-1] == "plan":
            print("MPW_SCOPED_SOURCE_PREFLIGHT=" + json.dumps(plan, sort_keys=True))
        else:
            stream(settings)
    except Exception as error:
        allowed = {
            "UNTRUSTED_RUNTIME_ROOT", "NOT_MARIADB", "UNSAFE_TABLE_NAME",
            "SCOPED_TABLE_MISSING", "SCOPED_FK_CLOSURE_CHANGED",
            "EXTERNAL_FK_REFERENCE", "SCOPED_VOLUME_GATE",
            "SCOPED_NONTRANSACTIONAL_TABLE", "DATABASE_IDENTITY_MISMATCH",
            "DUMP_CLIENT_MISSING", "SCOPED_SQL_STREAM_LIMIT",
            "SCOPED_DUMP_FAILED", "SCOPED_SQL_UNEXPECTEDLY_EMPTY",
            "UNKNOWN_OPERATION",
        }
        category = str(error) if str(error) in allowed else "SCOPED_SOURCE_UNCLASSIFIED"
        print("MPW_SCOPED_SOURCE_ABORT=" + category, file=sys.stderr)
        raise SystemExit(1)
