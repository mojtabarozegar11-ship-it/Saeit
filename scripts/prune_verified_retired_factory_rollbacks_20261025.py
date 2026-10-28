#!/usr/bin/env python3
"""Prune only three SHA-verified retired SQLite rollback *archives*.

A fail-closed retention gate requires three newer independently healthy,
uncompressed restore points. Never touch live DB, orders, sites or other backups.
"""
from __future__ import annotations

import argparse
import datetime as dt
import fcntl
import gzip
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sqlite3
import stat
import subprocess
import tempfile
import time
from urllib.parse import quote

OPS = Path("/home/githubops/factory-runtime/operations")
ROOT = OPS / "backups"
TARGETS = (
    "native-master-20261022T042604Z-2134354",
    "native-master-20261022T043500Z-2141700",
    "native-master-20261022T082246Z-2190240",
)
ARCHIVE_NAME = "sqlite-before.sqlite3.gz"
RECEIPT_NAME = "sqlite-backup-lossless-archive-20261025.json"
PRUNE_PROOF = "sqlite-backup-pruned-20261025.json"

def hashed(path: Path) -> tuple[str, int]:
    digest = hashlib.sha256()
    total = 0
    with path.open("rb") as stream:
        for buf in iter(lambda: stream.read(1024 * 1024 * 4), b""):
            digest.update(buf)
            total += len(buf)
    return digest.hexdigest(), total

def verify_newer() -> list[str]:
    newer = sorted(
        (p for p in ROOT.glob("native-master-20261022*")
         if p.is_dir() and not p.is_symlink() and p.name > TARGETS[-1]
         and (p / "sqlite-before.sqlite3").is_file()
         and not (p / "sqlite-before.sqlite3").is_symlink()),
        key=lambda p: p.name, reverse=True,
    )
    if len(newer) < 3:
        raise RuntimeError("LESS_THAN_THREE_NEWER_UNCOMPRESSED_BACKUPS")
    verified = []
    for folder in newer[:3]:
        db = folder / "sqlite-before.sqlite3"
        st = db.stat()
        if not stat.S_ISREG(st.st_mode) or st.st_nlink != 1 or not 600_000_000 <= st.st_size <= 800_000_000:
            raise RuntimeError("NEWER_BACKUP_NOT_STABLE_REGULAR_SQLITE")
        if time.time() - st.st_mtime < 60:
            raise RuntimeError("NEWER_BACKUP_STILL_BEING_WRITTEN")
        uri = "file:" + quote(str(db), safe="/") + "?mode=ro&immutable=1"
        con = sqlite3.connect(uri, uri=True, timeout=10)
        try:
            con.execute("PRAGMA query_only=ON")
            value = con.execute("PRAGMA quick_check(1)").fetchone()
            if not value or value[0] != "ok":
                raise RuntimeError("NEWER_RESTORE_POINT_INTEGRITY_FAILED")
        finally:
            con.close()
        st2 = db.stat()
        if st2.st_ino != st.st_ino or st2.st_size != st.st_size or st2.st_mtime_ns != st.st_mtime_ns:
            raise RuntimeError("NEWER_RESTORE_POINT_CHANGED")
        verified.append(folder.name)
        print("NEWER_BACKUP_INTEGRITY_OK=" + str(len(verified)), flush=True)
    return verified

def candidates() -> list[dict]:
    if os.geteuid() == 0 or os.getenv("USER") != "githubops":
        raise RuntimeError("NOT_NONROOT_GITHUBOPS")
    for p in (OPS, ROOT):
        if not p.is_dir() or p.is_symlink():
            raise RuntimeError("UNSAFE_BACKUP_ROOT")
    cron = subprocess.run(["crontab", "-l"], capture_output=True, text=True, check=True, timeout=8).stdout
    procs = subprocess.run(["ps", "-u", "githubops", "-o", "args="], capture_output=True, text=True, check=True, timeout=8).stdout
    now = dt.datetime.now(dt.timezone.utc)
    output = []
    for name in TARGETS:
        timestamp = re.fullmatch(r"native-master-(\d{8}T\d{6}Z)-\d+", name)
        if not timestamp:
            raise RuntimeError("NOT_ALLOWLISTED_TIMESTAMP")
        born = dt.datetime.strptime(timestamp.group(1), "%Y%m%dT%H%M%SZ").replace(tzinfo=dt.timezone.utc)
        if (now - born).total_seconds() < 72 * 3600:
            raise RuntimeError("BACKUP_NOT_PAST_EXPLICIT_72H_CUTOFF")
        if name in cron or name in procs:
            raise RuntimeError("ACTIVE_BACKUP_REFERENCE")
        folder = ROOT / name
        archive = folder / ARCHIVE_NAME
        proof = folder / RECEIPT_NAME
        pruned = folder / PRUNE_PROOF
        if folder.is_symlink() or not folder.is_dir() or archive.is_symlink() or not archive.is_file():
            raise RuntimeError("ARCHIVE_PATH_MISSING_OR_UNSAFE")
        if proof.is_symlink() or not proof.is_file() or pruned.exists() or pruned.is_symlink():
            raise RuntimeError("ARCHIVE_ORIGINAL_PROOF_MISSING_OR_ALREADY_PRUNED")
        if (folder / "sqlite-before.sqlite3").exists():
            raise RuntimeError("RAW_DUPLICATE_STILL_PRESENT")
        st = archive.stat()
        if not stat.S_ISREG(st.st_mode) or st.st_nlink != 1 or not 95_000_000 <= st.st_size <= 125_000_000:
            raise RuntimeError("ARCHIVE_SIZE_OR_LINK_UNEXPECTED")
        receipt = json.loads(proof.read_text())
        if receipt.get("schema") != "saeit.factory.backup.lossless-archive.v1" or receipt.get("archive_file") != ARCHIVE_NAME:
            raise RuntimeError("UNTRUSTED_ARCHIVE_RECEIPT")
        archive_sha, compressed_bytes = hashed(archive)
        if archive_sha != receipt.get("gzip_sha256") or compressed_bytes != receipt.get("compressed_bytes"):
            raise RuntimeError("ARCHIVE_HASH_MISMATCH")
        uncompressed = hashlib.sha256()
        amount = 0
        with gzip.open(archive, "rb") as stream:
            for buf in iter(lambda: stream.read(4 * 1024 * 1024), b""):
                uncompressed.update(buf)
                amount += len(buf)
        if uncompressed.hexdigest() != receipt.get("original_sha256") or amount != receipt.get("original_bytes"):
            raise RuntimeError("ARCHIVE_RESTORE_ROUNDTRIP_FAILED")
        st2 = archive.stat()
        if st2.st_ino != st.st_ino or st2.st_size != st.st_size or st2.st_mtime_ns != st.st_mtime_ns:
            raise RuntimeError("ARCHIVE_MODIFIED_DURING_VERIFICATION")
        print("RETIRED_ARCHIVE_HASH_OK=" + str(len(output) + 1), flush=True)
        output.append({"name": name, "path": archive, "sha256": archive_sha, "bytes": compressed_bytes,
                       "ino": st.st_ino, "mtime_ns": st.st_mtime_ns})
    return output

def atomic_proof(path: Path, data: dict) -> None:
    fd, temporary = tempfile.mkstemp(prefix=".prune-verified-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(data, stream, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary, 0o600)
        os.rename(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)

def main(apply: bool) -> None:
    if shutil.disk_usage(ROOT).free < 2_000_000_000:
        raise RuntimeError("BELOW_DISK_EMERGENCY_RESERVE")
    newer = verify_newer()
    items = candidates()
    planned = sum(item["bytes"] for item in items)
    print("PRUNE_PRECHECK=" + json.dumps({"mode": "APPLY" if apply else "DRY_RUN",
          "retired_candidates": len(items), "archive_bytes": planned,
          "healthy_newer_sqlite_restore_points": len(newer),
          "factory_orders_and_sites": "UNTOUCHED"}, sort_keys=True), flush=True)
    if not apply:
        return
    lock = OPS / ".rollback-snapshot-lossless-archive.lock"
    if lock.is_symlink():
        raise RuntimeError("UNSAFE_LOCK")
    with lock.open("a+b") as guard:
        fcntl.flock(guard, fcntl.LOCK_EX)
        free_before = shutil.disk_usage(ROOT).free
        for item in items:
            p = item["path"]
            st = p.lstat()
            if not stat.S_ISREG(st.st_mode) or st.st_nlink != 1 or st.st_ino != item["ino"] or st.st_mtime_ns != item["mtime_ns"] or st.st_size != item["bytes"]:
                raise RuntimeError("ARCHIVE_CHANGED_BEFORE_PRUNE")
            if hashed(p)[0] != item["sha256"]:
                raise RuntimeError("ARCHIVE_CHANGED_BEFORE_UNLINK")
            proof = p.parent / PRUNE_PROOF
            atomic_proof(proof, {"schema": "saeit.factory.backup.expired-prune.v1",
                "retired_snapshot": item["name"], "removed_archive_sha256": item["sha256"],
                "removed_archive_bytes": item["bytes"], "newer_healthy_backup_count": len(newer),
                "reason": "retired redundant after three newer independently integrity-checked SQLite backups",
                "timestamp_utc": dt.datetime.now(dt.timezone.utc).isoformat()})
            p.unlink()
            print("PRUNE_ITEM=" + json.dumps({"retired_snapshot": item["name"],
                  "pruned_bytes": item["bytes"], "newer_restore_points_preserved": len(newer)}), flush=True)
        free_after = shutil.disk_usage(ROOT).free
    print("PRUNE_RESULT=" + json.dumps({"archived_bytes_removed": planned,
         "free_bytes_before": free_before, "free_bytes_after": free_after,
         "files_deleted": len(items), "live_db_orders_sites_changed": False}, sort_keys=True), flush=True)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    try:
        main(args.apply)
    except Exception as exc:
        print("PRUNE_FAILED=" + type(exc).__name__ + ":" + str(exc)[:150], flush=True)
        raise

# Owner requested a current dry-run before retiring these verified prior-generation archives; 2026-10-28.
