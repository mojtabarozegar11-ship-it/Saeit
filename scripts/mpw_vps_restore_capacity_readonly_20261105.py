#!/usr/bin/env python3
"""Read-only VPS capacity probe for the existing encrypted MojPlayWin backup.

Reads only filesystem metadata and two manifest documents. It never opens
customer data, decrypts archives, starts containers or writes to production.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import stat
import subprocess
from pathlib import Path


STEM = "mojplaywin_20261102T090223Z_3c23e70544115e95"
ROOT = Path.home() / ".private-mojplaywin-offhost-backups"


def regular_private(path):
    if path.is_symlink():
        return False
    try:
        info = path.stat()
    except OSError:
        return False
    return (stat.S_ISREG(info.st_mode) and info.st_uid == os.getuid()
            and not (info.st_mode & 0o177))


def archive(kind):
    if kind not in ("mysql", "files"):
        raise RuntimeError("INVALID_ARCHIVE_KIND")
    prefix = STEM + "_" + kind + "_gpgv2"
    blob = ROOT / (prefix + ".gpg")
    manifest = ROOT / (prefix + ".manifest.json")
    if not regular_private(blob) or not regular_private(manifest):
        raise RuntimeError("BACKUP_ARCHIVE_OR_MANIFEST_UNAVAILABLE")
    if manifest.stat().st_size > 32768:
        raise RuntimeError("MANIFEST_TOO_LARGE")
    meta = json.loads(manifest.read_text(encoding="ascii"))
    encrypted = blob.stat().st_size
    plaintext = meta.get("plaintext_bytes")
    if (meta.get("kind") != kind or meta.get("backup_set_stem") != STEM
            or meta.get("format") != "OpenPGP-AES256-GPGv2"
            or meta.get("ciphertext_roundtrip_integrity_verified") is not True
            or meta.get("source_completion_footer_verified") is not True
            or meta.get("encrypted_bytes") != encrypted
            or not isinstance(plaintext, int) or plaintext < 1024
            or not isinstance(meta.get("plaintext_sha256"), str)
            or not re.fullmatch("[0-9a-f]{64}", meta["plaintext_sha256"])):
        raise RuntimeError("MANIFEST_METADATA_UNVERIFIED")
    return {"encrypted_bytes": encrypted, "plaintext_bytes": plaintext,
            "manifest_metadata_valid": True}


def docker_readable():
    if not shutil.which("docker"):
        return {"cli_present": False, "daemon_available": False}
    try:
        probe = subprocess.run(
            ["docker", "info", "--format", "{{.ServerVersion}}"],
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL, timeout=5, check=False,
        )
        ready = probe.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        ready = False
    return {"cli_present": True, "daemon_available": ready}


def run():
    if ROOT.is_symlink() or not ROOT.is_dir():
        raise RuntimeError("PRIVATE_ARCHIVE_ROOT_UNAVAILABLE")
    sql = archive("mysql")
    files = archive("files")
    free_bytes = shutil.disk_usage(ROOT).free
    # This is only a conservative disk-space check, not a restore certificate.
    estimate = int(sql["plaintext_bytes"] * 1.4) + 2 * 1024**3
    report = {
        "source": "existing_private_vps_backup_manifests",
        "mysql": sql,
        "files": files,
        "vps_free_disk_bytes": free_bytes,
        "isolated_mysql_disk_reserve_bytes": estimate,
        "conservative_disk_gate_pass": free_bytes >= estimate,
        "docker": docker_readable(),
        "mariadb_client_present": bool(shutil.which("mariadb") or shutil.which("mysql")),
        "database_decrypted": False,
        "archive_streamed": False,
        "restoration_performed": False,
        "production_writes": False,
        "customer_data_printed": False,
    }
    print("MPW_VPS_RESTORE_CAPACITY_READONLY=" + json.dumps(report, sort_keys=True))


if __name__ == "__main__":
    run()
