#!/usr/bin/env python3
"""One-time fail-closed rotation of a specific, inactive VPS lifecycle log.

This script never touches a database, product, customer record, other log or
cron/service setting. The source log remains in place as an empty file only
after a fully verified, immutable local gzip archive has been committed.
"""
from __future__ import annotations

import argparse
import fcntl
import gzip
import hashlib
import json
import os
import stat
import tempfile
import time
from pathlib import Path

ROOT = Path("/home/githubops/factory-runtime/operations")
LOG_NAME = "factory-lifecycle-stages.log"
LOCK_NAME = ".lifecycle-tick.lock"
ARCHIVE_NAME = "factory-lifecycle-stages.log.verified-20261106.gz"
EXPECTED_TARGET_SIZE = 30_679_816
MIN_AGE_SECONDS = 8 * 86400
MIN_DISK_FREE = 256 * 1024 * 1024
STABILITY_SECONDS = 2
BLOCK_SIZE = 1024 * 1024


def _snapshot(info):
    return (info.st_dev, info.st_ino, info.st_size,
            info.st_mtime_ns, info.st_nlink)


def _safe_file(path: Path, device: int):
    info = os.lstat(path)
    if (not stat.S_ISREG(info.st_mode) or info.st_dev != device
            or info.st_nlink != 1):
        raise RuntimeError("TARGET_NOT_SINGLE_REGULAR_FILE")
    return info


def _sha_stream(source):
    digest = hashlib.sha256()
    total = 0
    while True:
        block = source.read(BLOCK_SIZE)
        if not block:
            break
        digest.update(block)
        total += len(block)
    return digest.hexdigest(), total


def rotate(root: Path = ROOT, apply: bool = False) -> dict:
    root = Path(root)
    if root.is_symlink() or not root.is_dir():
        raise RuntimeError("OPERATIONS_ROOT_UNSAFE")
    base = root.resolve(strict=True)
    device = os.lstat(base).st_dev
    target = base / LOG_NAME
    lock_path = base / LOCK_NAME
    archive = base / ARCHIVE_NAME
    initial = _safe_file(target, device)
    _safe_file(lock_path, device)
    if os.path.lexists(archive):
        raise RuntimeError("ARCHIVE_ALREADY_EXISTS_NOT_OVERWRITING")
    if initial.st_size != EXPECTED_TARGET_SIZE:
        raise RuntimeError("PINNED_LOG_SIZE_CHANGED")
    if time.time() - initial.st_mtime < MIN_AGE_SECONDS:
        raise RuntimeError("LOG_RECENTLY_ACTIVE")
    if os.statvfs(base).f_bavail * os.statvfs(base).f_frsize < MIN_DISK_FREE:
        raise RuntimeError("INSUFFICIENT_WORKING_SPACE")
    report = {
        "schema": "factory.vps.lifecycle-log.verified-rotation.v1",
        "target": "(redacted-pinned-lifecycle-log)",
        "source_bytes_before": initial.st_size,
        "archive_created": False,
        "source_truncated": False,
        "factory_services_changed": False,
        "other_files_changed": False,
    }
    if not apply:
        return dict(report, mode="dry_run", gate="READY_RECHECK_UNDER_LOCK")

    lock_fd = os.open(lock_path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
    try:
        if _snapshot(os.fstat(lock_fd)) != _snapshot(_safe_file(lock_path, device)):
            raise RuntimeError("LOCK_FILE_CHANGED")
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RuntimeError("FACTORY_LIFECYCLE_LOCK_BUSY") from exc
        source_fd = os.open(target, os.O_RDWR | os.O_NOFOLLOW | os.O_CLOEXEC)
        try:
            if _snapshot(os.fstat(source_fd)) != _snapshot(initial):
                raise RuntimeError("LOG_CHANGED_BEFORE_LOCKED_ROTATION")
            time.sleep(STABILITY_SECONDS)
            if _snapshot(os.fstat(source_fd)) != _snapshot(_safe_file(target, device)):
                raise RuntimeError("LOG_CHANGED_WHILE_LOCKED")
            if _snapshot(os.fstat(source_fd)) != _snapshot(initial):
                raise RuntimeError("LOG_CHANGED_DURING_STABILITY_WAIT")

            tmp_fd, tmp_name = tempfile.mkstemp(prefix=".lifecycle-archive-",
                                                 dir=str(base))
            try:
                with os.fdopen(tmp_fd, "wb") as output:
                    with gzip.GzipFile(filename="", mode="wb", fileobj=output,
                                       compresslevel=6, mtime=0) as compressed:
                        hasher = hashlib.sha256()
                        total = 0
                        with os.fdopen(os.dup(source_fd), "rb") as source:
                            source.seek(0)
                            for block in iter(lambda: source.read(BLOCK_SIZE), b""):
                                compressed.write(block)
                                hasher.update(block)
                                total += len(block)
                    output.flush()
                    os.fsync(output.fileno())
                if total != initial.st_size:
                    raise RuntimeError("ARCHIVED_BYTE_COUNT_MISMATCH")
                with gzip.open(tmp_name, "rb") as restored:
                    verified_sha, verified_bytes = _sha_stream(restored)
                if verified_sha != hasher.hexdigest() or verified_bytes != total:
                    raise RuntimeError("GZIP_ROUNDTRIP_FAILED")
                os.lseek(source_fd, 0, os.SEEK_SET)
                with os.fdopen(os.dup(source_fd), "rb") as unchanged_source:
                    original_sha, original_bytes = _sha_stream(unchanged_source)
                if original_sha != hasher.hexdigest() or original_bytes != total:
                    raise RuntimeError("SOURCE_CHANGED_BEFORE_COMMIT")
                if (_snapshot(os.fstat(source_fd)) != _snapshot(initial)
                        or _snapshot(_safe_file(target, device)) != _snapshot(initial)):
                    raise RuntimeError("SOURCE_METADATA_CHANGED_BEFORE_COMMIT")
                if os.path.lexists(archive):
                    raise RuntimeError("ARCHIVE_DESTINATION_RACE")
                os.replace(tmp_name, archive)
                directory_fd = os.open(base, os.O_RDONLY | os.O_DIRECTORY)
                try:
                    os.fsync(directory_fd)
                finally:
                    os.close(directory_fd)
                archive_size = os.lstat(archive).st_size
                # This is the ONLY operation that frees space. The exact source
                # bytes can be restored from the checksum-verified archive.
                os.ftruncate(source_fd, 0)
                os.fsync(source_fd)
                if os.fstat(source_fd).st_size != 0:
                    raise RuntimeError("SOURCE_NOT_TRUNCATED")
                return dict(report, mode="applied", gate="VERIFIED_ARCHIVED",
                            archive_created=True, source_truncated=True,
                            archive_bytes=archive_size,
                            source_sha256_prefix=hasher.hexdigest()[:16],
                            estimated_reclaimed_bytes=initial.st_size - archive_size)
            finally:
                if os.path.exists(tmp_name):
                    os.unlink(tmp_name)
        finally:
            os.close(source_fd)
    finally:
        os.close(lock_fd)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true",
                        help="Perform the single pinned, verified, lock-guarded rotation.")
    options = parser.parse_args()
    result = rotate(apply=options.apply)
    print("FACTORY_LIFECYCLE_LOG_ROTATION=" + json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
