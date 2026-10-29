#!/usr/bin/env python3
"""Isolated SQLite backup copy rehearsal; never run against the live database.

Input is not modified. A passing test does NOT prove off-host provenance,
backup freshness, WAL completeness, production restore, or deploy readiness.
"""
import argparse
import hashlib
import json
import os
import shutil
import sqlite3
import stat
import tempfile
from pathlib import Path

MAX_BYTES = 8 * 1024**3

class Blocked(Exception):
    pass

def check_input(path):
    p = Path(path).absolute()
    if any(x.is_symlink() for x in (p, *p.parents)):
        raise Blocked("LINKED_PATH")
    fd = os.open(p, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0))
    meta = os.fstat(fd)
    if not stat.S_ISREG(meta.st_mode) or meta.st_size < 100 or meta.st_size > MAX_BYTES:
        os.close(fd)
        raise Blocked("UNBOUNDED_OR_INVALID_INPUT")
    return fd, meta.st_size

def verify(path, expected_sha256, temp_root=None):
    if not expected_sha256 or len(expected_sha256) != 64 or any(c not in "0123456789abcdefABCDEF" for c in expected_sha256):
        raise Blocked("EXPECTED_SHA256_REQUIRED")
    fd, size = check_input(path)
    try:
        with os.fdopen(fd, "rb") as source:
            if source.read(16) != b"SQLite format 3\x00":
                raise Blocked("NOT_SQLITE")
            source.seek(0)
            digest = hashlib.sha256()
            while True:
                chunk = source.read(1024 * 1024)
                if not chunk:
                    break
                digest.update(chunk)
            actual = digest.hexdigest()
            if actual != expected_sha256.lower():
                raise Blocked("SHA256_MISMATCH")
            source.seek(0)
            with tempfile.TemporaryDirectory(prefix="f01-restore-", dir=temp_root) as tmp:
                target = Path(tmp) / "rehearsal.sqlite3"
                with open(target, "xb") as out:
                    shutil.copyfileobj(source, out, 1024 * 1024)
                with open(target, "rb") as restored:
                    if hashlib.file_digest(restored, "sha256").hexdigest() != actual:
                        raise Blocked("RESTORE_COPY_HASH_MISMATCH")
                con = sqlite3.connect(target.as_uri() + "?mode=ro&immutable=1", uri=True, timeout=5)
                try:
                    con.execute("PRAGMA query_only=ON")
                    if con.execute("PRAGMA integrity_check").fetchall() != [("ok",)]:
                        raise Blocked("SQLITE_INTEGRITY_FAILURE")
                    schema_count = con.execute("SELECT count(*) FROM sqlite_master WHERE type IN ('table','index','view','trigger')").fetchone()[0]
                finally:
                    con.close()
            return {"schema": "f01-offhost-sqlite-rehearsal.v1", "status": "ISOLATED_COPY_INTEGRITY_VERIFIED",
                    "sha256": actual, "bytes": size, "schema_objects": schema_count,
                    "input_modified": False, "production_restore_proved": False,
                    "offhost_provenance_verified": False, "deployment_authorized": False}
    except (OSError, sqlite3.Error) as exc:
        raise Blocked("IO_OR_SQLITE_FAILURE") from exc

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--backup", required=True)
    p.add_argument("--expected-sha256", required=True)
    p.add_argument("--scratch-dir", help="isolated scratch with enough free space")
    args = p.parse_args()
    try:
        result = verify(args.backup, args.expected_sha256, args.scratch_dir)
        code = 0
    except (Blocked, OSError) as exc:
        result = {"schema": "f01-offhost-sqlite-rehearsal.v1", "status": "BLOCKED",
                  "reason": str(exc) if isinstance(exc, Blocked) else "INPUT_UNAVAILABLE",
                  "production_restore_proved": False, "deployment_authorized": False}
        code = 2
    print(json.dumps(result, sort_keys=True))
    return code

if __name__ == "__main__":
    raise SystemExit(main())
