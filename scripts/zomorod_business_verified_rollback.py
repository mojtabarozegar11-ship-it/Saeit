#!/usr/bin/env python3
"""Verified private PHP rollback; never touches public_html or accounting DB.

Run only on a failed manual genetics release. Backups are hash-verified before
a live path is touched. Unknown concurrent edits are quarantined, not destroyed.
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import re
import shutil
import stat
import sys

EXPECTED_PRIVATE = Path("/home/zomorod2/.private/zomorod-business")
EXPECTED_BACKUP_PARENT = Path("/home/zomorod2/.backups/zomorod-business-genetics")
MAX_PHP_BYTES = 2_000_000


class RestoreError(Exception):
    pass


def valid_sha(value: str) -> bool:
    return bool(re.fullmatch(r"[0-9a-f]{64}", value))


def digest_file(file: Path) -> str:
    if file.is_symlink() or not file.is_file():
        raise RestoreError("UNSAFE_FILE")
    before = file.stat()
    if not stat.S_ISREG(before.st_mode) or not (0 < before.st_size <= MAX_PHP_BYTES):
        raise RestoreError("INVALID_FILE_SIZE")
    digest = hashlib.sha256()
    fd = os.open(file, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    with os.fdopen(fd, "rb") as stream:
        opened = os.fstat(stream.fileno())
        if opened.st_ino != before.st_ino or opened.st_dev != before.st_dev:
            raise RestoreError("FILE_CHANGED_DURING_OPEN")
        while True:
            block = stream.read(131072)
            if not block:
                break
            digest.update(block)
        end = os.fstat(stream.fileno())
    if (opened.st_size != end.st_size or opened.st_ctime_ns != end.st_ctime_ns
            or opened.st_mtime_ns != end.st_mtime_ns):
        raise RestoreError("FILE_CHANGED_DURING_READ")
    if file.is_symlink() or file.stat().st_ino != end.st_ino:
        raise RestoreError("PATH_CHANGED_DURING_READ")
    return digest.hexdigest()


def backup_copy(source: Path, destination: Path, expected_hash: str) -> None:
    if digest_file(source) != expected_hash:
        raise RestoreError("BACKUP_DIGEST_MISMATCH")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(destination, flags, 0o600)
    try:
        with os.fdopen(fd, "wb") as out, source.open("rb") as inp:
            shutil.copyfileobj(inp, out, length=131072)
            out.flush()
            os.fsync(out.fileno())
        if digest_file(destination) != expected_hash:
            raise RestoreError("RECOVERY_COPY_CORRUPT")
    except BaseException:
        destination.unlink(missing_ok=True)
        raise


def restore(
    private: Path, backup: Path, release_sha: str,
    old_app: str, old_dossier: str, candidate_app: str, candidate_dossier: str,
) -> dict[str, str]:
    if not re.fullmatch(r"[0-9a-f]{40}", release_sha):
        raise RestoreError("BAD_RELEASE_ID")
    if any(not valid_sha(v) for v in (old_app, candidate_app, candidate_dossier)):
        raise RestoreError("BAD_EXPECTED_HASH")
    if old_dossier != "ABSENT" and not valid_sha(old_dossier):
        raise RestoreError("BAD_DOSSIER_HASH")
    for folder in (private, backup):
        if folder.is_symlink() or not folder.is_dir():
            raise RestoreError("UNSAFE_DIRECTORY")
    if backup.stat().st_mode & 0o077:
        raise RestoreError("INSECURE_BACKUP_DIRECTORY")
    if digest_file(backup / "app.php") != old_app:
        raise RestoreError("BACKUP_APP_INVALID")
    if old_dossier == "ABSENT":
        if os.path.lexists(backup / "genetics-center.php"):
            raise RestoreError("UNEXPECTED_BACKUP_DOSSIER")
    elif digest_file(backup / "genetics-center.php") != old_dossier:
        raise RestoreError("BACKUP_DOSSIER_INVALID")

    # Prepare all needed recovery files first. A preflight failure leaves the
    # original live files unchanged and keeps the original backup intact.
    staged = private / (".rollback-app-ready-" + release_sha)
    staged_dossier = private / (".rollback-dossier-ready-" + release_sha)
    if os.path.lexists(staged) or os.path.lexists(staged_dossier):
        raise RestoreError("RECOVERY_STAGE_ALREADY_EXISTS")
    try:
        backup_copy(backup / "app.php", staged, old_app)
        if old_dossier != "ABSENT":
            backup_copy(backup / "genetics-center.php", staged_dossier, old_dossier)
    except BaseException:
        staged.unlink(missing_ok=True)
        staged_dossier.unlink(missing_ok=True)
        raise

    live_app = private / "app.php"
    live_dossier = private / "genetics-center.php"
    quarantined = []
    def preserve_unexpected(live: Path, expected: set[str], label: str) -> None:
        if not os.path.lexists(live):
            return
        actual = digest_file(live)
        if actual in expected:
            return
        target = backup / ("concurrent-" + label + "-" + release_sha + ".php")
        if os.path.lexists(target):
            raise RestoreError("CONFLICT_ARCHIVE_ALREADY_EXISTS")
        # If another writer changed the live PHP, preserve those bytes in
        # the private backup before restoring the previously verified version.
        os.replace(live, target)
        if digest_file(target) != actual:
            raise RestoreError("CONFLICT_ARCHIVE_VERIFICATION_FAILED")
        quarantined.append(label)

    try:
        preserve_unexpected(live_app, {old_app, candidate_app}, "app")
        preserve_unexpected(
            live_dossier,
            ({candidate_dossier} if old_dossier == "ABSENT" else {old_dossier, candidate_dossier}),
            "dossier",
        )
        os.replace(staged, live_app)
        if old_dossier == "ABSENT":
            if os.path.lexists(live_dossier):
                # Only a known candidate can be removed; other versions were
                # preserved above in the restricted backup folder.
                if digest_file(live_dossier) != candidate_dossier:
                    raise RestoreError("DOSSIER_CHANGED_DURING_RESTORE")
                live_dossier.unlink()
        else:
            os.replace(staged_dossier, live_dossier)
        if digest_file(live_app) != old_app:
            raise RestoreError("APP_RESTORE_NOT_VERIFIED")
        if old_dossier == "ABSENT":
            if os.path.lexists(live_dossier):
                raise RestoreError("DOSSIER_ABSENCE_NOT_RESTORED")
        elif digest_file(live_dossier) != old_dossier:
            raise RestoreError("DOSSIER_RESTORE_NOT_VERIFIED")
        return {"result": "VERIFIED", "conflicts_preserved": str(len(quarantined))}
    finally:
        staged.unlink(missing_ok=True)
        staged_dossier.unlink(missing_ok=True)


def main() -> None:
    if len(sys.argv) != 8:
        raise SystemExit("ROLLBACK=INVALID_ARGUMENT_COUNT")
    private, backup = (Path(sys.argv[1]), Path(sys.argv[2]))
    release_sha = sys.argv[3]
    if private != EXPECTED_PRIVATE or backup != EXPECTED_BACKUP_PARENT / release_sha:
        raise SystemExit("ROLLBACK=UNAUTHORIZED_PATHS")
    if os.geteuid() == 0 or os.geteuid() != private.stat().st_uid:
        raise SystemExit("ROLLBACK=INVALID_USER")
    try:
        data = restore(private, backup, release_sha, *sys.argv[4:])
    except (RestoreError, OSError, ValueError) as err:
        kind = str(err) if isinstance(err, RestoreError) else type(err).__name__
        print("ROLLBACK=FAILED_" + kind, file=sys.stderr)
        raise SystemExit(9) from None
    print("ROLLBACK=" + data["result"])
    print("ROLLBACK_CONCURRENT_UPDATES_PRESERVED=" + data["conflicts_preserved"])
    print("ROLLBACK_PUBLIC_FILES_CHANGED=no")
    print("ROLLBACK_DATABASE_CHANGED=no")


if __name__ == "__main__":
    main()
