#!/usr/bin/env python3
"""Create a verified private gzip copy of ONE retired VPS log; retain original."""
from datetime import datetime, timezone
import gzip
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys

SOURCE = Path("/home/githubops/factory-runtime/operations/autonomous-product-cycle.log")
EXPECTED_BYTES = 328009123
EXPECTED_BASENAME_HASH = "1c96d4888f8e"
CAP_BYTES = 128 * 1024 * 1024
MIN_FREE_BYTES = 512 * 1024 * 1024
ARCHIVE = SOURCE.with_name(SOURCE.name + ".gz")
TEMP = SOURCE.with_name(SOURCE.name + ".gz.writing-20261106")
CHUNK = 1024 * 1024


def sha256_stream(readable):
    sha = hashlib.sha256()
    count = 0
    while True:
        block = readable.read(CHUNK)
        if not block:
            break
        sha.update(block)
        count += len(block)
    return sha.hexdigest(), count


def main():
    if os.geteuid() == 0:
        raise RuntimeError("must_run_as_nonroot")
    parent = SOURCE.parent
    if parent.is_symlink() or not parent.is_dir() or SOURCE.is_symlink():
        raise RuntimeError("unsafe_source_path")
    if hashlib.sha256(SOURCE.name.encode("utf8")).hexdigest()[:12] != EXPECTED_BASENAME_HASH:
        raise RuntimeError("wrong_source_name")
    if not SOURCE.is_file():
        raise RuntimeError("missing_source")
    before = SOURCE.stat()
    if before.st_size != EXPECTED_BYTES or before.st_nlink != 1:
        raise RuntimeError("source_changed_or_hardlinked")
    age = (datetime.now(timezone.utc).timestamp() - before.st_mtime) / 86400
    if age < 7:
        raise RuntimeError("source_not_retired")
    free_before = shutil.disk_usage(parent).free
    if free_before < MIN_FREE_BYTES + CAP_BYTES:
        raise RuntimeError("insufficient_free_space_for_bounded_archive")
    if ARCHIVE.exists() or ARCHIVE.is_symlink():
        raise RuntimeError("archive_exists_review_before_overwrite")
    if TEMP.exists() or TEMP.is_symlink():
        raise RuntimeError("temporary_archive_exists_review_before_overwrite")

    source_digest = hashlib.sha256()
    source_bytes = 0
    created = False
    try:
        file_descriptor = os.open(TEMP, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        created = True
        with os.fdopen(file_descriptor, "wb") as output:
            with gzip.GzipFile(fileobj=output, mode="wb", compresslevel=1, mtime=0) as zipped:
                with SOURCE.open("rb") as input_file:
                    while True:
                        block = input_file.read(CHUNK)
                        if not block:
                            break
                        source_digest.update(block)
                        source_bytes += len(block)
                        zipped.write(block)
                        if output.tell() > CAP_BYTES:
                            raise RuntimeError("archive_exceeded_size_cap")
            output.flush()
            os.fsync(output.fileno())

        after = SOURCE.stat()
        if (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns) != (
            before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns
        ) or source_bytes != EXPECTED_BYTES:
            raise RuntimeError("source_changed_during_archive")
        with gzip.open(TEMP, "rb") as verified:
            archived_digest, archived_bytes = sha256_stream(verified)
        if (archived_digest, archived_bytes) != (source_digest.hexdigest(), source_bytes):
            raise RuntimeError("archive_sha256_verification_failed")
        if TEMP.stat().st_size > CAP_BYTES:
            raise RuntimeError("archive_exceeded_size_cap")
        os.replace(TEMP, ARCHIVE)
        created = False
        result = {
            "schema": "saeit.vps.retired-log-preserving-archive.v1",
            "state": "verified_archive_created",
            "source_retained": SOURCE.is_file(),
            "source_bytes": source_bytes,
            "archive_bytes": ARCHIVE.stat().st_size,
            "source_archive_sha256_equal": True,
            "free_bytes_before": free_before,
            "free_bytes_after": shutil.disk_usage(parent).free,
            "target_basenames_redacted": True,
        }
        if not result["source_retained"]:
            raise RuntimeError("original_source_missing_after_archive")
        print("VPS_RETIRED_LOG_ARCHIVE_RESULT=" + json.dumps(result, sort_keys=True))
    finally:
        if created and TEMP.is_file() and not TEMP.is_symlink():
            TEMP.unlink()


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print("VPS_RETIRED_LOG_ARCHIVE_FAILED=" + type(exc).__name__ + ":" + str(exc),
              file=sys.stderr)
        sys.exit(1)
