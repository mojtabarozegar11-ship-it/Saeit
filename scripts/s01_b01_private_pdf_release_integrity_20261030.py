#!/usr/bin/env python3
"""S-01/B-01: offline private PDF integrity gate; never authorizes publication.

Usage: python scripts/s01_b01_private_pdf_release_integrity_20261030.py
       --private-root /private/Books/Publishing_Exit/B01_20261030/EXIT2
       --relative-pdf Mushroom_EN_VolII_TEXT_ONLY_EXIT2_PRIVATE_RELEASE_CANDIDATE.pdf
       --expected-sha256 <64 hex characters>
No network, database, buyer records, payment, factory or file writes.
"""
import argparse
import hashlib
import json
import os
import re
import stat
from pathlib import Path

MAX_BYTES = 512 * 1024 * 1024
CHUNK = 1024 * 1024


def inspect_private_pdf(root, relative, expected):
    if not re.fullmatch(r"[0-9a-fA-F]{64}", expected):
        raise ValueError("invalid expected SHA-256")
    rel = Path(relative)
    if rel.is_absolute() or not rel.parts or any(x in ("..", ".") for x in rel.parts):
        raise ValueError("unsafe relative path")
    root_path = Path(root)
    if not root_path.is_absolute():
        raise ValueError("private root must be absolute")
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    fd = os.open(root_path, flags)
    try:
        for part in rel.parts[:-1]:
            nxt = os.open(part, flags, dir_fd=fd)
            os.close(fd)
            fd = nxt
        file_fd = os.open(rel.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK,
                          dir_fd=fd)
        try:
            before = os.fstat(file_fd)
            if (not stat.S_ISREG(before.st_mode) or before.st_nlink != 1
                    or before.st_size < 16 or before.st_size > MAX_BYTES):
                raise ValueError("nonregular, linked, empty or oversized PDF")
            digest = hashlib.sha256()
            first = b""
            tail = b""
            read_count = 0
            with os.fdopen(os.dup(file_fd), "rb") as stream:
                while True:
                    data = stream.read(CHUNK)
                    if not data:
                        break
                    if not first:
                        first = data[:16]
                    tail = (tail + data)[-2048:]
                    digest.update(data)
                    read_count += len(data)
                    if read_count > MAX_BYTES:
                        raise ValueError("PDF grew beyond size limit")
            after = os.fstat(file_fd)
            if (read_count != before.st_size or
                    (before.st_dev, before.st_ino, before.st_mode, before.st_nlink,
                     before.st_size, before.st_mtime_ns) !=
                    (after.st_dev, after.st_ino, after.st_mode, after.st_nlink,
                     after.st_size, after.st_mtime_ns)):
                raise ValueError("PDF changed during read")
            if not first.startswith(b"%PDF-") or b"%%EOF" not in tail:
                raise ValueError("PDF header or EOF marker missing")
            actual = digest.hexdigest()
            if actual.lower() != expected.lower():
                raise ValueError("SHA-256 mismatch")
            return {"status": "FILE_HASH_VERIFIED", "sha256": actual,
                    "bytes": read_count, "file_verified": True,
                    "editorial_approved": False, "rights_approved": False,
                    "checkout_verified": False, "safe_to_publish": False}
        finally:
            os.close(file_fd)
    finally:
        os.close(fd)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--private-root", required=True)
    p.add_argument("--relative-pdf", required=True)
    p.add_argument("--expected-sha256", required=True)
    a = p.parse_args(argv)
    try:
        result = inspect_private_pdf(a.private_root, a.relative_pdf, a.expected_sha256)
        rc = 0
    except (OSError, ValueError):
        result = {"status": "BLOCKED_PRIVATE_PDF_INTEGRITY",
                  "file_verified": False, "safe_to_publish": False}
        rc = 2
    print(json.dumps(result, sort_keys=True))
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
