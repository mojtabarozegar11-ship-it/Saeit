#!/usr/bin/env python3
"""Tala-only SQLite migration and verified snapshots; never reads other site data."""
import hashlib
import os
from pathlib import Path
import re
import sqlite3
import sys
import tempfile
import urllib.parse

def assert_regular(path: Path) -> None:
    if path.is_symlink() or (path.exists() and not path.is_file()):
        raise RuntimeError("TALA_UNSAFE_DATABASE_PATH")

def verify(db_file: Path):
    assert_regular(db_file)
    uri = "file:" + urllib.parse.quote(str(db_file)) + "?mode=ro"
    with sqlite3.connect(uri, uri=True, timeout=15) as db:
        if db.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise RuntimeError("TALA_SQLITE_INTEGRITY_FAILED")
        names = {v[0] for v in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        return {name: db.execute('SELECT COUNT(*) FROM "' + name + '"').fetchone()[0]
                for name in ("users", "entries", "audit_log") if name in names}

def snapshot(source: Path, destination: Path):
    assert_regular(source)
    assert_regular(destination)
    destination.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(destination.parent, 0o700)
    fd, temporary = tempfile.mkstemp(prefix=".tala-snapshot-", dir=destination.parent)
    os.close(fd)
    temp = Path(temporary)
    try:
        os.chmod(temp, 0o600)
        uri = "file:" + urllib.parse.quote(str(source)) + "?mode=ro"
        with sqlite3.connect(uri, uri=True, timeout=20) as src:
            with sqlite3.connect(str(temp), timeout=20) as dest:
                src.backup(dest, pages=128, sleep=0.1)
        expected = verify(source)
        actual = verify(temp)
        if expected != actual:
            raise RuntimeError("TALA_SNAPSHOT_TABLE_COUNTS_MISMATCH")
        os.replace(temp, destination)
        os.chmod(destination, 0o600)
        return actual
    finally:
        if temp.exists():
            temp.unlink()

def locations(home: Path, sha: str):
    if not re.fullmatch("[0-9a-f]{40}", sha):
        raise RuntimeError("TALA_INVALID_RELEASE_SHA")
    home = home.resolve(strict=True)
    legacy = home / "public_html/tala/api/.private/tala.sqlite3"
    store = home / ".tala-secure"
    external = store / "tala.sqlite3"
    backup = home / ".backups/zomorodmelal-tala" / sha
    if store.is_symlink() or backup.is_symlink():
        raise RuntimeError("TALA_UNSAFE_DIRECTORY")
    if not backup.is_dir():
        raise RuntimeError("TALA_RELEASE_BACKUP_DIRECTORY_MISSING")
    return legacy, store, external, backup

def prepare(home: Path, sha: str):
    legacy, store, external, backup = locations(home, sha)
    store.mkdir(mode=0o700, exist_ok=True)
    os.chmod(store, 0o700)
    assert_regular(legacy)
    assert_regular(external)
    if legacy.exists() and external.exists():
        raise RuntimeError("TALA_DUAL_DATABASE_AUTHORITY: manual reconciliation required")
    if legacy.exists():
        counts = verify(legacy)
        migrated = snapshot(legacy, external)
        if migrated != counts:
            raise RuntimeError("TALA_MIGRATION_MISMATCH")
        print("TALA_DATABASE=migrated_outside_webroot")
    elif external.exists():
        verify(external)
        print("TALA_DATABASE=existing_outside_webroot")
    else:
        print("TALA_DATABASE=empty_first_boot")
        return
    primary = backup / "tala-consistent.sqlite3"
    if primary.exists():
        raise RuntimeError("TALA_SNAPSHOT_ALREADY_EXISTS")
    counts = snapshot(external, primary)
    temporary = backup / ".tala-restore-test.sqlite3"
    try:
        restored = snapshot(primary, temporary)
        if restored != counts:
            raise RuntimeError("TALA_RESTORE_TEST_MISMATCH")
        print("TALA_BACKUP=sqlite_online_snapshot_verified")
        print("TALA_RESTORE_TEST=passed")
        print("TALA_TABLE_COUNT_TYPES=" + str(len(counts)))
    finally:
        if temporary.exists():
            temporary.unlink()

def restore_legacy(home: Path, sha: str):
    _legacy, _store, external, backup = locations(home, sha)
    prior = backup / "prior"
    old_php = prior / "api/admin.php"
    if not prior.is_dir():
        return
    if not old_php.is_file():
        raise RuntimeError("TALA_PRIOR_API_MISSING")
    if "const TALA_DB_FILE = __DIR__ . '/.private/tala.sqlite3';" not in old_php.read_text(encoding="utf-8"):
        print("TALA_ROLLBACK_DB=external_kept")
        return
    if not external.exists():
        print("TALA_ROLLBACK_DB=no_new_external_db")
        return
    target = prior / "api/.private/tala.sqlite3"
    if target.parent.is_symlink():
        raise RuntimeError("TALA_UNSAFE_PRIOR_DIRECTORY")
    target.parent.mkdir(mode=0o700, exist_ok=True)
    snapshot(external, target)
    print("TALA_ROLLBACK_DB=synced_to_legacy")

def selftest():
    with tempfile.TemporaryDirectory(prefix="tala-storage-test-") as td:
        home = Path(td)
        (home / "public_html/tala/api/.private").mkdir(parents=True)
        legacy = home / "public_html/tala/api/.private/tala.sqlite3"
        with sqlite3.connect(legacy) as db:
            db.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, username TEXT)")
            db.execute("CREATE TABLE entries (id INTEGER PRIMARY KEY, amount_rial INTEGER)")
            db.execute("CREATE TABLE audit_log (id INTEGER PRIMARY KEY, event TEXT)")
            db.execute("INSERT INTO users VALUES (1, 'test')")
            db.execute("INSERT INTO entries VALUES (1, 123)")
            db.commit()
        sha = "a" * 40
        backup = home / ".backups/zomorodmelal-tala" / sha
        backup.mkdir(parents=True)
        prepare(home, sha)
        ext = home / ".tala-secure/tala.sqlite3"
        assert verify(ext) == {"users": 1, "entries": 1, "audit_log": 0}
        assert verify(backup / "tala-consistent.sqlite3") == verify(ext)
        assert legacy.exists()  # Migration never erases the original.
        prior = backup / "prior/api/.private"
        prior.mkdir(parents=True)
        (backup / "prior/api/admin.php").write_text(
            "const TALA_DB_FILE = __DIR__ . '/.private/tala.sqlite3';",
            encoding="utf-8")
        restore_legacy(home, sha)
        assert verify(prior / "tala.sqlite3") == verify(ext)
        print("TALA_STORAGE_SELFTEST=passed")

if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else ""
    if mode == "selftest" and len(sys.argv) == 2:
        selftest()
    elif mode in ("prepare", "restore") and len(sys.argv) == 3:
        if mode == "prepare":
            prepare(Path.home(), sys.argv[2])
        else:
            restore_legacy(Path.home(), sys.argv[2])
    else:
        raise SystemExit("Usage: tala_storage.py selftest | prepare SHA | restore SHA")
