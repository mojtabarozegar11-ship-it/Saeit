#!/usr/bin/env python3
"""READ ONLY: stream only immutable owner-private ZERO-CUSTOMER SQLite first snapshot.

Never open current production MariaDB or live application. No cPanel writes.
The destination stream must be consumed by owner-side trusted encryption.
"""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import pwd
import sqlite3
import stat
import sys

HOME = Path("/home/zomorod2")
DIR = HOME / ".mojprop-native-v141-isolated-20261118"
SRC = DIR / "merchant-initial-snapshot.sqlite3"
LIMIT = 8 * 1024 * 1024
TABLES = {
    "prop_firm_propv141nativeorder", "prop_firm_propv141nativereceipt",
    "prop_firm_propglobaltrxsettlement", "prop_firm_propv141simstate",
    "prop_firm_propv141virtualbook",
}

def die(msg: str) -> None:
    print("MOJPROP_READONLY_SOURCE_HOLD=" + msg, file=sys.stderr)
    raise SystemExit(2)

def main() -> None:
    uid = os.geteuid()
    if uid == 0 or pwd.getpwuid(uid).pw_name != "zomorod2":
        die("WRONG_OWNER")
    for path in (HOME, DIR):
        st = path.lstat()
        if not stat.S_ISDIR(st.st_mode) or st.st_uid != uid or st.st_mode & 0o022:
            die("UNSAFE_PARENT")
    meta = SRC.lstat()
    if (not stat.S_ISREG(meta.st_mode) or meta.st_uid != uid
            or meta.st_nlink != 1 or meta.st_mode & 0o077
            or not 4096 <= meta.st_size <= LIMIT):
        die("SOURCE_NOT_AN_IMMUTABLE_PRIVATE_SQLITE")
    for suffix in ("-wal", "-shm", "-journal"):
        companion = DIR / (SRC.name + suffix)
        if companion.exists() or companion.is_symlink():
            die("SQLITE_SIDECAR_PRESENT")
    fd = os.open(SRC, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    try:
        a = os.fstat(fd)
        identity = lambda s: (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns)
        if identity(a) != identity(meta):
            die("SOURCE_RACE")
        chunks, count = [], 0
        while True:
            data = os.read(fd, 1024 * 1024)
            if not data:
                break
            count += len(data)
            if count > LIMIT:
                die("UNEXPECTED_GROWTH")
            chunks.append(data)
        b = os.fstat(fd)
        if identity(a) != identity(b):
            die("SOURCE_CHANGED_DURING_READ")
    finally:
        os.close(fd)
    raw = b"".join(chunks)
    if count != meta.st_size or raw[:16] != b"SQLite format 3\x00":
        die("SOURCE_BYTES_INVALID")
    # Mode=ro&immutable=1 requires an existing canonical file, no sidecars.
    uri = SRC.as_uri() + "?mode=ro&immutable=1"
    with sqlite3.connect(uri, uri=True, timeout=5) as db:
        tables = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if not TABLES.issubset(tables):
            die("FIRST_INSTALL_SCHEMA_MISSING")
        if db.execute("PRAGMA integrity_check").fetchone() != ("ok",):
            die("SQLITE_INTEGRITY_FAILURE")
        for table in TABLES:
            if db.execute('SELECT COUNT(*) FROM "' + table + '"').fetchone()[0] != 0:
                die("PAYMENT_ROWS_NOT_EMPTY")
        for table in ("auth_user", "django_session"):
            if table in tables and db.execute('SELECT COUNT(*) FROM "' + table + '"').fetchone()[0] != 0:
                die("CUSTOMER_OR_SESSION_PRESENT")
    if identity(SRC.lstat()) != identity(meta):
        die("SOURCE_CHANGED_AFTER_VERIFICATION")
    out = memoryview(raw)
    while out:
        wrote = os.write(sys.stdout.fileno(), out)
        if wrote <= 0:
            die("PIPE_WRITE_FAILED")
        out = out[wrote:]

if __name__ == "__main__":
    main()
