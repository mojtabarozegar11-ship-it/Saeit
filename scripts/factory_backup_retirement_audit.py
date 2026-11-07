#!/usr/bin/env python3
"""Read-only inventory for retiring legacy factory SQLite backups.

This command NEVER deletes, renames, compresses, vacuums, copies, or modifies
factory files. Identical hashes are evidence of identical bytes, NOT proof that
one copy is safe to retire: an independently restored, off-host backup and an
approved retention decision are still mandatory.

Example:
    python3 scripts/factory_backup_retirement_audit.py \
        --runtime-root /home/githubops/factory-runtime --hash
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import stat
import sys
from collections import defaultdict
from pathlib import Path

GIB = 1024**3
READ_CHUNK = 1024**2


def checked_directory(path: Path) -> None:
    info = path.lstat()
    if not stat.S_ISDIR(info.st_mode) or stat.S_ISLNK(info.st_mode):
        raise ValueError(f"Unsafe or missing directory: {path}")


def check_layout(runtime_root: Path) -> tuple[Path, Path]:
    if not runtime_root.is_absolute() or runtime_root.name != "factory-runtime":
        raise ValueError("Pass the absolute path to the factory-runtime directory")
    checked_directory(runtime_root)
    operations = runtime_root / "operations"
    backups = operations / "backups"
    checked_directory(operations)
    checked_directory(backups)
    return backups, runtime_root / "django-app" / "db.sqlite3"


def sqlite_backups(backups: Path) -> list[Path]:
    result: list[Path] = []
    for parent, dirs, names in os.walk(backups, topdown=True, followlinks=False):
        parent_path = Path(parent)
        dirs[:] = sorted(
            name
            for name in dirs
            if not (parent_path / name).is_symlink()
        )
        for name in sorted(names):
            item = parent_path / name
            if item.suffix != ".sqlite3":
                continue
            info = item.lstat()
            if stat.S_ISREG(info.st_mode) and not stat.S_ISLNK(info.st_mode):
                result.append(item)
    return result


def file_evidence(path: Path, read_hash: bool) -> dict:
    flags = os.O_RDONLY
    for name in ("O_CLOEXEC", "O_NOFOLLOW", "O_NONBLOCK"):
        flags |= getattr(os, name, 0)
    fd = os.open(path, flags)
    try:
        before = os.fstat(fd)
        if not stat.S_ISREG(before.st_mode):
            raise ValueError(f"Non-regular backup file: {path}")
        digest = hashlib.sha256() if read_hash else None
        if digest is not None:
            with os.fdopen(os.dup(fd), "rb", buffering=0) as handle:
                while block := handle.read(READ_CHUNK):
                    digest.update(block)
        after = os.fstat(fd)
        current = path.lstat()
        identity = ("st_dev", "st_ino", "st_size", "st_mtime_ns", "st_ctime_ns")
        if any(getattr(before, key) != getattr(after, key) or
               getattr(before, key) != getattr(current, key) for key in identity):
            raise RuntimeError(f"Backup changed during scan: {path}")
        return {
            "bytes": before.st_size,
            "mtime_ns": before.st_mtime_ns,
            "sha256": digest.hexdigest() if digest is not None else None,
            "hash_verified_stable": digest is not None,
        }
    finally:
        os.close(fd)


def space_gate(runtime_root: Path, live_db: Path) -> dict:
    info = os.statvfs(runtime_root)
    free_bytes = info.f_bavail * info.f_frsize
    minimum_reserve = max(2 * GIB, (info.f_blocks * info.f_frsize + 19) // 20)
    live_db_bytes = 0
    live_db_status = "missing"
    try:
        db_info = live_db.lstat()
        if stat.S_ISREG(db_info.st_mode) and not stat.S_ISLNK(db_info.st_mode):
            live_db_bytes = db_info.st_size
            live_db_status = "present"
        else:
            live_db_status = "unsafe"
    except FileNotFoundError:
        pass
    required_free = minimum_reserve + live_db_bytes
    return {
        "free_bytes": free_bytes,
        "minimum_reserve_bytes": minimum_reserve,
        "live_db_bytes": live_db_bytes,
        "live_db_status": live_db_status,
        "required_free_before_new_local_snapshot_bytes": required_free,
        "shortfall_bytes": max(0, required_free - free_bytes),
        "new_snapshot_space_gate_met": (
            live_db_status == "present" and free_bytes >= required_free
        ),
    }


def audit(runtime_root: Path, hash_files: bool) -> dict:
    backups, live_db = check_layout(runtime_root)
    items: list[dict] = []
    for path in sqlite_backups(backups):
        details = file_evidence(path, hash_files)
        details["relative_path"] = path.relative_to(runtime_root).as_posix()
        items.append(details)
    same_size: dict[int, list[str]] = defaultdict(list)
    exact: dict[str, list[str]] = defaultdict(list)
    for item in items:
        same_size[item["bytes"]].append(item["relative_path"])
        if item["sha256"] is not None:
            exact[item["sha256"]].append(item["relative_path"])
    return {
        "schema": "factory-backup-retirement-audit/v1",
        "read_only": True,
        "deletion_performed": False,
        "copies_recoverable_off_host_verified": False,
        "automatic_deletion_authorized": False,
        "policy": "Exact duplicates are investigation candidates, never automatic deletions.",
        "runtime_root": str(runtime_root),
        "disk": space_gate(runtime_root, live_db),
        "sqlite_backup_count": len(items),
        "sqlite_backup_bytes": sum(x["bytes"] for x in items),
        "sha256_complete": hash_files,
        "same_size_groups": [members for members in same_size.values() if len(members) > 1],
        "identical_content_groups": [
            members for members in exact.values() if len(members) > 1
        ] if hash_files else None,
        "verified_safe_deletion_paths": [],
        "files": items,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime-root", type=Path, required=True)
    parser.add_argument(
        "--hash", action="store_true",
        help="Read full backup contents to verify SHA-256 equivalence (potentially 10+ GiB).",
    )
    args = parser.parse_args()
    try:
        result = audit(args.runtime_root, args.hash)
    except (OSError, RuntimeError, ValueError) as exc:
        print(f"FACTORY_RETIREMENT_AUDIT_ABORT={type(exc).__name__}:{exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
