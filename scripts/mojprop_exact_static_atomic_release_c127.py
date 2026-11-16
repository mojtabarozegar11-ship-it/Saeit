#!/usr/bin/env python3
"""C127 one-static-file Moj Prop form recovery, fail-closed and no daemon changes.

Only a trusted owner-gated release job may invoke the live CLI. The expected
original was independently captured via public GET and stored in private GitHub.
The fixed webroot, backup and SHA identities are not configurable through CLI.
No DB, SSH keys, port, service, Cron, payment or customer file is modified.
"""
from __future__ import annotations

import fcntl
import hashlib
import json
import os
from pathlib import Path
import pwd
import stat
import sys
import tempfile

ACCOUNT = "zomorod2"
TARGET = Path("/home/zomorod2/mojplaywin.com/moj-prop/index.html")
BACKUP = Path("/home/zomorod2/.backups/mojprop-public-before-c127-b2e9381b.html")
LOCK = Path("/home/zomorod2/.backups/.mojprop-static-c127.lock")
ORIGINAL_SHA = "b2e9381b2ac70a92b62de150277b9089bb28ca56c7a98948dd42673435bfc3ff"
CANDIDATE_SHA = "76918c5129ff669ef02f82435a68f61a32d70141800712100d4a7fe9e8554895"
ORIGINAL_SIZE = 23812
CANDIDATE_SIZE = 23869
ROOT = b'<select id="horizon">'
END = b'</select>'
PAIRS = (
    (b"Today / urgent", b"urgent"),
    (b"This week", b"week"),
    (b"This month", b"month"),
    (b"Initial review only", b"review"),
)
BOUND = 512_000


class SafetyGate(ValueError):
    pass


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def candidate(original: bytes) -> bytes:
    if (type(original) is not bytes or len(original) != ORIGINAL_SIZE
            or digest(original) != ORIGINAL_SHA or original.count(ROOT) != 1
            or not original.startswith(b"<!-- MOJ_PROP_CATALOG_RELEASE_V4 -->")):
        raise SafetyGate("UNRECOGNIZED_OR_CHANGED_ORIGINAL")
    start = original.index(ROOT) + len(ROOT)
    stop = original.find(END, start)
    if stop <= start or original.find(ROOT, start) != -1:
        raise SafetyGate("UNSAFE_HORIZON_BOUNDARIES")
    section = original[start:stop]
    if section.count(b"<option>") != 4 or section.count(b"</option>") != 4:
        raise SafetyGate("UNEXPECTED_HORIZON_MARKUP")
    proposed = section
    for label, value in PAIRS:
        before = b"<option>" + label + b"</option>"
        after = b'<option value="' + value + b'">' + label + b"</option>"
        if proposed.count(before) != 1:
            raise SafetyGate("MISSING_EXACT_REVIEWED_OPTION")
        proposed = proposed.replace(before, after, 1)
    if proposed.replace(b'<option value="urgent">', b"<option>", 1) \
       .replace(b'<option value="week">', b"<option>", 1) \
       .replace(b'<option value="month">', b"<option>", 1) \
       .replace(b'<option value="review">', b"<option>", 1) != section:
        raise SafetyGate("INVERSE_NOT_BYTE_EXACT")
    outcome = original[:start] + proposed + original[stop:]
    if len(outcome) != CANDIDATE_SIZE or digest(outcome) != CANDIDATE_SHA:
        raise SafetyGate("CANDIDATE_BYTE_HASH_NOT_APPROVED")
    return outcome


def checked_regular(path: Path, *, euid: int) -> tuple[bytes, os.stat_result]:
    s = path.lstat()
    if (not stat.S_ISREG(s.st_mode) or s.st_uid != euid
            or s.st_mode & 0o002 or s.st_nlink != 1
            or s.st_size > BOUND or path.is_symlink()):
        raise SafetyGate("FILE_IDENTITY_OR_PERMISSION_UNSAFE")
    with path.open("rb") as f:
        content = f.read(BOUND + 1)
    if len(content) != s.st_size:
        raise SafetyGate("FILE_READ_RACE")
    return content, s


def checked_paths(target: Path, backup: Path, *, euid: int) -> None:
    for item in (target.parent, target.parent.parent, backup.parent):
        s = item.lstat()
        if not stat.S_ISDIR(s.st_mode) or item.is_symlink():
            raise SafetyGate("UNSAFE_DIRECTORY")
    if backup.parent.stat().st_uid != euid:
        raise SafetyGate("BACKUP_OWNER_MISMATCH")
    space = os.statvfs(target.parent)
    if space.f_bavail * space.f_frsize < 2_097_152:
        raise SafetyGate("INSUFFICIENT_SMALL_FILE_ROLLBACK_SPACE")


def durable_backup(original: bytes, backup: Path, *, euid: int) -> None:
    if backup.exists() or backup.is_symlink():
        existing, s = checked_regular(backup, euid=euid)
        if s.st_mode & 0o077 or digest(existing) != ORIGINAL_SHA:
            raise SafetyGate("EXISTING_BACKUP_NOT_EXACT_PRIVATE")
        return
    fd = os.open(str(backup), os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(original)
            f.flush()
            os.fsync(f.fileno())
    except BaseException:
        raise
    restored, s = checked_regular(backup, euid=euid)
    if s.st_mode & 0o077 or digest(restored) != ORIGINAL_SHA:
        raise SafetyGate("BACKUP_VERIFICATION_FAILED")


def atomic_replace(target: Path, payload: bytes, expected_sha: str, *, euid: int) -> None:
    old, old_stat = checked_regular(target, euid=euid)
    if digest(old) != expected_sha:
        raise SafetyGate("CONCURRENT_TARGET_OR_HASH_CHANGE")
    fd, tmp = tempfile.mkstemp(prefix=".mojprop-index-c127-", suffix=".tmp", dir=target.parent)
    try:
        os.fchmod(fd, stat.S_IMODE(old_stat.st_mode))
        with os.fdopen(fd, "wb") as f:
            f.write(payload)
            f.flush()
            os.fsync(f.fileno())
        current, s = checked_regular(target, euid=euid)
        if (digest(current) != expected_sha or s.st_ino != old_stat.st_ino
                or s.st_mtime_ns != old_stat.st_mtime_ns):
            raise SafetyGate("CHANGED_BEFORE_ATOMIC_SWAP")
        os.replace(tmp, target)
        try:
            dirfd = os.open(str(target.parent), os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(dirfd)
            finally:
                os.close(dirfd)
        except OSError as exc:
            raise SafetyGate("DIRECTORY_DURABILITY_UNKNOWN") from exc
        new, new_stat = checked_regular(target, euid=euid)
        if digest(new) != digest(payload) or stat.S_IMODE(new_stat.st_mode) != stat.S_IMODE(old_stat.st_mode):
            raise SafetyGate("POST_SWAP_CONTENT_OR_MODE_INVALID")
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def transact(mode: str, target: Path = TARGET, backup: Path = BACKUP, *, euid: int | None = None) -> dict:
    if mode not in ("preflight", "apply", "rollback"):
        raise SafetyGate("UNKNOWN_ACTION")
    euid = os.geteuid() if euid is None else euid
    checked_paths(target, backup, euid=euid)
    if mode == "preflight":
        current, _ = checked_regular(target, euid=euid)
        candidate(current)  # verifies exact original and approved delta
        return {"mode": mode, "status": "source_exact", "writes": False,
                "original_sha256": ORIGINAL_SHA, "candidate_sha256": CANDIDATE_SHA}
    lock = backup.parent / LOCK.name
    lockfd = os.open(str(lock), os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    try:
        fcntl.flock(lockfd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        current, _ = checked_regular(target, euid=euid)
        if mode == "apply":
            proposal = candidate(current)
            durable_backup(current, backup, euid=euid)
            atomic_replace(target, proposal, ORIGINAL_SHA, euid=euid)
            return {"mode": mode, "status": "candidate_installed", "writes": True,
                    "sha256": CANDIDATE_SHA, "rollback_original": ORIGINAL_SHA}
        if digest(current) == ORIGINAL_SHA:
            return {"mode": mode, "status": "already_original", "writes": False}
        if digest(current) != CANDIDATE_SHA or len(current) != CANDIDATE_SIZE:
            raise SafetyGate("ROLLBACK_REFUSES_UNKNOWN_LIVE_FILE")
        original, s = checked_regular(backup, euid=euid)
        if s.st_mode & 0o077 or digest(original) != ORIGINAL_SHA or len(original) != ORIGINAL_SIZE:
            raise SafetyGate("ROLLBACK_BACKUP_UNSAFE")
        atomic_replace(target, original, CANDIDATE_SHA, euid=euid)
        return {"mode": mode, "status": "original_restored", "writes": True,
                "sha256": ORIGINAL_SHA}
    finally:
        os.close(lockfd)


def main() -> None:
    if (len(sys.argv) != 2 or sys.argv[1] not in ("preflight", "apply", "rollback")
            or os.geteuid() == 0 or pwd.getpwuid(os.geteuid()).pw_name != ACCOUNT):
        raise SystemExit("MOJPROP_C127_ABORT_WRONG_ACCOUNT_OR_ACTION")
    try:
        result = transact(sys.argv[1])
    except (OSError, SafetyGate, BlockingIOError) as exc:
        # Never print paths, page content, user data or traceback into Actions.
        raise SystemExit("MOJPROP_C127_SAFE_ABORT_" + type(exc).__name__) from None
    print("MOJPROP_C127_STATE=" + json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
