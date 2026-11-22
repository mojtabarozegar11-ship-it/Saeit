#!/usr/bin/env python3
"""Read-only inventory of VPS factory SQLite backup candidates.

This tool can never delete, rename, compress or modify a backup. Its output is
an audit, NOT authorization to run the disabled retention workflow.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import stat
import time
from pathlib import Path

DEFAULT_ROOT = Path("/home/githubops/factory-runtime/operations/backups")
EXACT_SNAPSHOT = re.compile(r"master-before-[0-9]{8}T[0-9]{6}Z\.sqlite3")
SQLITE_MAGIC = b"SQLite format 3\x00"
MAX_WALK_FILES = 30_000
MAX_DEPTH = 8
MAX_CHECK_SECONDS = 75
# Budget applies across all SQLite snapshots, not once per multi-GB file.
MAX_TOTAL_VERIFICATION_SECONDS = 240


# This standalone child is deliberately fed a constant script, not any backup data.
# It works when the audit itself is streamed to VPS via `python3 -` over SSH.
SQLITE_CHILD_CHECK = """
import sqlite3
import sys
from urllib.parse import quote
path = sys.argv[1]
uri = "file:" + quote(path, safe="/") + "?mode=ro&immutable=1"
conn = sqlite3.connect(uri, uri=True, timeout=5)
try:
    conn.execute("PRAGMA query_only=ON")
    row = conn.execute("PRAGMA quick_check").fetchone()
    print("ok" if row and row[0] == "ok" else "not_ok", flush=True)
finally:
    conn.close()
"""


def check_database(path: Path, seconds: int = MAX_CHECK_SECONDS) -> tuple[bool, str]:
    try:
        with path.open("rb") as stream:
            if stream.read(16) != SQLITE_MAGIC:
                return False, "not_sqlite_header"
        # Never open a snapshot with WAL/journal sidecars in immutable mode.
        if any(os.path.lexists(str(path) + suffix)
               for suffix in ("-wal", "-shm", "-journal")):
            return False, "sqlite_sidecar_present"
        if seconds <= 0:
            return False, "quick_check_timed_out"
        # Run slow disk I/O in an independent process so the parent can impose
        # a wall-clock deadline even if SQLite's progress callback cannot fire.
        try:
            result = subprocess.run(
                [sys.executable, "-B", "-c", SQLITE_CHILD_CHECK,
                 str(path.absolute())],
                capture_output=True,
                text=True,
                check=False,
                timeout=float(seconds),
            )
        except subprocess.TimeoutExpired:
            return False, "quick_check_timed_out"
        if result.returncode != 0:
            return False, "DatabaseError"
        if result.stdout.strip() == "ok":
            return True, "quick_check_ok"
        if result.stdout.strip() == "not_ok":
            return False, "quick_check_failed"
        return False, "unexpected_check_output"
    except OSError as exc:
        return False, type(exc).__name__


def audit(root: Path) -> dict:
    root = Path(root)
    if root.is_symlink() or not root.is_dir():
        raise ValueError("BACKUP_ROOT_MISSING_OR_UNSAFE")
    base = root.resolve(strict=True)
    device = os.lstat(base).st_dev
    seen = 0
    records_with_mtime = []
    for directory, folders, files in os.walk(base, topdown=True, followlinks=False):
        here = Path(directory)
        depth = len(here.relative_to(base).parts)
        if depth > MAX_DEPTH:
            raise ValueError("BACKUP_TREE_TOO_DEEP")
        folders[:] = sorted(
            name for name in folders
            if not (here / name).is_symlink()
            and os.lstat(here / name).st_dev == device
        )
        for name in sorted(files):
            seen += 1
            if seen > MAX_WALK_FILES:
                raise ValueError("BACKUP_TREE_LIMIT_EXCEEDED")
            if not name.endswith(".sqlite3"):
                continue
            path = here / name
            pre = os.lstat(path)
            if not stat.S_ISREG(pre.st_mode) or pre.st_dev != device:
                continue
            # Collect metadata first: newest snapshots must not wait behind older files.
            records_with_mtime.append((
                pre.st_mtime_ns, path.relative_to(base).as_posix(), path, pre
            ))
    records_with_mtime.sort(key=lambda item: (-item[0], item[1]))
    budget_started = time.monotonic()
    skipped_budget_count = 0
    records = []
    for _, relative, path, pre in records_with_mtime:
        started = time.monotonic()
        remaining = MAX_TOTAL_VERIFICATION_SECONDS - (started - budget_started)
        # Recheck the identity before reading, preserving fail-closed semantics.
        current = os.lstat(path)
        unchanged_before_check = (
            stat.S_ISREG(current.st_mode)
            and pre.st_dev == current.st_dev and pre.st_ino == current.st_ino
            and pre.st_size == current.st_size
            and pre.st_mtime_ns == current.st_mtime_ns
            and pre.st_nlink == current.st_nlink
        )
        if not unchanged_before_check:
            verified, check = False, "changed_before_verification"
        elif pre.st_nlink != 1:
            verified, check = False, "hardlinked"
        elif remaining <= 1:
            verified, check = False, "global_verification_budget_exhausted"
            skipped_budget_count += 1
        else:
            verified, check = check_database(
                path, seconds=min(MAX_CHECK_SECONDS, remaining)
            )
        check_elapsed_seconds = round(time.monotonic() - started, 2)
        post = os.lstat(path)
        stable = (
            unchanged_before_check
            and pre.st_dev == post.st_dev and pre.st_ino == post.st_ino
            and pre.st_size == post.st_size and pre.st_mtime_ns == post.st_mtime_ns
            and pre.st_nlink == post.st_nlink
        )
        records.append({
            "path_relative": relative,
            "bytes": pre.st_size,
            "age_days": round(max(0, time.time() - pre.st_mtime) / 86400, 2),
            "links": pre.st_nlink,
            "exact_master_before_name": path.parent == base and bool(
                EXACT_SNAPSHOT.fullmatch(path.name)
            ),
            "stable_during_audit": stable,
            "quick_check_ok": verified and stable,
            "check_result": check if stable else "changed_during_audit",
            "check_elapsed_seconds": check_elapsed_seconds,
            "approved_for_deletion": False,
        })
    verified_master = [r for r in records if (
        r["exact_master_before_name"] and r["quick_check_ok"]
    )]
    keep = [r["path_relative"] for r in verified_master[:2]]
    return {
        "schema": "factory.vps.sqlite.backup.audit.v1",
        "observed_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "backup_root": str(base),
        "read_only": True,
        "files_changed_or_deleted": 0,
        "factory_hold_preserved": True,
        "offsite_functional_restore_verified": False,
        "active_references_verified": False,
        "deletion_gate": "BLOCKED_PENDING_OFFSITE_RESTORE_AND_SEPARATE_APPROVAL",
        "verification_budget_seconds": MAX_TOTAL_VERIFICATION_SECONDS,
        "verification_skipped_budget_count": skipped_budget_count,
        "files_scanned": seen,
        "sqlite_count": len(records),
        "sqlite_total_bytes": sum(r["bytes"] for r in records),
        "verified_exact_master_count": len(verified_master),
        "keep_newest_two_verified_master_paths": keep,
        "records": records,
    }


def public_report(report: dict) -> dict:
    """Redact private directory and backup paths in public Actions logs."""
    out = dict(report)
    root = report.get("backup_root", "")
    out["backup_root"] = "(redacted-fixed-root)"
    out["backup_root_sha256_prefix"] = hashlib.sha256(
        root.encode("utf-8")
    ).hexdigest()[:16]
    out["records"] = []
    for row in report["records"]:
        entry = {key: value for key, value in row.items() if key != "path_relative"}
        entry["path_sha256_prefix"] = hashlib.sha256(
            row["path_relative"].encode("utf-8")
        ).hexdigest()[:16]
        entry["filename"] = (
            Path(row["path_relative"]).name
            if row["exact_master_before_name"] else "(redacted)"
        )
        out["records"].append(entry)
    out["keep_newest_two_verified_master_paths"] = [
        Path(name).name for name in report["keep_newest_two_verified_master_paths"]
    ]
    return out



# This second inventory covers operational archives and disposable-looking files.
# It deliberately excludes the active factory's private DB and cannot delete data.
FACTORY_OPERATIONS_ROOT = Path("/home/githubops/factory-runtime/operations")
ARCHIVE_SCAN_MAX_FILES = 50_000
ARCHIVE_SCAN_MAX_SECONDS = 50
ARCHIVE_SCAN_MAX_DEPTH = 10
ARCHIVE_SUFFIXES = {".sqlite3", ".gz", ".log", ".json", ".zip", ".tar",
                    ".tgz", ".tmp", ".bak", ".db", ".sqlite", ".old"}


def inventory_factory_operations(root: Path = FACTORY_OPERATIONS_ROOT) -> dict:
    root = Path(root)
    if not root.exists():
        return {"schema": "factory.vps.operations.inventory.v1",
                "root_present": False, "read_only": True,
                "files_changed_or_deleted": 0}
    if root.is_symlink() or not root.is_dir():
        raise ValueError("FACTORY_OPERATIONS_ROOT_UNSAFE")
    base = root.resolve(strict=True)
    device = os.lstat(base).st_dev
    areas: dict[str, dict] = {}
    extensions: dict[str, dict] = {}
    largest: list[dict] = []
    scanned = 0
    skipped = 0
    symlinks = 0
    started = time.monotonic()
    truncated = False
    for directory, folders, files in os.walk(base, topdown=True, followlinks=False):
        here = Path(directory)
        depth = len(here.relative_to(base).parts)
        if depth > ARCHIVE_SCAN_MAX_DEPTH or time.monotonic() - started > ARCHIVE_SCAN_MAX_SECONDS:
            truncated = True
            break
        safe_folders = []
        for name in sorted(folders):
            if time.monotonic() - started > ARCHIVE_SCAN_MAX_SECONDS:
                truncated = True
                break
            try:
                info = os.lstat(here / name)
                if stat.S_ISLNK(info.st_mode):
                    symlinks += 1
                elif stat.S_ISDIR(info.st_mode) and info.st_dev == device:
                    safe_folders.append(name)
                else:
                    skipped += 1
            except OSError:
                skipped += 1
        folders[:] = safe_folders
        if truncated:
            break
        for name in sorted(files):
            if (scanned >= ARCHIVE_SCAN_MAX_FILES or
                    time.monotonic() - started > ARCHIVE_SCAN_MAX_SECONDS):
                truncated = True
                break
            try:
                path = here / name
                info = os.lstat(path)
                if stat.S_ISLNK(info.st_mode):
                    symlinks += 1
                    continue
                if not stat.S_ISREG(info.st_mode) or info.st_dev != device:
                    skipped += 1
                    continue
                scanned += 1
                relative = path.relative_to(base)
                first = relative.parts[0] if len(relative.parts) > 1 else "(top)"
                area = first if first in {"backups", "archive", "archives",
                                          "logs", "cache", "tmp"} else "other"
                suffix = path.suffix.lower()
                ext = suffix if suffix in ARCHIVE_SUFFIXES else "other"
                for collection, key in ((areas, area), (extensions, ext)):
                    bucket = collection.setdefault(key, {"files": 0, "bytes": 0})
                    bucket["files"] += 1
                    bucket["bytes"] += info.st_size
                if ext != ".sqlite3" and info.st_size >= 1_000_000:
                    largest.append({
                        "path_sha256_prefix": hashlib.sha256(
                            relative.as_posix().encode("utf-8")
                        ).hexdigest()[:16],
                        "area": area, "extension": ext,
                        "bytes": info.st_size,
                        "age_days": round(max(0, time.time() - info.st_mtime) / 86400, 2),
                        "links": info.st_nlink,
                        "potential_delete": False,
                    })
                    largest.sort(key=lambda item: -item["bytes"])
                    del largest[15:]
            except OSError:
                skipped += 1
        if truncated:
            break
    return {
        "schema": "factory.vps.operations.inventory.v1",
        "root_present": True, "read_only": True,
        "files_changed_or_deleted": 0,
        "offsite_functional_restore_verified": False,
        "deletion_gate": "BLOCKED_PENDING_EVIDENCE",
        "files_scanned": scanned, "entries_skipped": skipped,
        "symlinks_skipped": symlinks, "scan_truncated": truncated,
        "bytes_total": sum(item["bytes"] for item in areas.values()),
        "by_area": areas, "by_extension": extensions,
        "largest_non_sqlite": largest,
    }



# Finished product packages are saleable inventory, never cleanup candidates.
# Keep this scan independent of operational backup/log scans.
FACTORY_FINISHED_ROOT = Path(
    "/home/githubops/factory-runtime/private/autonomous-product-cycle/"
    "production-warehouse/finished"
)
FINISHED_MAX_FILES = 20_000
FINISHED_MAX_SECONDS = 20
FINISHED_MAX_DEPTH = 8


def inventory_factory_finished(root: Path = FACTORY_FINISHED_ROOT) -> dict:
    root = Path(root)
    report = {
        "schema": "factory.vps.finished.products.inventory.v1",
        "read_only": True, "files_changed_or_deleted": 0,
        "protected_saleable_inventory": True,
        "deletion_allowed": False,
    }
    if not root.exists():
        return dict(report, root_present=False)
    if root.is_symlink() or not root.is_dir():
        raise ValueError("FACTORY_FINISHED_ROOT_UNSAFE")
    base = root.resolve(strict=True)
    device = os.lstat(base).st_dev
    started = time.monotonic()
    files_scanned = 0
    zip_count = 0
    zip_bytes = 0
    zip_headers_ok = 0
    other_bytes = 0
    symlinks_skipped = 0
    entries_skipped = 0
    truncated = False
    largest = []
    for directory, folders, files in os.walk(base, topdown=True, followlinks=False):
        here = Path(directory)
        if (len(here.relative_to(base).parts) > FINISHED_MAX_DEPTH
                or time.monotonic() - started >= FINISHED_MAX_SECONDS):
            truncated = True
            break
        safe_folders = []
        for name in sorted(folders):
            if time.monotonic() - started >= FINISHED_MAX_SECONDS:
                truncated = True
                break
            try:
                info = os.lstat(here / name)
                if stat.S_ISLNK(info.st_mode):
                    symlinks_skipped += 1
                elif stat.S_ISDIR(info.st_mode) and info.st_dev == device:
                    safe_folders.append(name)
                else:
                    entries_skipped += 1
            except OSError:
                entries_skipped += 1
        folders[:] = safe_folders
        if truncated:
            break
        for name in sorted(files):
            if (files_scanned >= FINISHED_MAX_FILES
                    or time.monotonic() - started >= FINISHED_MAX_SECONDS):
                truncated = True
                break
            try:
                path = here / name
                info = os.lstat(path)
                if stat.S_ISLNK(info.st_mode):
                    symlinks_skipped += 1
                    continue
                if not stat.S_ISREG(info.st_mode) or info.st_dev != device:
                    entries_skipped += 1
                    continue
                files_scanned += 1
                if name == "product.zip":
                    zip_count += 1
                    zip_bytes += info.st_size
                    # ZIP signature only; NOT a full package integrity check.
                    with path.open("rb") as stream:
                        if stream.read(4) in (b"PK\x03\x04", b"PK\x05\x06"):
                            zip_headers_ok += 1
                    relative = path.relative_to(base).as_posix()
                    largest.append({
                        "relative_sha256_prefix": hashlib.sha256(
                            relative.encode("utf-8")
                        ).hexdigest()[:16],
                        "bytes": info.st_size,
                        "age_days": round(max(0, time.time() - info.st_mtime) / 86400, 2),
                        "protected": True,
                    })
                    largest.sort(key=lambda row: -row["bytes"])
                    del largest[10:]
                else:
                    other_bytes += info.st_size
            except OSError:
                entries_skipped += 1
        if truncated:
            break
    return dict(report, root_present=True, files_scanned=files_scanned,
                product_zip_count=zip_count, product_zip_bytes=zip_bytes,
                product_zip_headers_ok=zip_headers_ok,
                full_zip_integrity_verified=False,
                other_files_bytes=other_bytes,
                bytes_observed=zip_bytes + other_bytes,
                entries_skipped=entries_skipped,
                symlinks_skipped=symlinks_skipped,
                scan_truncated=truncated,
                largest_protected_packages=largest)



# Optional content-identity pass. Distinct from SQLite quick_check: this proves
# exact byte equivalence without classifying any copy as safe for deletion.
HASH_SCAN_SECONDS = 180
HASH_READ_CHUNK = 1024 * 1024


def backup_hash_identity(root: Path, seconds: float = HASH_SCAN_SECONDS) -> dict:
    root = Path(root)
    if root.is_symlink() or not root.is_dir():
        raise ValueError("BACKUP_HASH_ROOT_UNSAFE")
    base = root.resolve(strict=True)
    device = os.lstat(base).st_dev
    paths = []
    seen = 0
    for directory, folders, files in os.walk(base, topdown=True, followlinks=False):
        here = Path(directory)
        if len(here.relative_to(base).parts) > MAX_DEPTH:
            raise ValueError("BACKUP_HASH_TREE_TOO_DEEP")
        folders[:] = sorted(
            name for name in folders
            if not (here / name).is_symlink()
            and os.lstat(here / name).st_dev == device
        )
        for name in sorted(files):
            seen += 1
            if seen > MAX_WALK_FILES:
                raise ValueError("BACKUP_HASH_TREE_LIMIT_EXCEEDED")
            path = here / name
            info = os.lstat(path)
            if (name.endswith(".sqlite3") and stat.S_ISREG(info.st_mode)
                    and info.st_dev == device and info.st_nlink == 1):
                paths.append((info.st_mtime_ns, path))
    paths.sort(reverse=True)
    started = time.monotonic()
    groups = {}
    observations = []
    for _, path in paths:
        relative = path.relative_to(base).as_posix()
        entry = {
            "path_sha256_prefix": hashlib.sha256(relative.encode()).hexdigest()[:16],
            "filename": path.name if path.parent == base and
                        EXACT_SNAPSHOT.fullmatch(path.name) else "(redacted)",
            "sha256": None,
            "hash_status": "not_checked",
            "bytes": None,
        }
        if time.monotonic() - started >= seconds:
            entry["hash_status"] = "global_hash_budget_exhausted"
            observations.append(entry)
            continue
        fd = None
        try:
            fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
            before = os.fstat(fd)
            digest = hashlib.sha256()
            completed = False
            while time.monotonic() - started < seconds:
                block = os.read(fd, HASH_READ_CHUNK)
                if not block:
                    completed = True
                    break
                digest.update(block)
            after = os.fstat(fd)
            current = os.lstat(path)
            keys = ("st_dev", "st_ino", "st_size", "st_mtime_ns", "st_ctime_ns", "st_nlink")
            stable = (completed and stat.S_ISREG(before.st_mode)
                      and before.st_nlink == 1
                      and all(getattr(before, key) == getattr(after, key) ==
                              getattr(current, key) for key in keys))
            entry["bytes"] = before.st_size
            if stable:
                key = digest.hexdigest()
                entry["sha256"] = key
                entry["hash_status"] = "stable_full_sha256"
                groups.setdefault(key, []).append(entry)
            else:
                entry["hash_status"] = (
                    "global_hash_budget_exhausted" if not completed
                    else "changed_during_hash"
                )
        except OSError as exc:
            entry["hash_status"] = type(exc).__name__
        finally:
            if fd is not None:
                os.close(fd)
        observations.append(entry)
    same_content = [
        {
            "sha256": key,
            "bytes_each": values[0]["bytes"],
            "members": [{"path_sha256_prefix": item["path_sha256_prefix"],
                         "filename": item["filename"]} for item in values],
            "byte_identical_extra_bytes_not_authorized": (
                len(values) - 1) * values[0]["bytes"],
            "approved_for_deletion": False,
        }
        for key, values in sorted(groups.items()) if len(values) > 1
    ]
    return {
        "schema": "factory.vps.sqlite.hash.identity.v1",
        "read_only": True,
        "files_changed_or_deleted": 0,
        "hashed_count": sum(x["hash_status"] == "stable_full_sha256"
                            for x in observations),
        "sqlite_files_seen": len(paths),
        "full_hash_coverage": all(x["hash_status"] == "stable_full_sha256"
                                  for x in observations),
        "identical_content_groups": same_content,
        "deletion_gate": "BLOCKED_PENDING_INDEPENDENT_RESTORE_AND_OWNER_APPROVAL",
        "records": observations,
    }


def backup_snapshot_space_gate(root: Path) -> dict:
    """Estimate the reserve required before making another local DB snapshot."""
    runtime = Path(root).parent.parent
    if runtime.name != "factory-runtime" or runtime.is_symlink():
        return {"status": "not_factory_runtime_root"}
    info = os.statvfs(runtime)
    free = info.f_bavail * info.f_frsize
    reserve = max(2 * 1024**3, (info.f_blocks * info.f_frsize + 19) // 20)
    db = runtime / "django-app" / "db.sqlite3"
    try:
        db_stat = db.lstat()
    except FileNotFoundError:
        return {"status": "missing_live_db", "free_bytes": free}
    if not stat.S_ISREG(db_stat.st_mode) or stat.S_ISLNK(db_stat.st_mode):
        return {"status": "unsafe_live_db", "free_bytes": free}
    needed = reserve + db_stat.st_size
    return {
        "status": "observed",
        "free_bytes": free,
        "reserve_bytes": reserve,
        "live_database_bytes": db_stat.st_size,
        "required_before_new_snapshot_bytes": needed,
        "shortfall_bytes": max(0, needed - free),
        "safe_new_snapshot_space": free >= needed,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT,
                        help="Read-only source directory; no files are modified.")
    parser.add_argument("--hash", action="store_true",
                        help="Read full SQLite backup contents for exact SHA-256 identity.")
    args = parser.parse_args()
    result = audit(args.root)
    print("FACTORY_BACKUP_AUDIT=" + json.dumps(public_report(result), sort_keys=True))
    if args.root == DEFAULT_ROOT:
        print("FACTORY_OPERATIONS_INVENTORY=" + json.dumps(
            inventory_factory_operations(), sort_keys=True))
        print("FACTORY_FINISHED_PRODUCT_INVENTORY=" + json.dumps(
            inventory_factory_finished(), sort_keys=True))
    if args.hash:
        print("FACTORY_BACKUP_HASH_IDENTITY=" + json.dumps(
            backup_hash_identity(args.root), sort_keys=True))
    print("FACTORY_BACKUP_SNAPSHOT_SPACE_GATE=" + json.dumps(
        backup_snapshot_space_gate(args.root), sort_keys=True))
    if not result["sqlite_count"]:
        raise SystemExit("NO_SQLITE_BACKUPS_FOUND")


if __name__ == "__main__":
    main()
