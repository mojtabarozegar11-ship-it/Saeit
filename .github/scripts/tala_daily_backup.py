#!/usr/bin/env python3
"""Read-only, verified daily backups for Zomorod Tala ONLY.

Primary: ~/.tala-secure/tala.sqlite3
Archive: ~/.backups/zomorodmelal-tala/daily/<timestamp>-<run-id>/
Never modifies or deletes the live database or an existing backup.
"""
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import stat
import sys
import tempfile
import urllib.parse

TABLES = ("users", "entries", "audit_log")

def private_directory(path: Path) -> None:
    if path.is_symlink():
        raise RuntimeError("TALA_UNSAFE_SYMLINK_DIRECTORY")
    if path.exists() and not path.is_dir():
        raise RuntimeError("TALA_UNSAFE_BACKUP_DIRECTORY")
    if not path.exists():
        path.mkdir(mode=0o700)
    os.chmod(path, 0o700)

def regular_file(path: Path) -> None:
    if path.is_symlink() or not path.is_file():
        raise RuntimeError("TALA_PRIMARY_DATABASE_UNAVAILABLE")
    if not stat.S_ISREG(path.stat().st_mode):
        raise RuntimeError("TALA_PRIMARY_DATABASE_UNSAFE")

def readonly_db(path: Path):
    return sqlite3.connect("file:" + urllib.parse.quote(str(path)) + "?mode=ro", uri=True, timeout=20)

def verify(path: Path) -> dict:
    regular_file(path)
    with readonly_db(path) as db:
        if db.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise RuntimeError("TALA_SQLITE_INTEGRITY_FAILED")
        if db.execute("PRAGMA foreign_key_check").fetchone() is not None:
            raise RuntimeError("TALA_SQLITE_FOREIGN_KEY_FAILED")
        tables = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if not all(name in tables for name in TABLES):
            raise RuntimeError("TALA_SCHEMA_INCOMPLETE")
        return {name: int(db.execute('SELECT COUNT(*) FROM "' + name + '"').fetchone()[0]) for name in TABLES}

def copy_online(source: Path, destination: Path) -> None:
    regular_file(source)
    if destination.exists() or destination.is_symlink():
        raise RuntimeError("TALA_BACKUP_WOULD_OVERWRITE")
    with readonly_db(source) as db:
        with sqlite3.connect(str(destination), timeout=20) as dest:
            db.backup(dest, pages=128, sleep=0.1)
    os.chmod(destination, 0o600)

def verified_backup(home: Path, runid: str, now: dt.datetime | None = None) -> Path:
    if not re.fullmatch(r"[0-9]{1,20}", runid):
        raise RuntimeError("TALA_INVALID_BACKUP_RUN_ID")
    home = home.resolve(strict=True)
    root = home / ".tala-secure"
    if root.is_symlink() or not root.is_dir():
        raise RuntimeError("TALA_PRIVATE_DATABASE_DIRECTORY_INVALID")
    primary = root / "tala.sqlite3"
    regular_file(primary)

    backups = home / ".backups"
    site_backups = backups / "zomorodmelal-tala"
    daily = site_backups / "daily"
    # ~/.backups may contain other applications' archives. Do not chmod it.
    if backups.is_symlink() or (backups.exists() and not backups.is_dir()):
        raise RuntimeError("TALA_SHARED_BACKUP_PARENT_UNSAFE")
    if not backups.exists():
        backups.mkdir(mode=0o700)
    for folder in (site_backups, daily):
        private_directory(folder)

    instant = now or dt.datetime.now(dt.timezone.utc)
    instant = instant.astimezone(dt.timezone.utc)
    stamp = instant.strftime("%Y%m%dT%H%M%SZ")
    output = daily / (stamp + "-" + runid)
    if output.exists() or output.is_symlink():
        raise RuntimeError("TALA_BACKUP_ALREADY_EXISTS")
    output.mkdir(mode=0o700)
    snapshot = output / "tala.sqlite3"
    trial = output / ".restore-test.sqlite3"
    manifest = output / "manifest.json"
    try:
        copy_online(primary, snapshot)
        counts = verify(snapshot)
        copy_online(snapshot, trial)
        if verify(trial) != counts:
            raise RuntimeError("TALA_RESTORE_VERIFICATION_FAILED")
        trial.unlink()
        digest = hashlib.sha256()
        with snapshot.open("rb") as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b""):
                digest.update(chunk)
        record = {
            "scope": "tala",
            "timestamp_utc": instant.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "sha256": digest.hexdigest(),
            "size_bytes": snapshot.stat().st_size,
            "row_counts": counts,
            "sqlite_integrity": "ok",
            "restore_test": "passed",
        }
        with manifest.open("x", encoding="utf-8") as f:
            json.dump(record, f, indent=2, sort_keys=True)
            f.write("\n")
        os.chmod(manifest, 0o600)
        print("TALA_DAILY_BACKUP=verified")
        print("TALA_RESTORE_TEST=passed")
        print("TALA_BACKUP_SCOPE=only_tala")
        print("TALA_BACKUP_ARCHIVE=private_cpanel")
        return output
    finally:
        if trial.exists():
            trial.unlink()

def selftest():
    with tempfile.TemporaryDirectory(prefix="tala-daily-test-") as temp:
        home = Path(temp)
        store = home / ".tala-secure"
        store.mkdir(mode=0o700)
        primary = store / "tala.sqlite3"
        with sqlite3.connect(primary) as db:
            db.executescript("""
                CREATE TABLE users(id INTEGER PRIMARY KEY);
                CREATE TABLE entries(id INTEGER PRIMARY KEY, created_by INTEGER REFERENCES users(id));
                CREATE TABLE audit_log(id INTEGER PRIMARY KEY);
                INSERT INTO users VALUES (1);
                INSERT INTO entries VALUES (1,1);
            """)
        first = verified_backup(home, "123", dt.datetime(2026,10,17,8,0,tzinfo=dt.timezone.utc))
        old_hash = hashlib.sha256((first / "tala.sqlite3").read_bytes()).hexdigest()
        with sqlite3.connect(primary) as db:
            db.execute("INSERT INTO entries VALUES (2,1)")
        second = verified_backup(home, "124", dt.datetime(2026,10,18,8,0,tzinfo=dt.timezone.utc))
        assert verify(first / "tala.sqlite3")["entries"] == 1
        assert verify(second / "tala.sqlite3")["entries"] == 2
        assert hashlib.sha256((first / "tala.sqlite3").read_bytes()).hexdigest() == old_hash
        assert (first / "manifest.json").exists()
        assert not (first / ".restore-test.sqlite3").exists()
        try:
            verified_backup(home, "123", dt.datetime(2026,10,17,8,0,tzinfo=dt.timezone.utc))
        except RuntimeError as exc:
            assert str(exc) == "TALA_BACKUP_ALREADY_EXISTS"
        else:
            raise AssertionError("must refuse to overwrite existing backup")
        print("TALA_DAILY_BACKUP_SELFTEST=passed")

if __name__ == "__main__":
    if len(sys.argv) == 2 and sys.argv[1] == "selftest":
        selftest()
    elif len(sys.argv) == 3 and sys.argv[1] == "backup":
        verified_backup(Path.home(), sys.argv[2])
    else:
        raise SystemExit("Usage: tala_daily_backup.py selftest | backup RUN_ID")
