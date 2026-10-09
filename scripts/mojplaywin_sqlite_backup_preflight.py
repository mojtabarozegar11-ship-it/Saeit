#!/usr/bin/env python3
"""Offline, operator-invoked SQLite backup preflight for MojPlayWin.

Run from the deployed Django project with its existing virtualenv and .env loaded.
No migrations, writes to source database, network calls, or deployment.
"""
import argparse
import hashlib
import os
import pathlib
import sqlite3
import sys
import time

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", required=True, help="Private backup directory outside web root")
    args = parser.parse_args()
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    import django
    django.setup()
    from django.db import connections
    settings = connections["default"].settings_dict
    if settings["ENGINE"] != "django.db.backends.sqlite3":
        raise SystemExit("BLOCKED: database engine is not SQLite")
    raw_name = settings["NAME"]
    if not raw_name or str(raw_name) == ":memory:" or str(raw_name).startswith("file:"):
        raise SystemExit("BLOCKED: non-file/URI SQLite path requires manual verification")
    source = pathlib.Path(raw_name).expanduser().resolve(strict=True)
    if not source.is_file():
        raise SystemExit("BLOCKED: SQLite path is not a regular file")
    if not os.access(source, os.R_OK):
        raise SystemExit("BLOCKED: database file is not readable")
    output_dir = pathlib.Path(args.output_dir).expanduser().resolve()
    if output_dir == source.parent or output_dir == source or str(output_dir).startswith(str(source.parent / "public_html")):
        raise SystemExit("BLOCKED: choose a separate private backup directory")
    if not output_dir.exists() or not output_dir.is_dir():
        raise SystemExit("BLOCKED: output directory must already exist")
    if output_dir.stat().st_mode & 0o077:
        raise SystemExit("BLOCKED: output directory permissions must be 0700")
    if source.parent == output_dir:
        raise SystemExit("BLOCKED: backup directory cannot be database directory")
    dest = output_dir / ("mojplaywin-db-" + time.strftime("%Y%m%d-%H%M%S") + ".sqlite3")
    if dest.exists():
        raise SystemExit("BLOCKED: backup destination already exists")
    src_uri = source.as_uri() + "?mode=ro"
    print("SQLITE_SOURCE_PRESENT=yes")
    print("SQLITE_SOURCE_SIZE_BYTES=" + str(source.stat().st_size))
    print("BACKUP_DIRECTORY_PRIVATE=yes")
    try:
        with sqlite3.connect(src_uri, uri=True, timeout=30) as src:
            with sqlite3.connect(str(dest), timeout=30) as target:
                src.backup(target, pages=256, sleep=0.1)
        os.chmod(dest, 0o600)
        with sqlite3.connect(dest.as_uri() + "?mode=ro", uri=True) as verify:
            result = verify.execute("PRAGMA integrity_check").fetchone()[0]
        if result != "ok":
            raise RuntimeError("backup integrity check failed")
        sha = hashlib.sha256()
        with dest.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                sha.update(chunk)
        print("BACKUP_INTEGRITY=ok")
        print("BACKUP_SIZE_BYTES=" + str(dest.stat().st_size))
        print("BACKUP_SHA256=" + sha.hexdigest())
        print("BACKUP_FILE=" + str(dest))
    except Exception:
        if dest.exists():
            dest.unlink()
        raise

if __name__ == "__main__":
    main()
