#!/usr/bin/env python3
"""Fail-closed pre-switch integrity check for the private Zomorod business desk.

Rechecks live sources, exact backups and staged candidates immediately before
an authorized installer switches live PHP paths. Read-only. Never prints source,
secrets, filenames or financial records.
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import re
import stat
import sys

MAX_SOURCE_BYTES = 2_000_000


class GuardViolation(Exception):
    pass


def hash_regular(path: Path) -> str:
    if path.is_symlink():
        raise GuardViolation("SYMLINK_FORBIDDEN")
    before = path.stat()
    if not stat.S_ISREG(before.st_mode) or before.st_size <= 0 or before.st_size > MAX_SOURCE_BYTES:
        raise GuardViolation("UNSAFE_SOURCE_FILE")
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    with os.fdopen(os.open(path, flags), "rb") as handle:
        opened = os.fstat(handle.fileno())
        if opened.st_dev != before.st_dev or opened.st_ino != before.st_ino:
            raise GuardViolation("FILE_REPLACED_DURING_OPEN")
        digest = hashlib.sha256()
        while True:
            part = handle.read(131072)
            if not part:
                break
            digest.update(part)
        after = os.fstat(handle.fileno())
    if (after.st_dev != before.st_dev or after.st_ino != before.st_ino
            or after.st_mtime_ns != before.st_mtime_ns or after.st_size != before.st_size
            or after.st_ctime_ns != before.st_ctime_ns):
        raise GuardViolation("FILE_MUTATED_WHILE_HASHING")
    if path.is_symlink() or path.stat().st_ino != after.st_ino:
        raise GuardViolation("PATH_REPLACED_AFTER_HASHING")
    return digest.hexdigest()


def check(
    live_app: Path, live_dossier: Path, backup_app: Path,
    backup_dossier: Path, staged_app: Path, staged_dossier: Path,
    expected_app: str, expected_dossier: str,
    candidate_app: str, candidate_dossier: str,
) -> None:
    for value in (expected_app, candidate_app, candidate_dossier):
        if re.fullmatch(r"[0-9a-f]{64}", value) is None:
            raise GuardViolation("INVALID_SHA256")
    if expected_dossier != "ABSENT" and re.fullmatch(r"[0-9a-f]{64}", expected_dossier) is None:
        raise GuardViolation("INVALID_DOSSIER_BASELINE")
    if hash_regular(live_app) != expected_app:
        raise GuardViolation("LIVE_APP_CHANGED_SINCE_PREFLIGHT")
    if hash_regular(backup_app) != expected_app:
        raise GuardViolation("BACKUP_APP_NOT_EXACT")
    if expected_dossier == "ABSENT":
        if os.path.lexists(live_dossier) or os.path.lexists(backup_dossier):
            raise GuardViolation("UNEXPECTED_DOSSIER_APPEARED")
    else:
        if hash_regular(live_dossier) != expected_dossier:
            raise GuardViolation("LIVE_DOSSIER_CHANGED_SINCE_PREFLIGHT")
        if hash_regular(backup_dossier) != expected_dossier:
            raise GuardViolation("BACKUP_DOSSIER_NOT_EXACT")
    if hash_regular(staged_app) != candidate_app:
        raise GuardViolation("CANDIDATE_APP_CHANGED_IN_STAGE")
    if hash_regular(staged_dossier) != candidate_dossier:
        raise GuardViolation("CANDIDATE_DOSSIER_CHANGED_IN_STAGE")


def main() -> None:
    if len(sys.argv) != 11:
        print("PRE_SWITCH_GUARD=INVALID_ARGUMENT_COUNT", file=sys.stderr)
        raise SystemExit(2)
    parts = [Path(x) for x in sys.argv[1:7]]
    expected = sys.argv[7:]
    try:
        check(*parts, *expected)
    except (GuardViolation, OSError, ValueError) as exc:
        # The failure reason is a fixed symbol, not a file path or user data.
        label = str(exc) if isinstance(exc, GuardViolation) else type(exc).__name__
        print("PRE_SWITCH_GUARD=" + label, file=sys.stderr)
        raise SystemExit(8) from None
    print("PRE_SWITCH_GUARD=SOURCE_BACKUP_AND_CANDIDATES_MATCH")
    print("PRE_SWITCH_GUARD_READ_ONLY=yes")


if __name__ == "__main__":
    main()
