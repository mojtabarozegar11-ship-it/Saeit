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
    # Keep an O_NOFOLLOW source descriptor open while copying. Do not reopen
    # source by filename after checking its hash (symlink replacement race).
    reader_flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    with os.fdopen(os.open(source, reader_flags), "rb") as inp:
        src_before = os.fstat(inp.fileno())
        if not stat.S_ISREG(src_before.st_mode):
            raise RestoreError("RECOVERY_SOURCE_UNSAFE")
        fd = os.open(destination, flags, 0o600)
        try:
            with os.fdopen(fd, "wb") as out:
                shutil.copyfileobj(inp, out, length=131072)
                out.flush()
                os.fsync(out.fileno())
            src_after = os.fstat(inp.fileno())
            if (src_before.st_ino != src_after.st_ino
                    or src_before.st_dev != src_after.st_dev
                    or src_before.st_size != src_after.st_size
                    or src_before.st_mtime_ns != src_after.st_mtime_ns
                    or src_before.st_ctime_ns != src_after.st_ctime_ns
                    or source.is_symlink()
                    or source.stat().st_ino != src_after.st_ino):
                raise RestoreError("RECOVERY_SOURCE_CHANGED_DURING_COPY")
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

    # Refuse an existing collision archive before moving any live file.
    # This preflight avoids a partial quarantine if the second archive path
    # was already occupied by another release/recovery attempt.
    for label in ("app", "dossier"):
        conflict = backup / ("concurrent-" + label + "-" + release_sha + ".php")
        if os.path.lexists(conflict):
            raise RestoreError("CONFLICT_ARCHIVE_ALREADY_EXISTS")

    live_app = private / "app.php"
    live_dossier = private / "genetics-center.php"
    known_dossier = {candidate_dossier} if old_dossier == "ABSENT" else {old_dossier, candidate_dossier}
    # Validate BOTH live paths before producing any conflict archive or
    # replacing any live file. A broken symlink must not strand app.php.
    observed: dict[Path, str | None] = {}
    for live in (live_app, live_dossier):
        observed[live] = digest_file(live) if os.path.lexists(live) else None

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

    quarantined = []
    def preserve_unexpected(live: Path, known: set[str], label: str) -> None:
        actual = observed[live]
        if actual is None or actual in known:
            return
        target = backup / ("concurrent-" + label + "-" + release_sha + ".php")
        if os.path.lexists(target):
            raise RestoreError("CONFLICT_ARCHIVE_ALREADY_EXISTS")
        # COPY first. Moving the live file to the archive would remove it
        # before the other live path is validated, risking a broken site.
        backup_copy(live, target, actual)
        if digest_file(target) != actual or digest_file(live) != actual:
            raise RestoreError("CONFLICT_COPY_VERIFICATION_FAILED")
        quarantined.append(label)

    try:
        preserve_unexpected(live_app, {old_app, candidate_app}, "app")
        preserve_unexpected(live_dossier, known_dossier, "dossier")
        # Revalidate BOTH live file states immediately before first rename.
        for live, old_hash in observed.items():
            now = digest_file(live) if os.path.lexists(live) else None
            if now != old_hash:
                raise RestoreError("LIVE_CHANGED_DURING_RECOVERY_PREP")
        os.replace(staged, live_app)
        if old_dossier == "ABSENT":
            if os.path.lexists(live_dossier):
                # A concurrent dossier can be removed ONLY after its exact
                # current bytes were preserved and verified in a private
                # archive. Refuse any change after the archive was created.
                actual_dossier = digest_file(live_dossier)
                if actual_dossier != observed[live_dossier]:
                    raise RestoreError("DOSSIER_CHANGED_DURING_RESTORE")
                if actual_dossier != candidate_dossier:
                    archive = backup / ("concurrent-dossier-" + release_sha + ".php")
                    if ("dossier" not in quarantined
                            or digest_file(archive) != actual_dossier):
                        raise RestoreError("DOSSIER_CONFLICT_NOT_VERIFIED")
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
