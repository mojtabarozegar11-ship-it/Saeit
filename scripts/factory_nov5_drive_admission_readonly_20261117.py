#!/usr/bin/env python3
"""Bounded, read-only admission check before encrypted Nov-5 offsite transfer.

This tool streams the two immutable snapshots to SHA-256 and zlib gzip level 1
without writing any compressed data. It only reports capability booleans for
possible direct Drive transport; it never reads or prints credential contents.
"""
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import time
import zlib

ROOT = Path("/home/githubops/factory-runtime/operations/backups")
EXPECTED = (
    ("master-before-20261105T154953Z.sqlite3",
     "a9fd2175f9ace1a81d67cf7145e54b8621fd44cc06b0b2739bdc9345e21750e2"),
    ("master-before-20261105T210434Z.sqlite3",
     "402c16b67d430132701435eb4b3f79de88cd5c2479bb07c741c6674708a931be"),
)
EXPECTED_BYTES = 1_408_634_880
BUFFER_BYTES = 2 * 1024 * 1024
MAGIC = b"SQLite format 3\x00"


def inspect(name, expected_digest):
    p = ROOT / name
    before = p.lstat()
    if (not stat.S_ISREG(before.st_mode) or before.st_nlink != 1
            or before.st_size != EXPECTED_BYTES):
        raise RuntimeError("SOURCE_NOT_REGULAR_OR_SIZE_CHANGED")
    if any((ROOT / (name + suffix)).exists()
           for suffix in ("-wal", "-shm", "-journal")):
        raise RuntimeError("SOURCE_HAS_SQLITE_SIDECAR")
    fd = os.open(p, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    try:
        opened = os.fstat(fd)
        fields = ("st_dev", "st_ino", "st_size", "st_mtime_ns", "st_ctime_ns")
        if any(getattr(before, f) != getattr(opened, f) for f in fields):
            raise RuntimeError("SOURCE_CHANGED_BEFORE_READ")
        compressed = zlib.compressobj(level=1, method=zlib.DEFLATED, wbits=31)
        digest = hashlib.sha256()
        total = 0
        gz_bytes = 0
        with os.fdopen(fd, "rb", closefd=False) as inp:
            header = inp.read(16)
            if header != MAGIC:
                raise RuntimeError("SOURCE_BAD_SQLITE_MAGIC")
            inp.seek(0)
            while True:
                chunk = inp.read(BUFFER_BYTES)
                if not chunk:
                    break
                total += len(chunk)
                if total > EXPECTED_BYTES:
                    raise RuntimeError("SOURCE_GREW")
                digest.update(chunk)
                gz_bytes += len(compressed.compress(chunk))
        gz_bytes += len(compressed.flush())
        after = os.fstat(fd)
        if (total != EXPECTED_BYTES
                or any(getattr(opened, f) != getattr(after, f) for f in fields)):
            raise RuntimeError("SOURCE_CHANGED_DURING_READ")
        if digest.hexdigest() != expected_digest:
            raise RuntimeError("SOURCE_SHA256_NOT_EXPECTED")
        return {
            "name": name,
            "source_bytes": total,
            "source_sha256_verified": True,
            "gzip_level1_exact_bytes": gz_bytes,
            "gzip_level1_ratio": round(gz_bytes / total, 6),
            "compression_stream_written_to_disk": False,
            "source_unchanged": True,
        }
    finally:
        os.close(fd)


def transport_capabilities():
    tool = shutil.which("rclone")
    config = Path.home() / ".config/rclone/rclone.conf"
    config_regular = False
    if config.exists() and not config.is_symlink():
        st = config.lstat()
        config_regular = stat.S_ISREG(st.st_mode)
    remote_count = None
    if tool and config_regular:
        try:
            proc = subprocess.run(
                [tool, "--config", str(config), "listremotes"],
                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                text=True, timeout=12, check=False,
            )
            if proc.returncode == 0:
                remote_count = len([x for x in proc.stdout.splitlines() if x.endswith(":")])
        except (OSError, subprocess.TimeoutExpired):
            pass
    # A configured remote is NOT evidence of Google Drive permissions, usable
    # scope, backup quota, or recovered private key; never claim it is.
    return {
        "rclone_installed": bool(tool),
        "rclone_config_file_present": config_regular,
        "rclone_configured_remotes_count": remote_count,
        "gcloud_cli_installed": bool(shutil.which("gcloud")),
        "google_drive_direct_upload_authorized": False,
        "drive_quota_verified": False,
        "recovery_private_key_verified": False,
        "github_artifact_capacity_verified": False,
    }


def main():
    import pwd
    if os.geteuid() != pwd.getpwnam("githubops").pw_uid:
        raise RuntimeError("WRONG_ACCOUNT")
    if ROOT.is_symlink() or not ROOT.is_dir():
        raise RuntimeError("ROOT_NOT_SAFE")
    t0 = time.monotonic()
    st = os.statvfs(ROOT)
    free_before = st.f_bavail * st.f_frsize
    files = [inspect(name, digest) for name, digest in EXPECTED]
    st = os.statvfs(ROOT)
    free_after = st.f_bavail * st.f_frsize
    total_gzip = sum(x["gzip_level1_exact_bytes"] for x in files)
    result = {
        "schema": "moj.factory.nov5.drive-admission.readonly.v1",
        "source": "two fixed immutable Nov5 snapshots",
        "read_only": True,
        "source_files_deleted": 0,
        "destination_files_created": 0,
        "source_snapshots": files,
        "source_total_bytes": sum(x["source_bytes"] for x in files),
        "gzip_level1_total_exact_bytes": total_gzip,
        "gzip_level1_total_ratio": round(
            total_gzip / sum(x["source_bytes"] for x in files), 6),
        "vps_free_bytes_before": free_before,
        "vps_free_bytes_after": free_after,
        "transport": transport_capabilities(),
        "safe_to_delete_originals": False,
        "backup_uploaded_to_drive": False,
        "elapsed_seconds": round(time.monotonic() - t0, 2),
    }
    print("MOJ_FACTORY_NOV5_DRIVE_ADMISSION=" +
          json.dumps(result, sort_keys=True), flush=True)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print("MOJ_FACTORY_NOV5_DRIVE_ADMISSION_FAILED=" +
              type(exc).__name__ + ":" + str(exc), file=sys.stderr, flush=True)
        sys.exit(1)
