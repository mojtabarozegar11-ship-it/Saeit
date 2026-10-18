#!/usr/bin/env python3
"""Bounded NON-ROW MySQL schema-dump preflight on live cPanel connection.

Runs 'mariadb-dump --no-data' with timeout (never backs up row data, changes
production DB, logs schema/source URL or captures credentials). The schema
stream is drained in memory, never persisted. A passing check does NOT
prove the full data dump can run under load or form a complete backup.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import time
from pathlib import Path
from urllib.parse import urlsplit, unquote

HOME = Path("/home/zomorod2")
APP = HOME / "Saeit-staging"
DOCROOT = HOME / "mojplaywin.com"
MAX_BYTES = 32 * 1024 * 1024
MAX_SECONDS = 60


def source():
    found = []
    for p in (APP / ".env", APP / ".env.production", APP / ".env.local", DOCROOT / ".env"):
        try:
            if p.is_symlink() or not p.is_file() or p.stat().st_size > 65536:
                continue
            for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
                m = re.match(r"^\s*(?:export\s+)?DATABASE_URL\s*=\s*(.*?)\s*$", line)
                if m:
                    v = urlsplit(m.group(1).strip().strip('"').strip("'"))
                    if v.scheme.lower() not in ("mysql", "mariadb", "mysql2"):
                        return None
                    found.append(v)
        except (OSError, ValueError):
            return None
    return found[0] if len(found) == 1 else None


def check():
    result = {
        "classification": "READ_ONLY_SCHEMA_DUMP_SOURCE_PREFLIGHT",
        "single_mysql_url": False,
        "schema_dumper_present": shutil.which("mariadb-dump") is not None and shutil.which("timeout") is not None,
        "table_count": None,
        "estimated_data_bytes": None,
        "estimated_index_bytes": None,
        "non_innodb_tables": None,
        "schema_dump_exit_ok": False,
        "bytes_drained_only_in_memory": 0,
        "elapsed_seconds": None,
        "table_rows_read": False,
        "schema_output_persisted": False,
        "database_or_passenger_modified": False,
        "source_full_dump_verified": False,
        "release_permitted": False,
    }
    parsed = source()
    result["single_mysql_url"] = parsed is not None
    if not parsed or not result["schema_dumper_present"]:
        return result
    db = unquote(parsed.path.lstrip("/"))
    user = unquote(parsed.username or "")
    password = unquote(parsed.password or "")
    if not db or not user or not password:
        return result
    if shutil.which("mariadb"):
        query_args = [
            "mariadb", "--no-defaults", "--batch", "--skip-column-names",
            "--host=" + (parsed.hostname or "localhost"), "--user=" + user,
            "--database=" + db, "--connect-timeout=8",
            "--execute=SELECT COUNT(*), COALESCE(SUM(DATA_LENGTH),0), COALESCE(SUM(INDEX_LENGTH),0), COALESCE(SUM(ENGINE <> 'InnoDB'),0) FROM information_schema.TABLES WHERE TABLE_SCHEMA=DATABASE() AND TABLE_TYPE='BASE TABLE'",
        ]
        if parsed.port:
            query_args.append("--port=" + str(parsed.port))
        try:
            p = subprocess.run(
                ["timeout", "15s", *query_args], capture_output=True,
                env=dict(os.environ, MYSQL_PWD=password), timeout=18, check=False,
            )
            if p.returncode == 0 and len(p.stdout) < 200:
                vals = [int(v) for v in p.stdout.decode("ascii").split()]
                if len(vals) == 4 and all(v >= 0 for v in vals):
                    result.update(dict(zip(
                        ("table_count", "estimated_data_bytes", "estimated_index_bytes", "non_innodb_tables"),
                        vals,
                    )))
        except (OSError, ValueError, UnicodeError, subprocess.TimeoutExpired):
            pass
    args = ["mariadb-dump", "--no-defaults", "--no-data",
            "--single-transaction", "--quick", "--skip-lock-tables",
            "--default-character-set=utf8mb4", "--hex-blob",
            "--host=" + (parsed.hostname or "localhost"), "--user=" + user]
    if parsed.port:
        args.append("--port=" + str(parsed.port))
    args.extend(["--databases", db])
    t0 = time.monotonic()
    proc = None
    total = 0
    try:
        proc = subprocess.Popen(
            ["timeout", "55s", *args], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            env=dict(os.environ, MYSQL_PWD=password), bufsize=0,
        )
        while time.monotonic() - t0 < MAX_SECONDS:
            b = proc.stdout.read(65536)
            if not b:
                break
            total += len(b)
            if total > MAX_BYTES:
                break
        if total <= MAX_BYTES and time.monotonic() - t0 < MAX_SECONDS:
            result["schema_dump_exit_ok"] = proc.wait(timeout=3) == 0
        result["bytes_drained_only_in_memory"] = total
        result["elapsed_seconds"] = round(time.monotonic() - t0, 2)
    except (OSError, ValueError, subprocess.TimeoutExpired):
        result["elapsed_seconds"] = round(time.monotonic() - t0, 2)
    finally:
        if proc is not None:
            if proc.poll() is None:
                proc.kill()
            proc.wait()
    return result


if __name__ == "__main__":
    print(json.dumps(check(), sort_keys=True))
