#!/usr/bin/env python3
"""Read-only integrity screen for privately supplied SKU72/225 ZIPs.

Never opens, modifies or processes SKU879. No claim of content quality, rights,
shop deliverability, or correspondence with any private VPS candidate.
"""
import argparse
import errno
import hashlib
import json
import os
import stat
import sys
import zipfile
from pathlib import Path

MAX_ARCHIVE_BYTES = 2 * 1024**3
MAX_UNCOMPRESSED_BYTES = 4 * 1024**3
MAX_ENTRY_BYTES = 512 * 1024**2
MAX_ENTRIES = 2000
MAX_COMPRESSION_RATIO = 250


class QCBlocked(Exception):
    pass


def _safe_name(name):
    if not name or "\\" in name or "\x00" in name or name.startswith("/"):
        return False
    # PurePosixPath normalizes interior "." and repeated separators: reject
    # raw aliases before normalization, including Windows drive and controls.
    parts = name.rstrip("/").split("/")
    if any(p in ("", ".", "..") for p in parts):
        return False
    if ":" in parts[0] or any(ord(ch) < 32 or ord(ch) == 127 for ch in name):
        return False
    return True


def verify(sku, archive, expected_sha256=None):
    if sku not in (72, 225):
        raise QCBlocked("SKU_NOT_AUTHORIZED")
    path = Path(archive).absolute()
    # Pin each ancestor by descriptor: a symlink swap cannot redirect the open.
    directory_flags = (os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
                       | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_CLOEXEC", 0))
    leaf_flags = (os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
                  | getattr(os, "O_NONBLOCK", 0) | getattr(os, "O_CLOEXEC", 0))
    try:
        parent_fd = os.open("/", directory_flags)
        try:
            for component in path.parts[1:-1]:
                next_fd = os.open(component, directory_flags, dir_fd=parent_fd)
                os.close(parent_fd)
                parent_fd = next_fd
            fd = os.open(path.parts[-1], leaf_flags, dir_fd=parent_fd)
        finally:
            os.close(parent_fd)
    except OSError as exc:
        reason = "LINKED_PATH" if exc.errno in (errno.ELOOP, errno.ENOTDIR) else "ARCHIVE_UNAVAILABLE"
        raise QCBlocked(reason) from exc
    with os.fdopen(fd, "rb") as handle:
        meta = os.fstat(handle.fileno())
        if not stat.S_ISREG(meta.st_mode) or meta.st_size > MAX_ARCHIVE_BYTES:
            raise QCBlocked("NOT_BOUNDED_REGULAR_FILE")
        digest = hashlib.sha256()
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
        hexdigest = digest.hexdigest()
        if expected_sha256 and hexdigest.lower() != expected_sha256.lower():
            raise QCBlocked("SHA256_MISMATCH")
        handle.seek(0)
        try:
            with zipfile.ZipFile(handle, "r") as z:
                infos = z.infolist()
                if not infos or len(infos) > MAX_ENTRIES:
                    raise QCBlocked("INVALID_MEMBER_COUNT")
                seen = set()
                total = 0
                files = 0
                for info in infos:
                    if not _safe_name(info.filename):
                        raise QCBlocked("UNSAFE_MEMBER_NAME")
                    key = info.filename.casefold().rstrip("/")
                    if key in seen:
                        raise QCBlocked("DUPLICATE_MEMBER_NAME")
                    seen.add(key)
                    mode = (info.external_attr >> 16) & 0xffff
                    member_type = stat.S_IFMT(mode)
                    if member_type not in (0, stat.S_IFREG, stat.S_IFDIR):
                        raise QCBlocked("SPECIAL_FILE_MEMBER")
                    if info.flag_bits & 1:
                        raise QCBlocked("ENCRYPTED_MEMBER")
                    if info.file_size > MAX_ENTRY_BYTES:
                        raise QCBlocked("OVERSIZED_MEMBER")
                    if info.file_size > MAX_COMPRESSION_RATIO * max(1, info.compress_size):
                        raise QCBlocked("EXCESSIVE_COMPRESSION_RATIO")
                    total += info.file_size
                    if total > MAX_UNCOMPRESSED_BYTES:
                        raise QCBlocked("UNCOMPRESSED_LIMIT")
                    if info.is_dir():
                        continue
                    files += 1
                    with z.open(info, "r") as member:
                        while member.read(1024 * 1024):
                            pass  # ZipFile checks each member CRC; no extraction.
                return {"schema": "f01-sku-archive-qc.v1", "sku": sku,
                        "status": "ZIP_INTEGRITY_VERIFIED_ONLY",
                        "sha256": hexdigest, "member_count": len(infos),
                        "file_count": files, "uncompressed_bytes": total,
                        "read_only": True, "content_quality_verified": False,
                        "rights_verified": False, "store_delivery_verified": False,
                        "vps_candidate_equivalence_verified": False}
        except (zipfile.BadZipFile, RuntimeError, EOFError, OSError, ValueError) as exc:
            raise QCBlocked("ZIP_READ_OR_CRC_FAILURE") from exc


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sku", type=int, required=True, choices=[72, 225])
    parser.add_argument("--zip", required=True)
    parser.add_argument("--expected-sha256")
    args = parser.parse_args()
    try:
        result = verify(args.sku, args.zip, args.expected_sha256)
    except QCBlocked as exc:
        print(json.dumps({"status": "BLOCKED", "reason": str(exc),
                          "read_only": True, "no_production_change": True}))
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
