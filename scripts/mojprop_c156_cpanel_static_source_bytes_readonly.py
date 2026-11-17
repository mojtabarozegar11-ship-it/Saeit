#!/usr/bin/env python3
"""C156 exact two-file owner cPanel static identity inspection only.

Runs via the already pinned factory->cPanel SSH. NEVER writes, prints file
contents/digests/paths/credentials, fetches customer data, or authorizes a
payment, release, migration, backup deletion, or restoration.
"""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import stat

ROOT = Path("/home/zomorod2/mojplaywin.com/moj-prop")
MAX_BYTES = 196608
PINNED_GIT_BLOBS = {
    "home": {
        "known_current_main": "30b7fe4400f88252f3b71a581f96a796ca853b6c",
        "known_legacy_v4": "12fc38ba598c094146d16affeb6b0b86702199c9",
        "approved_plan1_source": "cba28a9592a7cee2543d2f31983ad41e2b1853f8",
    },
    "contact": {
        "known_current_main": "7f715ed5297c4682f6907475e6dcbe816b2e1e40",
        "approved_plan1_source": "3bf570b8029c513dc5fd61c87c09c0659b52903a",
    },
}
FILES = {"home": Path("index.html"), "contact": Path("contact/index.html")}


def git_blob_id(raw: bytes) -> str:
    return hashlib.sha1(
        b"blob " + str(len(raw)).encode("ascii") + b"\0" + raw
    ).hexdigest()


def classify(raw: bytes, kind: str) -> str:
    if kind not in FILES or not raw or len(raw) > MAX_BYTES:
        return "unreviewed_or_unavailable"
    git_id = git_blob_id(raw)
    for label, expected in PINNED_GIT_BLOBS[kind].items():
        if git_id == expected:
            return label
    return "unreviewed_or_unavailable"


def _safe_owner_dir(path: Path, expected_uid: int) -> bool:
    try:
        mode = path.lstat()
        return (stat.S_ISDIR(mode.st_mode)
                and not stat.S_ISLNK(mode.st_mode)
                and mode.st_uid == expected_uid
                and mode.st_mode & 0o002 == 0)
    except OSError:
        return False


def inspect_disk(root: Path = ROOT, *, expected_uid: int | None = None) -> dict:
    uid = os.geteuid() if expected_uid is None else expected_uid
    pages = {}
    read_status = {}
    # Diagnostic classifications are from a closed list and disclose no
    # filenames, hashes, bytes or identifiers. Failure is never readiness.
    safe_root = (root.is_absolute()
                 and _safe_owner_dir(root, uid)
                 and not root.parent.is_symlink())
    for kind, relative in FILES.items():
        state = "unreviewed_or_unavailable"
        file = root / relative
        parent = file.parent
        if not safe_root:
            reason = "blocked_unsafe_root"
        elif not _safe_owner_dir(parent, uid):
            reason = "blocked_unsafe_parent"
        else:
            reason = "blocked_unreadable_or_race"
            try:
                before = file.lstat()
                if (stat.S_ISREG(before.st_mode)
                        and not stat.S_ISLNK(before.st_mode)
                        and before.st_uid == uid
                        and before.st_nlink == 1
                        and before.st_mode & 0o022 == 0
                        and 0 < before.st_size <= MAX_BYTES):
                    fd = os.open(file, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
                    try:
                        after = os.fstat(fd)
                        if ((after.st_ino, after.st_dev, after.st_size)
                                != (before.st_ino, before.st_dev, before.st_size)):
                            raise OSError("source replaced during read")
                        with os.fdopen(fd, "rb", closefd=False) as source:
                            raw = source.read(MAX_BYTES + 1)
                        final = os.fstat(fd)
                        if ((final.st_size, final.st_mtime_ns, final.st_ino)
                                != (before.st_size, before.st_mtime_ns, before.st_ino)):
                            raise OSError("source mutated during read")
                        state = classify(raw, kind)
                        reason = ("read_known_source" if
                                  state != "unreviewed_or_unavailable"
                                  else "read_unreviewed_source")
                    finally:
                        os.close(fd)
                else:
                    reason = "blocked_unsafe_file_metadata"
            except FileNotFoundError:
                reason = "missing_file"
            except (OSError, PermissionError, ValueError):
                reason = "blocked_unreadable_or_race"
        pages[kind] = state
        read_status[kind] = reason
    return {
        "schema": "mojprop.cpanel.static.exact_source.readonly.c156.v2",
        "pages": pages,
        "read_status": read_status,
        "both_disk_files_reviewed_exact": all(
            state != "unreviewed_or_unavailable"
            for state in pages.values()),
        "no_file_content_hash_or_path_logged": True,
        "read_only": True,
        "customer_records_accessed": False,
        "database_or_media_read": False,
        "database_backup_or_restore_performed": False,
        "release_authorized": False,
        "payment_or_email_sent": False,
    }


if __name__ == "__main__":
    print("MOJPROP_C156_CPANEL_STATIC_SOURCE_READONLY=" +
          json.dumps(inspect_disk(), sort_keys=True, separators=(",", ":")))
