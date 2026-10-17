#!/usr/bin/env python3
"""Probe separate VPS backup destination vs shared cPanel source (read-only).

Run on a pinned SSH endpoint via existing main-only audit workflow.
Never reads any user file content, credentials or secret values, never creates
a file or directory, never changes production or starts a backup operation.
Paths, hosts, directory names and exception messages are NEVER printed.
"""
from __future__ import annotations

import importlib.util
import json
import os
import shutil
import sys
from pathlib import Path


def space(path: Path) -> dict:
    try:
        if not path.is_dir() or path.is_symlink():
            return {"exists": False, "free_bytes": None}
        info = os.statvfs(path)
        return {"exists": True, "free_bytes": info.f_bavail * info.f_frsize}
    except OSError:
        return {"exists": False, "free_bytes": None}


def safe_dir(path: Path) -> dict:
    try:
        return {
            "exists": path.is_dir() and not path.is_symlink(),
            "writable_for_current_user": path.is_dir() and not path.is_symlink()
            and os.access(path, os.W_OK | os.X_OK),
        }
    except OSError:
        return {"exists": False, "writable_for_current_user": False}


def top_level_summary(path: Path) -> dict:
    result = {"readable": False, "subdirectories": 0, "regular_files": 0,
              "symlinks_not_followed": 0}
    try:
        with os.scandir(path) as entries:
            for item in entries:
                if item.is_symlink():
                    result["symlinks_not_followed"] += 1
                elif item.is_dir(follow_symlinks=False):
                    result["subdirectories"] += 1
                elif item.is_file(follow_symlinks=False):
                    result["regular_files"] += 1
        result["readable"] = True
    except OSError:
        pass
    return result


def probe(destination: str, *, home: Path | None = None) -> dict:
    if destination not in {"vps", "cpanel"}:
        raise ValueError("unsupported target")
    if destination == "vps":
        home = Path.home() if home is None else home
        return {
            "classification": "READ_ONLY_VPS_OFFHOST_BACKUP_DESTINATION",
            "offhost_candidate_is_vps": True,
            "backup_storage_root_confirmed": False,
            "home_directory": safe_dir(home),
            "home_free": space(home),
            "known_backup_folder": safe_dir(home / "backups"),
            "known_named_storage": safe_dir(Path("/srv/backup")),
            "tools_available": {command: shutil.which(command) is not None
                                for command in ("age", "gpg", "openssl", "tar", "gzip", "sha256sum", "python3")},
            "python_cryptography_module_available": importlib.util.find_spec("cryptography") is not None,
            "outbound_backup_stream_tested": False,
            "encryption_and_key_recovery_tested": False,
            "backup_destination_approved_safe": False,
            "backup_written": False,
            "release_permitted": False,
        }
    home = Path("/home/zomorod2") if home is None else home
    return {
        "classification": "READ_ONLY_CPANEL_BACKUP_SOURCE_TOPOLOGY",
        "account_root": safe_dir(home),
        "account_direct_child_inventory": top_level_summary(home),
        "tools_available": {command: shutil.which(command) is not None
                            for command in ("mysqldump", "mariadb-dump", "mysql", "mariadb",
                                            "tar", "gzip", "openssl", "python3")},
        "full_tenant_media_db_inventory_complete": False,
        "active_database_connection_verified": False,
        "backup_written": False,
        "release_permitted": False,
    }


if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in ("vps", "cpanel"):
        raise SystemExit("usage: script.py [vps|cpanel]")
    try:
        print(json.dumps(probe(sys.argv[1]), sort_keys=True))
    except Exception:
        print(json.dumps({"classification": "READ_ONLY_BACKUP_DESTINATION_ERROR",
                          "backup_written": False, "release_permitted": False}))
        raise SystemExit(1)
