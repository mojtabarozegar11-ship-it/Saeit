#!/usr/bin/env python3
"""One-incident, owner-armed VPS cleanup of a FAILED MojPlayWin GPG partial.

Never touches a complete archive, manifest, other backup set, cPanel, or DB.
Uses metadata only: no archive contents, filenames, keys or credentials in logs.
"""
from __future__ import annotations

import json
import os
import re
import stat
import sys
import time
from pathlib import Path

INCIDENT_RUN = "41389864098"
EXPECTED_BYTES = 1_673_216_872
ARM = "DELETE_ONLY_FAILED_GPG_PARTIAL_41389864098"
PARTIAL = re.compile(
    r"^(mojplaywin_20261102T04[0-5][0-9][0-5][0-9]Z_[0-9a-f]{16})_mysql_gpgv2\.gpg\.partial$"
)
MAX_ENTRIES = 20_000
MIN_AGE_SECONDS = 600


def _absent(fd: int, name: str) -> bool:
    try:
        os.stat(name, dir_fd=fd, follow_symlinks=False)
    except FileNotFoundError:
        return True
    return False


def inspect_or_remove(
    home: Path, *, execute: bool = False,
    expected_bytes: int = EXPECTED_BYTES, now: float | None = None,
) -> dict:
    """Fail closed unless EXACTLY the known failed-run partial is identified."""
    root = Path(home) / ".private-mojplaywin-offhost-backups"
    fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        folder = os.fstat(fd)
        if (not stat.S_ISDIR(folder.st_mode)
                or folder.st_uid != os.geteuid()
                or folder.st_mode & 0o077):
            raise RuntimeError("PRIVATE_BACKUP_FOLDER_UNSAFE")
        matches = []
        with os.scandir(fd) as entries:
            for index, entry in enumerate(entries):
                if index >= MAX_ENTRIES:
                    raise RuntimeError("BACKUP_FOLDER_SCAN_LIMIT")
                if entry.name.endswith(".gpg.partial"):
                    matches.append(entry.name)
        if len(matches) != 1:
            raise RuntimeError("NOT_EXACTLY_ONE_FAILED_PARTIAL")
        name = matches[0]
        match = PARTIAL.fullmatch(name)
        if match is None:
            raise RuntimeError("PARTIAL_NOT_FROM_APPROVED_INCIDENT")
        before = os.stat(name, dir_fd=fd, follow_symlinks=False)
        if (not stat.S_ISREG(before.st_mode)
                or before.st_uid != os.geteuid()
                or before.st_mode & 0o177
                or before.st_nlink != 1
                or before.st_size != expected_bytes):
            raise RuntimeError("PARTIAL_METADATA_NOT_APPROVED")
        if (time.time() if now is None else now) - before.st_mtime < MIN_AGE_SECONDS:
            raise RuntimeError("PARTIAL_STILL_RECENT")
        stem = match.group(1)
        for suffix in (
            "_mysql_gpgv2.gpg", "_mysql_gpgv2.manifest.json",
            "_files_gpgv2.gpg", "_files_gpgv2.manifest.json",
        ):
            if not _absent(fd, stem + suffix):
                raise RuntimeError("COMPLETED_BACKUP_SIBLING_PRESENT")
        if execute:
            current = os.stat(name, dir_fd=fd, follow_symlinks=False)
            if ((current.st_dev, current.st_ino, current.st_size, current.st_mtime_ns)
                    != (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns)):
                raise RuntimeError("PARTIAL_CHANGED_BEFORE_UNLINK")
            os.unlink(name, dir_fd=fd)
            os.fsync(fd)
        return {
            "classification": "ONE_FAILED_GPG_PARTIAL_VPS_ONLY",
            "failed_run_id": INCIDENT_RUN,
            "approved_partial_count": 1,
            "approved_partial_bytes": before.st_size,
            "deleted": execute,
            "completed_backups_removed": 0,
            "manifests_removed": 0,
            "archive_contents_read": False,
            "key_bytes_read": False,
            "production_modified": False,
            "release_permitted": False,
        }
    finally:
        os.close(fd)


if __name__ == "__main__":
    try:
        if sys.argv[1:] == ["--audit"]:
            result = inspect_or_remove(Path.home())
        elif (sys.argv[1:] == ["--execute", ARM]
              and os.environ.get("MPW_APPROVED_INCIDENT_RUN") == INCIDENT_RUN):
            result = inspect_or_remove(Path.home(), execute=True)
        else:
            raise RuntimeError("OWNER_ARM_OR_MODE_MISSING")
        print("MPW_ONE_PARTIAL_CLEANUP=" + json.dumps(result, sort_keys=True))
    except (OSError, RuntimeError) as exc:
        # Fixed classes only; do not echo paths, filenames, keys or private data.
        print("MPW_ONE_PARTIAL_CLEANUP_REFUSED=" + type(exc).__name__, file=sys.stderr)
        raise SystemExit(1)
