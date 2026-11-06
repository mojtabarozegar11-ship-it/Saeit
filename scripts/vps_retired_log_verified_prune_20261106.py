#!/usr/bin/env python3
"""Prune precisely one retired VPS log only after verifying retained gzip backup.

This script never touches SQLite, databases, application code, cron, or other logs.
Requires an opt-in workflow input, invoked only after owner approval.
"""
from datetime import datetime, timezone
import gzip
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys

SOURCE = Path("/home/githubops/factory-runtime/operations/autonomous-product-cycle.log")
ARCHIVE = SOURCE.with_name(SOURCE.name + ".gz")
SOURCE_BYTES = 328009123
ARCHIVE_BYTES = 103210162
EXPECTED_NAME_HASH = "1c96d4888f8e"
CHUNK = 1024 * 1024


def hash_file(reader):
    digest = hashlib.sha256()
    count = 0
    while True:
        data = reader.read(CHUNK)
        if not data:
            break
        digest.update(data)
        count += len(data)
    return digest.digest(), count


def check_own_open_descriptors(stat):
    """Reject open same-owner FDs; other-UID FDs may not be observable."""
    seen = 0
    limited = False
    for item in Path("/proc").iterdir():
        if not item.name.isdecimal():
            continue
        try:
            fds = list((item / "fd").iterdir())
            seen += 1
        except OSError:
            limited = True
            continue
        for fd in fds:
            try:
                reference = fd.stat()
            except OSError:
                continue
            if reference.st_dev == stat.st_dev and reference.st_ino == stat.st_ino:
                raise RuntimeError("source_held_open_by_visible_process")
    return {"scanned_processes": seen, "other_process_visibility_limited": limited}


def main():
    if os.geteuid() == 0:
        raise RuntimeError("refuse_root")
    if SOURCE.parent.is_symlink() or not SOURCE.parent.is_dir():
        raise RuntimeError("unsafe_parent")
    if hashlib.sha256(SOURCE.name.encode("utf8")).hexdigest()[:12] != EXPECTED_NAME_HASH:
        raise RuntimeError("wrong_name")
    if SOURCE.is_symlink() or ARCHIVE.is_symlink():
        raise RuntimeError("symlink_denied")
    if not SOURCE.is_file() or not ARCHIVE.is_file():
        raise RuntimeError("source_or_archive_missing")
    old = SOURCE.stat()
    saved = ARCHIVE.stat()
    if (old.st_size != SOURCE_BYTES or old.st_nlink != 1 or
            saved.st_size != ARCHIVE_BYTES or saved.st_nlink != 1 or
            (saved.st_mode & 0o077) != 0):
        raise RuntimeError("unexpected_size_links_or_permissions")
    age = (datetime.now(timezone.utc).timestamp() - old.st_mtime) / 86400
    if age < 7:
        raise RuntimeError("source_recently_modified")
    fd_evidence = check_own_open_descriptors(old)
    with SOURCE.open("rb") as raw:
        original_digest, original_size = hash_file(raw)
    with gzip.open(ARCHIVE, "rb") as expanded:
        stored_digest, stored_size = hash_file(expanded)
    if original_size != SOURCE_BYTES or stored_size != SOURCE_BYTES:
        raise RuntimeError("invalid_decompressed_size")
    if original_digest != stored_digest:
        raise RuntimeError("gzip_and_original_sha256_differ")
    current = SOURCE.stat()
    if (old.st_dev, old.st_ino, old.st_size, old.st_mtime_ns) != (
        current.st_dev, current.st_ino, current.st_size, current.st_mtime_ns
    ):
        raise RuntimeError("source_changed_during_validation")
    check_own_open_descriptors(current)
    before_free = shutil.disk_usage(SOURCE.parent).free
    SOURCE.unlink()
    directory_fd = os.open(SOURCE.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(directory_fd)
    finally:
        os.close(directory_fd)
    if not ARCHIVE.is_file() or ARCHIVE.stat().st_size != ARCHIVE_BYTES:
        raise RuntimeError("archive_missing_after_prune")
    print("VPS_RETIRED_LOG_PRUNE_RESULT=" + json.dumps({
        "state": "one_verified_original_log_removed",
        "original_bytes": SOURCE_BYTES,
        "archive_bytes_retained": ARCHIVE_BYTES,
        "archive_content_verified": True,
        "original_missing": not SOURCE.exists(),
        "free_bytes_before": before_free,
        "free_bytes_after": shutil.disk_usage(SOURCE.parent).free,
        "visible_fd_check": fd_evidence,
        "database_files_touched": 0,
    }, sort_keys=True))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print("VPS_RETIRED_LOG_PRUNE_FAILED=" + type(exc).__name__ + ":" + str(exc),
              file=sys.stderr)
        sys.exit(1)
