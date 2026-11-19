"""Read-only provenance metadata for the two fixed backup candidates.

No file contents are read. No decompression, extraction, temporary file,
write, delete, transfer, restart or deployment occurs.
"""
from __future__ import annotations
import datetime as dt
import hashlib
import json
import os
import stat
import time
from pathlib import Path

HOME = Path("/home/zomorod2")
RAW_ROOT = HOME / "Saeit-staging" / "backups"
RAW_ID = "631f2edc066491c2"
RAW_SIZE = 17901606016
RAW_MTIME = 1795033731
SECOND_GROUP = "012feef8bce02780"
SECOND_ID = "a0527a9d8e6018a2"
SECOND_SIZE = 2314043690
SECOND_MTIME = 1795077682
MAX_ENTRIES = 60000
MAX_SECONDS = 75


def token(value):
    return hashlib.sha256(os.fsencode(str(value))).hexdigest()[:16]


def ident(s):
    return (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns)


def iso(seconds):
    return dt.datetime.fromtimestamp(seconds, dt.timezone.utc).isoformat()


def locate(root, wanted, size, mtime, deadline):
    root = Path(root)
    if not root.is_dir() or root.is_symlink():
        return None
    stack = [root]
    seen = 0
    while stack and time.monotonic() < deadline and seen < MAX_ENTRIES:
        parent = stack.pop()
        try:
            with os.scandir(parent) as entries:
                for entry in entries:
                    seen += 1
                    if seen > MAX_ENTRIES or time.monotonic() >= deadline:
                        return None
                    s = entry.stat(follow_symlinks=False)
                    if stat.S_ISLNK(s.st_mode):
                        continue
                    p = Path(entry.path)
                    if stat.S_ISDIR(s.st_mode):
                        if s.st_uid == os.geteuid() and s.st_dev == root.stat().st_dev:
                            stack.append(p)
                    elif (stat.S_ISREG(s.st_mode) and s.st_size == size
                          and int(s.st_mtime) == mtime
                          and token(p.relative_to(HOME)) == wanted):
                        return p, s
        except OSError:
            return None
    return None


def parent_summary(parent):
    s = parent.stat()
    result = {
        "parent_token": token(parent.relative_to(HOME)),
        "parent_device": token(s.st_dev),
        "parent_inode": token(s.st_ino),
        "parent_mode": oct(stat.S_IMODE(s.st_mode)),
        "parent_owner_matches_process": s.st_uid == os.geteuid(),
        "parent_mtime": int(s.st_mtime),
        "parent_ctime": int(s.st_ctime),
        "parent_mtime_utc": iso(s.st_mtime),
        "parent_ctime_utc": iso(s.st_ctime),
        "entry_scan_complete": True,
        "regular_entries": 0,
        "directory_entries": 0,
        "symlink_entries": 0,
        "logical_bytes": 0,
    }
    count = 0
    try:
        with os.scandir(parent) as entries:
            for entry in entries:
                count += 1
                if count > 10000:
                    result["entry_scan_complete"] = False
                    break
                e = entry.stat(follow_symlinks=False)
                if stat.S_ISLNK(e.st_mode):
                    result["symlink_entries"] += 1
                elif stat.S_ISDIR(e.st_mode):
                    result["directory_entries"] += 1
                elif stat.S_ISREG(e.st_mode):
                    result["regular_entries"] += 1
                    result["logical_bytes"] += e.st_size
    except OSError:
        result["entry_scan_complete"] = False
    return result


def file_summary(path, expected, location_class):
    before = path.stat()
    result = {
        "location_class": location_class,
        "path_token": token(path.relative_to(HOME)),
        "device": token(before.st_dev),
        "inode": token(before.st_ino),
        "mode": oct(stat.S_IMODE(before.st_mode)),
        "owner_matches_process": before.st_uid == os.geteuid(),
        "regular_file": stat.S_ISREG(before.st_mode),
        "size_bytes": before.st_size,
        "mtime": int(before.st_mtime),
        "ctime": int(before.st_ctime),
        "mtime_utc": iso(before.st_mtime),
        "ctime_utc": iso(before.st_ctime),
        "expected_identity_matches": (
            before.st_size == expected[0] and int(before.st_mtime) == expected[1]
        ),
        "parent": parent_summary(path.parent),
    }
    after = path.stat()
    result["unchanged_during_metadata_read"] = ident(before) == ident(after)
    return result


def main():
    deadline = time.monotonic() + MAX_SECONDS
    roots = [
        p for p in HOME.iterdir()
        if token(p.name) == SECOND_GROUP and not p.is_symlink() and p.is_dir()
    ]
    raw = locate(RAW_ROOT, RAW_ID, RAW_SIZE, RAW_MTIME, deadline)
    second = (
        locate(roots[0], SECOND_ID, SECOND_SIZE, SECOND_MTIME, deadline)
        if len(roots) == 1 else None
    )
    out = {
        "schema": "mpw.backup.provenance.readonly.v6",
        "read_only": True,
        "raw_identified": raw is not None,
        "second_identified": second is not None,
        "raw_content_read": False,
        "temporary_files_created": False,
        "files_deleted": False,
        "deployment_performed": False,
        "external_transfer": False,
        "restore_verified": False,
        "safe_to_delete": False,
        "metadata_only": True,
    }
    if raw is None or second is None:
        out["error_category"] = "FIXED_PAIR_NOT_IDENTIFIED"
    else:
        raw_data = file_summary(raw[0], (RAW_SIZE, RAW_MTIME), "SAEIT_STAGING_BACKUPS")
        second_data = file_summary(second[0], (SECOND_SIZE, SECOND_MTIME), "CPANEL_HOME_SEPARATE_GROUP")
        out["raw"] = raw_data
        out["second"] = second_data
        out["same_device"] = raw_data["device"] == second_data["device"]
        out["same_parent"] = (
            raw_data["parent"]["parent_device"] == second_data["parent"]["parent_device"]
            and raw_data["parent"]["parent_inode"] == second_data["parent"]["parent_inode"]
        )
        out["mtime_delta_seconds_second_minus_raw"] = (
            second_data["mtime"] - raw_data["mtime"]
        )
        out["ctime_delta_seconds_second_minus_raw"] = (
            second_data["ctime"] - raw_data["ctime"]
        )
        out["error_category"] = "NONE"
    print("MPW_BACKUP_PROVENANCE_READONLY=" + json.dumps(out, sort_keys=True))


if __name__ == "__main__":
    main()
