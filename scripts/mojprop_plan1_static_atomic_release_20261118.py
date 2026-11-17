#!/usr/bin/env python3
"""Exact-byte Moj Prop Plan1 static release transaction, independent of Django.

NOT an instruction to deploy. The CLI defaults to read-only "preflight".
Production install MUST be invoked only by a separate owner-reviewed release
workflow after real SQL+app+media OFFHOST backup and independent restore,
authorized maintenance window, known-good on-site rollback, safe account quota,
and broker/legal review of the published text. Passing booleans is not evidence
that the offsite restore actually happened.

No DB/Passenger process/SSH/cPanel configuration, money or customer state touched.
The fixed current and candidate digests are independently measured; unknown
target content or stale candidate always blocks instead of overwriting.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import fcntl
import json
import os
from pathlib import Path
import pwd
import stat
import sys
import tempfile

ACCOUNT = "zomorod2"
LIVE = Path("/home/zomorod2/mojplaywin.com/moj-prop/index.html")
BACKUP = Path("/home/zomorod2/.backups/mojprop-pre-plan1-76918c5129ff-20261118.html")
LOCK = Path("/home/zomorod2/.backups/.mojprop-prelaunch-static.lock")
ORIGINAL_SHA = "76918c5129ff669ef02f82435a68f61a32d70141800712100d4a7fe9e8554895"
ORIGINAL_SIZE = 23869
CANDIDATE_SHA = "13bd45c1d6b62f03058428b3086e71b17de4f2776238e8ab85a49d648fce49b0"
CANDIDATE_SIZE = 46455
MAX_BYTES = 256 * 1024
MIN_STATIC_FILESYSTEM_FREE = 4 * 1024 * 1024
OWNER_ACK = "AUTHORIZE-MOJPROP-01-STATIC-ONLY-20261118"
NOFOLLOW = getattr(os, "O_NOFOLLOW", 0)


class ExactStaticReleaseDenied(ValueError):
    """Something changed: never clobber any unrecognized live or private file."""


@dataclass(frozen=True)
class ReleaseReviews:
    """Claims from the separate reviewing executor, NOT cryptographic proof."""
    owner_approved_specific_install: bool = False
    genuine_offhost_full_restore_verified_by_independent_reviewer: bool = False
    cpanel_account_quota_checked: bool = False
    owner_reviewed_exact_html_copy_and_legal_claims: bool = False
    safe_rollback_checked_by_independent_reviewer: bool = False

    def approved(self) -> bool:
        return all(getattr(self, field) is True for field in self.__dataclass_fields__)


def digest(data: bytes) -> str:
    return sha256(data).hexdigest()


def exact(data: bytes, expected_hash: str, expected_size: int, purpose: str) -> None:
    if type(data) is not bytes or len(data) != expected_size or len(data) > MAX_BYTES:
        raise ExactStaticReleaseDenied(purpose + "_SIZE_CHANGED")
    if digest(data) != expected_hash:
        raise ExactStaticReleaseDenied(purpose + "_SHA_CHANGED")


def _regular_read(path: Path, uid: int) -> tuple[bytes, os.stat_result]:
    # This check rejects symlinks, world-writable and hard-linked files, and
    # authenticates the actual inode opened, not only path metadata.
    s = path.lstat()
    if (not stat.S_ISREG(s.st_mode) or s.st_uid != uid or
            s.st_mode & 0o002 or s.st_nlink != 1 or s.st_size > MAX_BYTES):
        raise ExactStaticReleaseDenied("SOURCE_OR_TARGET_PERMISSIONS")
    fd = os.open(str(path), os.O_RDONLY | os.O_CLOEXEC | NOFOLLOW)
    try:
        t = os.fstat(fd)
        if (not stat.S_ISREG(t.st_mode) or t.st_dev != s.st_dev or
                t.st_ino != s.st_ino or t.st_uid != uid or t.st_size != s.st_size):
            raise ExactStaticReleaseDenied("FILE_RACE_OR_OWNER_CHANGED")
        blocks = []
        remaining = MAX_BYTES + 1
        while remaining:
            block = os.read(fd, min(remaining, 65536))
            if not block:
                break
            blocks.append(block)
            remaining -= len(block)
        payload = b"".join(blocks)
        if len(payload) != t.st_size:
            raise ExactStaticReleaseDenied("SHORT_OR_CHANGED_FILE")
        return payload, t
    finally:
        os.close(fd)


def _directory_checks(live: Path, backup: Path, uid: int) -> None:
    for folder in (live.parent, live.parent.parent, backup.parent):
        s = folder.lstat()
        if not stat.S_ISDIR(s.st_mode) or folder.is_symlink() or s.st_mode & 0o002:
            raise ExactStaticReleaseDenied("UNSAFE_RELEASE_DIRECTORY")
    bs = backup.parent.stat()
    if bs.st_uid != uid or bs.st_mode & 0o077:
        raise ExactStaticReleaseDenied("ROLLBACK_FOLDER_NOT_OWNER_PRIVATE")


def _validate_candidate(candidate: Path, uid: int) -> bytes:
    if candidate == LIVE or candidate == BACKUP:
        raise ExactStaticReleaseDenied("CANDIDATE_OVERLAPS_LIVE_OR_BACKUP")
    data, _ = _regular_read(candidate, uid)
    exact(data, CANDIDATE_SHA, CANDIDATE_SIZE, "PROPOSED")
    required = (b"MOJ-PROP-01", b"not payable today",
                b"Contact MOJ PROP about Plan 1 (free)",
                b"Do not send money today.", b"bearer token by email")
    if not all(term in data for term in required):
        raise ExactStaticReleaseDenied("PUBLISHED_CONSUMER_WARNINGS_MISSING")
    if b'href="/moj-prop-interest/form/' in data:
        raise ExactStaticReleaseDenied("LIVE_404_CONTACT_LINK_REINTRODUCED")
    return data


def _backup_valid(path: Path, uid: int) -> bool:
    try:
        raw, info = _regular_read(path, uid)
    except FileNotFoundError:
        return False
    if info.st_mode & 0o077:
        raise ExactStaticReleaseDenied("BACKUP_NOT_PRIVATE")
    exact(raw, ORIGINAL_SHA, ORIGINAL_SIZE, "ROLLBACK")
    return True


def _save_original_if_absent(raw: bytes, path: Path, uid: int) -> None:
    exact(raw, ORIGINAL_SHA, ORIGINAL_SIZE, "ORIGINAL")
    if path.exists() or path.is_symlink():
        if not _backup_valid(path, uid):
            raise ExactStaticReleaseDenied("ROLLBACK_IDENTICAL_BACKUP_NOT_PRESENT")
        return
    fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_EXCL | NOFOLLOW, 0o600)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(raw)
            f.flush()
            os.fsync(f.fileno())
    except BaseException:
        # Do not unlink any recovered original or previous backup.
        raise
    if not _backup_valid(path, uid):
        raise ExactStaticReleaseDenied("ROLLBACK_BACKUP_CREATION_UNVERIFIED")


def _atomic_swap(live: Path, replacement: bytes, current_hash: str, uid: int) -> None:
    expected=ORIGINAL_SIZE if current_hash == ORIGINAL_SHA else CANDIDATE_SIZE
    previous, old_stat = _regular_read(live, uid)
    exact(previous, current_hash, expected, "PRE_SWAP")
    fd, temporary = tempfile.mkstemp(prefix=".mojprop-01-reviewed-", suffix=".tmp",
                                     dir=str(live.parent))
    try:
        os.fchmod(fd, stat.S_IMODE(old_stat.st_mode))
        with os.fdopen(fd, "wb") as f:
            f.write(replacement)
            f.flush()
            os.fsync(f.fileno())
        now, new_stat = _regular_read(live, uid)
        if (digest(now) != current_hash or
                new_stat.st_ino != old_stat.st_ino or
                new_stat.st_mtime_ns != old_stat.st_mtime_ns):
            raise ExactStaticReleaseDenied("TARGET_CHANGED_BEFORE_ATOMIC_SWAP")
        os.replace(temporary, live)
        dirfd = os.open(str(live.parent), os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(dirfd)
        finally:
            os.close(dirfd)
        done, done_stat = _regular_read(live, uid)
        if digest(done) != digest(replacement) or (
                stat.S_IMODE(done_stat.st_mode) != stat.S_IMODE(old_stat.st_mode)):
            raise ExactStaticReleaseDenied("ATOMIC_SWAP_DURABILITY_OR_MODE_UNVERIFIED")
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def transact(mode: str, *, live: Path = LIVE, backup: Path = BACKUP,
             candidate: Path | None = None, uid: int | None = None,
             reviews: ReleaseReviews | None = None, owner_ack: str = "") -> dict:
    """No writes in preflight. Apply is impossible without all separate gates."""
    if mode not in ("preflight", "install", "rollback"):
        raise ExactStaticReleaseDenied("INVALID_OPERATION")
    uid = os.geteuid() if uid is None else uid
    _directory_checks(live, backup, uid)
    if mode != "rollback" and candidate is None:
        raise ExactStaticReleaseDenied("NO_CANDIDATE_SOURCE")
    current, _ = _regular_read(live, uid)
    if mode == "preflight":
        exact(current, ORIGINAL_SHA, ORIGINAL_SIZE, "CURRENT")
        _validate_candidate(candidate, uid)
        if backup.exists() or backup.is_symlink():
            _backup_valid(backup, uid)
        return {"status": "PINNED_SOURCE_PREFLIGHT_ONLY", "writes": False,
                "old_size": ORIGINAL_SIZE, "new_size": CANDIDATE_SIZE,
                "private_rollback_exists": backup.exists(),
                "fresh_restore_independently_proven": False,
                "install_allowed_by_preflight": False}

    if mode == "install":
        if (type(reviews) is not ReleaseReviews or not reviews.approved()
                or owner_ack != OWNER_ACK):
            raise ExactStaticReleaseDenied("OWNER_OR_INDEPENDENT_RESTORE_GATES_UNMET")
        # These are attested facts by the separate reviewer; not verified here.
        exact(current, ORIGINAL_SHA, ORIGINAL_SIZE, "CURRENT")
        payload = _validate_candidate(candidate, uid)
    else:
        exact(current, CANDIDATE_SHA, CANDIDATE_SIZE, "CURRENT_INSTALL")
        if not _backup_valid(backup, uid):
            raise ExactStaticReleaseDenied("VALID_PRIVATE_ROLLBACK_MISSING")
        payload, _ = _regular_read(backup, uid)
        exact(payload, ORIGINAL_SHA, ORIGINAL_SIZE, "ROLLBACK")

    if os.statvfs(live.parent).f_bavail * os.statvfs(live.parent).f_frsize < MIN_STATIC_FILESYSTEM_FREE:
        raise ExactStaticReleaseDenied("STATIC_TRANSACTION_LOCAL_HEADROOM_LOW")
    lock = backup.parent / LOCK.name
    fd = os.open(str(lock), os.O_CREAT | os.O_RDWR | NOFOLLOW, 0o600)
    try:
        info = os.fstat(fd)
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != uid or
                info.st_mode & 0o077 or info.st_nlink != 1):
            raise ExactStaticReleaseDenied("TRANSACTION_LOCK_UNSAFE")
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        now, _ = _regular_read(live, uid)
        exact(now, ORIGINAL_SHA if mode=="install" else CANDIDATE_SHA,
              ORIGINAL_SIZE if mode=="install" else CANDIDATE_SIZE, "LOCKED_CURRENT")
        if mode == "install":
            _save_original_if_absent(now, backup, uid)
        _atomic_swap(live, payload, ORIGINAL_SHA if mode=="install" else CANDIDATE_SHA, uid)
    finally:
        os.close(fd)
    return {"status":"PINNED_STATIC_INSTALLED" if mode=="install" else "PINNED_ORIGINAL_ROLLED_BACK",
            "writes": True, "verified_live_sha256":digest(payload),
            "database_modified":False,"payments_enabled":False}


def main() -> None:
    # The CLI only permits preflight and rollback. An install requires a
    # separate, independently reviewed owner release orchestration that passes
    # proven gate objects; no automatic GitHub push may enable "install".
    if len(sys.argv) not in (2,3) or os.geteuid()==0:
        raise SystemExit("MOJPROP_STATIC_CLI_BAD_ARGUMENTS_OR_ROOT")
    if pwd.getpwuid(os.geteuid()).pw_name != ACCOUNT:
        raise SystemExit("MOJPROP_STATIC_CLI_NOT_CPANEL_OWNER")
    mode=sys.argv[1]
    if mode not in ("preflight","rollback"):
        raise SystemExit("MOJPROP_STATIC_CLI_INSTALL_NOT_EXPOSED")
    if mode=="preflight" and len(sys.argv)!=3:
        raise SystemExit("MOJPROP_STATIC_CLI_NEEDS_REVIEWED_CANDIDATE_PATH")
    if mode=="rollback" and len(sys.argv)!=2:
        raise SystemExit("MOJPROP_STATIC_CLI_ROLLBACK_NO_CANDIDATE")
    try:
        result=transact(mode,candidate=Path(sys.argv[2]) if mode=="preflight" else None)
    except (OSError,ExactStaticReleaseDenied,BlockingIOError):
        raise SystemExit("MOJPROP_STATIC_EXACT_GUARD_BLOCKED") from None
    print("MOJPROP_STATIC_RELEASE_STATE="+json.dumps(result,sort_keys=True))


if __name__=="__main__":
    main()
