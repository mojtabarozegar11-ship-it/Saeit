#!/usr/bin/env python3
"""C14 owner-only SQLite lead-store inventory: no PII, no filesystem mutations.

The origin PHP source uses SQLite/PDO. This tool inspects bounded candidate
filenames but never outputs paths, filenames, SQL records or credentials.
Immutable SQLite connection avoids journal/WAL lock files and writes.
Counts are *snapshot indications*, not live transaction confirmation.
"""
from __future__ import annotations
import os
import pwd
from pathlib import Path
from urllib.parse import quote
import re
import sqlite3
import stat

MAX_SCAN = 48
MAX_BYTES = 100_000_000
TARGET_TABLES = ("inquiries", "requests", "service_requests", "leads", "messages", "questions")

def emit(name, value):
    assert re.fullmatch(r"[A-Z0-9_]+", name)
    print("ZM_C14_SQLITE_"+name+"="+str(value).lower())

def main():
    if pwd.getpwuid(os.getuid()).pw_name != "zomorod2":
        emit("STATE", "WRONG_ACCOUNT")
        return 12
    home = Path.home()
    dirs = (
        home / "public_html" / "ask-master",
        home / ".private" / "ask-master",
        home / ".private" / "company",
        home / ".private",
        home / "private" / "ask-master",
    )
    extensions = (".sqlite3", ".sqlite", ".db")
    seen = set()
    inspected = 0
    valid_sqlite = 0
    corrupt_or_unavailable = 0
    lead_table_candidates = 0
    snapshots_with_rows = 0
    incomplete = False
    for directory in dirs:
        if directory.is_symlink() or not directory.is_dir():
            continue
        try:
            mode = directory.stat()
            if not stat.S_ISDIR(mode.st_mode) or mode.st_uid != os.getuid():
                continue
            children = list(directory.iterdir())
        except OSError:
            incomplete = True
            continue
        if len(children) > 256:
            incomplete = True
            continue
        for f in children:
            if f.suffix.lower() not in extensions:
                continue
            if f in seen:
                continue
            seen.add(f)
            if len(seen) > MAX_SCAN:
                incomplete = True
                break
            if f.is_symlink() or not f.is_file():
                continue
            try:
                meta = f.stat()
                if not stat.S_ISREG(meta.st_mode) or meta.st_uid != os.getuid():
                    continue
                if not 512 <= meta.st_size <= MAX_BYTES:
                    continue
                with f.open("rb") as handle:
                    if handle.read(16) != b"SQLite format 3\x00":
                        continue
                inspected += 1
                # immutable snapshot: SQLite never opens WAL/SHM or makes a write.
                uri = "file:" + quote(str(f), safe="/") + "?mode=ro&immutable=1"
                db = sqlite3.connect(uri, uri=True, timeout=1)
                try:
                    db.execute("PRAGMA query_only=ON")
                    tables = {
                        x[0] for x in db.execute(
                            "SELECT name FROM sqlite_master WHERE type='table'"
                        ) if isinstance(x[0], str)
                    }
                    valid_sqlite += 1
                    known = [table for table in TARGET_TABLES if table in tables]
                    if known:
                        lead_table_candidates += 1
                    for table in known:
                        # table comes from an immutable, code-owned whitelist only.
                        n = db.execute('SELECT COUNT(*) FROM "'+table+'"').fetchone()[0]
                        if n > 0:
                            snapshots_with_rows += 1
                            break
                finally:
                    db.close()
            except (OSError, sqlite3.Error):
                corrupt_or_unavailable += 1
        if len(seen) > MAX_SCAN:
            break
    emit("STATE", "IMMUTABLE_METADATA_SCAN_COMPLETE")
    emit("DB_SNAPSHOTS_INSPECTED", inspected)
    emit("SQLITE_SCHEMA_READABLE", valid_sqlite)
    emit("CANDIDATE_LEAD_TABLE_DB_COUNT", lead_table_candidates)
    emit("CANDIDATE_LEAD_TABLE_DB_WITH_ROWS", snapshots_with_rows)
    emit("CANDIDATE_SQLITE_ERROR_COUNT", corrupt_or_unavailable)
    emit("SCAN_INCOMPLETE", str(incomplete))
    emit("POTENTIAL_WAL_UNREAD", "true")
    emit("PHP_DATABASE_PATH_MATCH_VERIFIED", "unknown")
    emit("LIVE_POST_PERSISTENCE_VERIFIED", "unknown")
    emit("CUSTOMER_PII_VALUES_ACCESSED", "false")
    emit("CUSTOMER_DATA_CHANGED", "false")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
