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
        for name in sorted(files):
            if scanned >= ARCHIVE_SCAN_MAX_FILES:
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


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT,
                        help="Read-only source directory; no files are modified.")
    args = parser.parse_args()
    result = audit(args.root)
    print("FACTORY_BACKUP_AUDIT=" + json.dumps(public_report(result), sort_keys=True))
    if args.root == DEFAULT_ROOT:
        print("FACTORY_OPERATIONS_INVENTORY=" + json.dumps(
            inventory_factory_operations(), sort_keys=True))
    if not result["sqlite_count"]:
        raise SystemExit("NO_SQLITE_BACKUPS_FOUND")


if __name__ == "__main__":
    main()
