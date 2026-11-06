#!/usr/bin/env python3
"""Fail-closed, one-line repair of the commercial inquiry POST-size guard.

Changes exactly one private form handler on the public cPanel site. No forms
are submitted, emails sent, customer records read, or payment paths changed.
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import pwd
import re
import stat
import sys
import tempfile


TARGET = Path("/home/zomorod2/mojplaywin.com/mpw-editorial/revenue/inquiry.php")
BACKUP_DIR = Path("/home/zomorod2/.local/share/mpw-inquiry-size-guard-backups")
OLD = (b"if (strlen((string)($_SERVER['CONTENT_LENGTH']??''))>6 && "
       b"(int)($_SERVER['CONTENT_LENGTH']??0)>12000) $errors[]='Request is too large.';")
NEW = (b"if ((int)($_SERVER['CONTENT_LENGTH']??0)>12000) "
       b"$errors[]='Request is too large.';")


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def transform(raw: bytes) -> bytes:
    if not 4000 < len(raw) < 100000 or raw.count(OLD) != 1 or NEW in raw:
        raise RuntimeError("Unexpected form version or already repaired")
    for required in (
        b"<?php", b"MojPlayWin first-party commercial inquiry",
        b"function store_inquiry(", b"if ($_SERVER['REQUEST_METHOD']==='POST')",
        b"name=\"csrf\"", b"name=\"consent\"",
    ):
        if required not in raw:
            raise RuntimeError("Unexpected inquiry source structure")
    new = raw.replace(OLD, NEW)
    if new.count(NEW) != 1 or len(new) >= len(raw):
        raise RuntimeError("Size-guard substitution failed")
    return new


def guard() -> None:
    if pwd.getpwuid(os.geteuid()).pw_name != "zomorod2":
        raise RuntimeError("Wrong hosting user")
    if (TARGET.is_symlink() or not TARGET.is_file() or
            TARGET.parent.resolve() != TARGET.parent):
        raise RuntimeError("Unexpected inquiry route")
    st = TARGET.stat()
    if (not stat.S_ISREG(st.st_mode) or st.st_uid != os.geteuid() or
            st.st_nlink != 1 or stat.S_IMODE(st.st_mode) & 0o022):
        raise RuntimeError("Unexpected source permissions")
    if BACKUP_DIR.is_symlink() or BACKUP_DIR.parent.is_symlink():
        raise RuntimeError("Unsafe backup directory")


def atomic_write(path: Path, body: bytes, mode: int) -> None:
    fd, temp = tempfile.mkstemp(prefix=".mpw-inquiry-size-", dir=path.parent)
    try:
        os.fchmod(fd, mode)
        with os.fdopen(fd, "wb") as stream:
            stream.write(body)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, path)
        dfd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(dfd)
        finally:
            os.close(dfd)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def owned_paths(run_id: str) -> tuple[Path, Path]:
    if not re.fullmatch(r"[0-9]{8,20}", run_id):
        raise RuntimeError("Invalid one-time release ID")
    return (BACKUP_DIR / f"{run_id}.original.php",
            BACKUP_DIR / f"{run_id}.published.sha256")


def main(operation: str, run_id: str = "") -> None:
    if operation == "selftest":
        fixture = (b"<?php MojPlayWin first-party commercial inquiry "
                   b"function store_inquiry( "
                   b"if ($_SERVER['REQUEST_METHOD']==='POST') "
                   b"name=\"csrf\" name=\"consent\" " + OLD + b" ?>")
        fixture += b" " * 4500
        fixed = transform(fixture)
        assert fixed.count(NEW) == 1 and OLD not in fixed
        try:
            transform(fixed)
        except RuntimeError:
            pass
        else:
            raise AssertionError("Must refuse a second write")
        print("MPW_INQUIRY_SIZE_GUARD_SELFTEST=PASS")
        return

    guard()
    raw = TARGET.read_bytes()
    if operation == "preflight":
        fixed = transform(raw)
        print(f"MPW_INQUIRY_SIZE_PREFLIGHT=PASS old_sha256={sha(raw)} new_sha256={sha(fixed)}")
        return
    backup, marker = owned_paths(run_id)
    if operation == "publish":
        fixed = transform(raw)
        BACKUP_DIR.mkdir(mode=0o700, parents=True, exist_ok=True)
        if stat.S_IMODE(BACKUP_DIR.stat().st_mode) != 0o700:
            raise RuntimeError("Backup directory permissions are not private")
        if any(p.exists() or p.is_symlink() for p in (backup, marker)):
            raise RuntimeError("Release identifier already used")
        fd = os.open(backup, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, "wb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        atomic_write(marker, (sha(fixed) + "\n").encode(), 0o600)
        if TARGET.read_bytes() != raw:
            raise RuntimeError("Concurrent inquiry edit detected")
        try:
            atomic_write(TARGET, fixed, stat.S_IMODE(TARGET.stat().st_mode))
            if TARGET.read_bytes() != fixed:
                raise RuntimeError("Published source differs from verified transformation")
        except BaseException:
            if TARGET.read_bytes() == fixed:
                atomic_write(TARGET, raw, stat.S_IMODE(TARGET.stat().st_mode))
            raise
        print(f"MPW_INQUIRY_SIZE_GUARD_PUBLISHED=PASS old_sha256={sha(raw)} new_sha256={sha(fixed)}")
        return
    if operation == "rollback":
        if not backup.is_file() or backup.is_symlink() or not marker.is_file() or marker.is_symlink():
            raise RuntimeError("Release backup missing")
        if sha(raw) != marker.read_text().strip():
            raise RuntimeError("Source changed since release; rollback refused")
        previous = backup.read_bytes()
        transform(previous)
        atomic_write(TARGET, previous, stat.S_IMODE(TARGET.stat().st_mode))
        if TARGET.read_bytes() != previous:
            raise RuntimeError("Rollback verification failed")
        print("MPW_INQUIRY_SIZE_GUARD_ROLLBACK=PASS")
        return
    raise RuntimeError("Expected selftest, preflight, publish or rollback")


if __name__ == "__main__":
    main(*sys.argv[1:])
