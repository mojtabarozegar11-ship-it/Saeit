#!/usr/bin/env python3
"""C150: bounded read of FIXED manifest.json in owner-private Plan1 rollback dirs.

No backup file/snapshot/receipt/database content is opened, restored or copied.
Only aggregate counts of narrowly recognized source-rollback JSON contracts
are printed. A valid local manifest is NOT proof of usable backup, DB/media
restore, offhost independence or release eligibility.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import pwd
import re
import stat

OWNER = "zomorod2"
ROOT = Path("/home/zomorod2/.mojplaywin-moj-prop-backups")
CASE = re.compile(r"(?:[0-9]{8,20}|mojprop[-_][a-z0-9_-]{4,45})\Z")
SHA40 = re.compile(r"[a-f0-9]{40}\Z")
SHA64 = re.compile(r"[a-f0-9]{64}\Z")
SOURCE_PATH = re.compile(r"(?:config|core|scripts)/[A-Za-z0-9_./-]{2,150}\Z")
MAX_ENTRIES = 128
MAX_CASES = 64
MAX_BYTES = 65536


def owner_private_dir(path: Path, uid: int) -> bool:
    try:
        st = path.lstat()
    except OSError:
        return False
    return (stat.S_ISDIR(st.st_mode) and st.st_uid == uid
            and not st.st_mode & 0o022)


def unique_pairs(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError("duplicate manifest JSON key")
        value[key] = item
    return value


def read_fixed_manifest(case_dir: Path, uid: int) -> object:
    """Only fixed manifest basename in validated owned directory, O_NOFOLLOW."""
    if not owner_private_dir(case_dir, uid) or not CASE.fullmatch(case_dir.name):
        return None
    path = case_dir / "manifest.json"
    fd = None
    try:
        fd = os.open(str(path), os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
        st = os.fstat(fd)
        if (not stat.S_ISREG(st.st_mode) or st.st_uid != uid or
                st.st_mode & 0o022 or st.st_nlink != 1 or
                not 1 <= st.st_size <= MAX_BYTES):
            return None
        with os.fdopen(fd,"rb",closefd=False) as f:
            data = f.read(MAX_BYTES+1)
        if len(data) > MAX_BYTES or len(data) != st.st_size:
            return None
        return json.loads(data.decode("utf-8"),object_pairs_hook=unique_pairs)
    except (OSError, ValueError, UnicodeError, TypeError):
        return None
    finally:
        if fd is not None:
            os.close(fd)


def safe_source_path(name: object) -> bool:
    return (type(name) is str and SOURCE_PATH.fullmatch(name) is not None
            and not name.startswith("/") and ".." not in name.split("/")
            and name.endswith(".py"))


def classify_manifest(value: object, case_name: str) -> dict:
    result = {"type": "unknown", "declared_source_files": 0,
              "declared_existing_files": 0,
              "schema_migration_attempted": False}
    if type(value) is not dict or value.get("run_id") != case_name:
        return result
    files = value.get("files")
    if (type(files) is not list or not 1 <= len(files) <= 80 or
            not all(safe_source_path(name) for name in files) or
            len(set(files)) != len(files)):
        return result
    if (type(value.get("commit")) is not str or
            SHA40.fullmatch(value["commit"]) is None or
            type(value.get("schema_migration_attempted")) is not bool):
        return result
    count = 0
    for name in files:
        item = value.get(name)
        if type(item) is not dict or type(item.get("existed")) is not bool:
            return result
        if item["existed"]:
            if (type(item.get("sha256")) is not str or
                    SHA64.fullmatch(item["sha256"]) is None or
                    type(item.get("mode")) is not int or
                    not 0 <= item["mode"] <= 0o777):
                return result
            count += 1
    return {"type": "source-only-rollback",
            "declared_source_files": len(files),
            "declared_existing_files": count,
            "schema_migration_attempted": value["schema_migration_attempted"]}


def inventory(root: Path, uid: int) -> dict:
    out = {"completed": False, "owner_root_verified": False,
           "case_directories_checked": 0, "manifest_read_attempts": 0,
           "source_only_rollback_manifests": 0,
           "unknown_or_invalid_manifest_shapes": 0,
           "source_files_declared_total": 0,
           "source_existing_files_declared_total": 0,
           "manifests_marking_migration_attempted": 0,
           "read_any_database_or_media": False,
           "read_any_backup_saved_file": False,
           "independent_restore_verified": False,
           "tenant_rollback_authorized": False}
    if not owner_private_dir(root, uid):
        return out
    out["owner_root_verified"] = True
    cases = 0
    attempts = 0
    accepted = 0
    bad = 0
    declared = 0
    existing = 0
    attempted = 0
    count = 0
    try:
        with os.scandir(root) as entries:
            for entry in entries:
                count += 1
                if count > MAX_ENTRIES:
                    return out
                if not CASE.fullmatch(entry.name):
                    continue
                try:
                    st = entry.stat(follow_symlinks=False)
                except OSError:
                    continue
                if not stat.S_ISDIR(st.st_mode) or st.st_uid != uid or st.st_mode & 0o022:
                    continue
                cases += 1
                if cases > MAX_CASES:
                    return out
                attempts += 1
                parsed = read_fixed_manifest(root / entry.name, uid)
                view = classify_manifest(parsed, entry.name)
                if view["type"] != "source-only-rollback":
                    bad += 1
                else:
                    accepted += 1
                    declared += view["declared_source_files"]
                    existing += view["declared_existing_files"]
                    attempted += int(view["schema_migration_attempted"])
    except OSError:
        return out
    out.update(completed=True, case_directories_checked=cases,
               manifest_read_attempts=attempts,
               source_only_rollback_manifests=accepted,
               unknown_or_invalid_manifest_shapes=bad,
               source_files_declared_total=declared,
               source_existing_files_declared_total=existing,
               manifests_marking_migration_attempted=attempted)
    return out


def report() -> dict:
    out = {"schema": "mojprop.cpanel.local_rollback_manifest_shape.c150.v1",
           "owner_identity_verified": False, "read_only": True,
           "inventory": inventory(Path("/missing-root-safe-default"),-1),
           "db_snapshot_read": False, "backup_content_read": False,
           "customer_data_accessed": False,
           "independent_offhost_backup_verified": False,
           "app_db_media_restore_proven": False,
           "payment_collected": False, "production_release_authorized": False,
           "cost_incurred": False}
    try:
        if pwd.getpwuid(os.geteuid()).pw_name != OWNER:
            return out
        out["owner_identity_verified"] = True
        out["inventory"] = inventory(ROOT, os.geteuid())
    except (OSError, KeyError, ValueError):
        pass
    return out


if __name__ == "__main__":
    print("MOJPROP_C150_ROLLBACK_MANIFEST_SHAPE_READONLY=" +
          json.dumps(report(),sort_keys=True,separators=(",",":")))
