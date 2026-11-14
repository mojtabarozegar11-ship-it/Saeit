#!/usr/bin/env python3
"""C15 read-only PHP→SQLite lineage evidence without reading private customer rows.

Runs on the verified cPanel account. Only outputs bounded boolean and count
signals. Does not print PHP, SQL, paths, table/column names, client data,
credentials, or archive files. Does not execute PHP or submit any request.
SQLite immutable snapshots deliberately cannot see pending WAL writes.
"""
from __future__ import annotations

from pathlib import Path
from urllib.parse import quote
import os
import pwd
import re
import sqlite3
import stat

ROOT = Path.home() / "public_html" / "ask-master"
ALLOWED_BASES = (
    ROOT,
    Path.home() / ".private",
    Path.home() / ".private" / "ask-master",
    Path.home() / ".private" / "company",
    Path.home() / "private" / "ask-master",
)
MAX_PHP_FILES = 12
MAX_SQLITE_FILES = 48
MAX_FOLDER_ITEMS = 256
MAX_FILE_SIZE = 90 * 1024 * 1024
LEAD_CONTACT = {"email", "email_address", "phone", "mobile", "contact"}
LEAD_MESSAGE = {"message", "body", "question", "subject", "details", "content"}
SQL_TABLE_PATTERN = re.compile(
    rb"\b(?:INSERT\s+INTO|UPDATE|FROM|JOIN)\s+[\"\x60]?([A-Za-z_][A-Za-z0-9_]{0,79})[\"\x60]?",
    re.I,
)

def out(key: str, value: object):
    assert re.fullmatch("[A-Z0-9_]+", key)
    print("ZM_C15_LEAD_" + key + "=" + str(value).lower())

def safe_directory(path: Path) -> bool:
    try:
        stat_ = path.stat()
        return (
            not path.is_symlink() and stat.S_ISDIR(stat_.st_mode)
            and stat_.st_uid == os.getuid()
        )
    except OSError:
        return False

def source_tables():
    if not safe_directory(ROOT):
        return None
    files = sorted(ROOT.glob("*.php"))
    if len(files) > MAX_PHP_FILES:
        return None
    out("PHP_SOURCE_FILES", len(files))
    sql_identifiers = set()
    has_sqlite_dsn = False
    has_post = False
    for f in files:
        if f.is_symlink() or not f.is_file():
            return None
        meta = f.stat()
        if meta.st_uid != os.getuid() or meta.st_size > 400_000:
            return None
        content = f.read_bytes()
        sql_identifiers.update(m.group(1).decode("ascii").casefold()
                               for m in SQL_TABLE_PATTERN.finditer(content))
        has_sqlite_dsn |= b"sqlite:" in content.lower()
        has_post |= b"$_POST" in content
    out("PHP_SQL_TABLE_IDENTIFIERS_FOUND", len(sql_identifiers))
    out("PHP_SQLITE_DSN_INDICATOR", has_sqlite_dsn)
    out("PHP_POST_INDICATOR", has_post)
    return sql_identifiers

def main() -> int:
    if pwd.getpwuid(os.getuid()).pw_name != "zomorod2":
        out("STATE", "UNEXPECTED_ACCOUNT")
        return 11
    referenced = source_tables()
    if referenced is None:
        out("STATE", "UNSAFE_OR_UNREADABLE_PHP")
        return 12
    dbs = 0
    shared_name_db = 0
    lead_schema_db = 0
    lead_schema_with_snapshot_row = 0
    wal_present_db = 0
    private_db = 0
    public_db = 0
    errors = 0
    too_many = False
    for base in ALLOWED_BASES:
        if not safe_directory(base):
            continue
        try:
            entries = list(base.iterdir())
        except OSError:
            errors += 1
            continue
        if len(entries) > MAX_FOLDER_ITEMS:
            too_many = True
            break
        for f in entries:
            if f.suffix.lower() not in (".db", ".sqlite", ".sqlite3"):
                continue
            if dbs >= MAX_SQLITE_FILES:
                too_many = True
                break
            if f.is_symlink() or not f.is_file():
                continue
            meta = f.stat()
            if not stat.S_ISREG(meta.st_mode) or meta.st_uid != os.getuid():
                continue
            if not 512 <= meta.st_size <= MAX_FILE_SIZE:
                continue
            with f.open("rb") as handle:
                if handle.read(16) != b"SQLite format 3\x00":
                    continue
            dbs += 1
            if f.parent == ROOT:
                public_db += 1
            else:
                private_db += 1
            wal_present_db += int(f.with_name(f.name + "-wal").exists())
            uri = "file:" + quote(str(f), safe="/") + "?mode=ro&immutable=1"
            try:
                with sqlite3.connect(uri, uri=True, timeout=1) as con:
                    con.execute("PRAGMA query_only=ON")
                    tables = [
                        t[0].casefold() for t in con.execute(
                            "SELECT name FROM sqlite_master WHERE type='table'"
                        )
                        if isinstance(t[0], str)
                        and re.fullmatch("[A-Za-z_][A-Za-z0-9_]{0,79}", t[0])
                    ]
                    shared = set(tables) & referenced
                    shared_name_db += int(bool(shared))
                    lead_tables = []
                    for t in tables:
                        columns = {
                            c[1].casefold() for c in con.execute(
                                'PRAGMA table_info("'+t+'")'
                            ) if isinstance(c[1], str)
                        }
                        if columns & LEAD_CONTACT and columns & LEAD_MESSAGE:
                            lead_tables.append(t)
                    if lead_tables:
                        lead_schema_db += 1
                    for t in lead_tables:
                        present = con.execute(
                            'SELECT EXISTS(SELECT 1 FROM "'+t+'" LIMIT 1)'
                        ).fetchone()[0]
                        if present:
                            lead_schema_with_snapshot_row += 1
                            break
            except sqlite3.Error:
                errors += 1
        if too_many:
            break
    out("STATE", "READ_ONLY_IMMUTABLE_INVENTORY_COMPLETE")
    out("SQLITE_FILES_INSPECTED", dbs)
    out("SQLITE_DB_IN_PUBLIC_ASK_FOLDER", public_db)
    out("SQLITE_DB_OUTSIDE_PHP_PUBLIC_FOLDER", private_db)
    out("SQLITE_DB_WITH_WAL_FILES", wal_present_db)
    out("SQLITE_DB_WITH_PHP_QUERY_TABLE_MATCH", shared_name_db)
    out("SQLITE_DB_WITH_LEAD_LIKE_SCHEMA", lead_schema_db)
    out("LEAD_LIKE_DB_WITH_SNAPSHOT_ROW", lead_schema_with_snapshot_row)
    out("SCHEMA_READ_ERRORS", errors)
    out("SEARCH_LIMIT_REACHED", too_many)
    out("PHP_RUNTIME_DB_PATH_IDENTIFIED", "unknown")
    out("WAL_CONTENT_ACCOUNTED_FOR", "false")
    out("LIVE_POST_TO_DB_PROVEN", "false")
    out("CUSTOMER_PII_READ", "false")
    out("PRODUCTION_DATA_WRITES", "0")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
