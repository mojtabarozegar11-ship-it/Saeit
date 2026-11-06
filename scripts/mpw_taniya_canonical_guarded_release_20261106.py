#!/usr/bin/env python3
"""Pin one missing canonical on the live Taniya Studio Django template.

Only its HTML template and the verified Passenger restart marker are touched.
No game state, purchases, email, models, settings or database are changed.
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


APP = Path("/home/zomorod2/Saeit-staging")
DOC = Path("/home/zomorod2/mojplaywin.com")
TARGET = APP / "templates/taniya_studio/index.html"
RESTART = DOC / "tmp/restart.txt"
BACKUPS = Path("/home/zomorod2/.local/share/mpw-taniya-canonical-backups")
BEFORE = b"  <title>Taniya Studio \xe2\x80\x94 Play a little, imagine a lot</title>\n"
ADDITION = b'  <link rel="canonical" href="https://mojplaywin.com/taniya/">\n'


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def transform(raw: bytes) -> bytes:
    if (not 1000 < len(raw) < 500000 or raw.count(BEFORE) != 1
            or b'rel="canonical"' in raw or b"rel='canonical'" in raw
            or b'<html lang="en">' not in raw or b'<head>' not in raw):
        raise RuntimeError("Unexpected or already modified Taniya template")
    updated = raw.replace(BEFORE, BEFORE + ADDITION)
    if updated.count(ADDITION) != 1 or b"</head>" not in updated:
        raise RuntimeError("Canonical insertion validation failed")
    return updated


def verify_paths() -> None:
    if pwd.getpwuid(os.geteuid()).pw_name != "zomorod2":
        raise RuntimeError("Wrong hosting user")
    if (APP.is_symlink() or DOC.is_symlink() or
            APP.resolve() != APP or DOC.resolve() != DOC):
        raise RuntimeError("Unexpected app or document root")
    wsgi = DOC / "passenger_wsgi.py"
    if (not wsgi.is_file() or wsgi.is_symlink() or
            b"Saeit-staging" not in wsgi.read_bytes()):
        raise RuntimeError("Active Passenger application source changed")
    if TARGET.is_symlink() or not TARGET.is_file():
        raise RuntimeError("Taniya template unavailable")
    st = TARGET.stat()
    if (not stat.S_ISREG(st.st_mode) or st.st_uid != os.geteuid() or
            st.st_nlink != 1 or stat.S_IMODE(st.st_mode) & 0o022):
        raise RuntimeError("Unsafe template permissions")
    if RESTART.is_symlink() or not RESTART.parent.is_dir() or RESTART.parent.is_symlink():
        raise RuntimeError("Actual Passenger restart location unavailable")
    if BACKUPS.is_symlink() or BACKUPS.parent.is_symlink():
        raise RuntimeError("Unsafe private backup location")


def atomic(path: Path, content: bytes, mode: int) -> None:
    fd, temp = tempfile.mkstemp(prefix=".mpw-taniya-canonical-", dir=path.parent)
    try:
        os.fchmod(fd, mode)
        with os.fdopen(fd, "wb") as file:
            file.write(content)
            file.flush()
            os.fsync(file.fileno())
        os.replace(temp, path)
        dfd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(dfd)
        finally:
            os.close(dfd)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def restart() -> None:
    if RESTART.is_symlink():
        raise RuntimeError("Unexpected symlinked Passenger marker")
    if RESTART.exists():
        if not RESTART.is_file():
            raise RuntimeError("Unexpected Passenger marker type")
        os.utime(RESTART, None)
    else:
        fd = os.open(RESTART, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o644)
        os.close(fd)


def owned_paths(run_id: str) -> tuple[Path, Path]:
    if not re.fullmatch(r"[0-9]{8,20}", run_id):
        raise RuntimeError("Invalid one-off release ID")
    return (BACKUPS / f"{run_id}.original.html",
            BACKUPS / f"{run_id}.published.sha256")


def run(operation: str, run_id: str = "") -> None:
    if operation == "selftest":
        fixture = (b'<!doctype html><html lang="en"><head>\n' + BEFORE +
                   b'</head><body><h1>Taniya</h1></body></html>' + b' ' * 1500)
        new = transform(fixture)
        assert new.count(ADDITION) == 1
        try:
            transform(new)
        except RuntimeError:
            pass
        else:
            raise AssertionError("Re-release must refuse known source")
        print("MPW_TANIYA_CANONICAL_SELFTEST=PASS")
        return

    verify_paths()
    old = TARGET.read_bytes()
    if operation == "preflight":
        new = transform(old)
        print(f"MPW_TANIYA_CANONICAL_PREFLIGHT=PASS old_sha256={sha(old)} new_sha256={sha(new)}")
        return
    backup, marker = owned_paths(run_id)
    if operation == "publish":
        new = transform(old)
        BACKUPS.mkdir(mode=0o700, parents=True, exist_ok=True)
        if stat.S_IMODE(BACKUPS.stat().st_mode) != 0o700:
            raise RuntimeError("Backup directory not private")
        if any(p.exists() or p.is_symlink() for p in (backup, marker)):
            raise RuntimeError("Release already exists")
        fd = os.open(backup, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, "wb") as file:
            file.write(old)
            file.flush()
            os.fsync(file.fileno())
        atomic(marker, (sha(new) + "\n").encode(), 0o600)
        if TARGET.read_bytes() != old:
            raise RuntimeError("Concurrent Taniya template edit")
        try:
            atomic(TARGET, new, stat.S_IMODE(TARGET.stat().st_mode))
            restart()
            if TARGET.read_bytes() != new:
                raise RuntimeError("Template verification failed")
        except BaseException:
            if TARGET.read_bytes() == new:
                atomic(TARGET, old, stat.S_IMODE(TARGET.stat().st_mode))
                restart()
            raise
        print("MPW_TANIYA_CANONICAL_PUBLISHED=PASS new_sha256=" + sha(new))
        return
    if operation == "rollback":
        if not backup.is_file() or backup.is_symlink() or not marker.is_file() or marker.is_symlink():
            raise RuntimeError("Release backup unavailable")
        if sha(old) != marker.read_text().strip():
            raise RuntimeError("Source changed after release; rollback refused")
        previous = backup.read_bytes()
        transform(previous)
        atomic(TARGET, previous, stat.S_IMODE(TARGET.stat().st_mode))
        restart()
        if TARGET.read_bytes() != previous:
            raise RuntimeError("Taniya rollback validation failed")
        print("MPW_TANIYA_CANONICAL_ROLLBACK=PASS")
        return
    raise RuntimeError("Expected selftest, preflight, publish or rollback")


if __name__ == "__main__":
    run(*sys.argv[1:])
