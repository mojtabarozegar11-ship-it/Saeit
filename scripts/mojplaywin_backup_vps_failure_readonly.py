#!/usr/bin/env python3
"""VPS metadata-only reason classifier after the aborted encrypted backup.

Does not open any backup file or key, print path names, decrypt, write, delete,
connect to database, restart services or modify sub-sites.
"""
import json
import os
import stat
from pathlib import Path


def classify_directory(p):
    try:
        s = p.lstat()
        return {
            "exists": True, "is_directory": stat.S_ISDIR(s.st_mode),
            "is_symlink": stat.S_ISLNK(s.st_mode),
            "owned_by_current_user": s.st_uid == os.getuid(),
            "private_permissions": not bool(s.st_mode & 0o077),
            "writable": os.access(p, os.W_OK | os.X_OK),
        }
    except OSError:
        return {"exists": False, "is_directory": False,
                "is_symlink": False, "owned_by_current_user": False,
                "private_permissions": False, "writable": False}


def classify_file(p):
    try:
        s = p.lstat()
        return {"exists": True, "regular": stat.S_ISREG(s.st_mode),
                "symlink": stat.S_ISLNK(s.st_mode),
                "private_permissions": not bool(s.st_mode & 0o177),
                "owned_by_current_user": s.st_uid == os.getuid(),
                "bytes": s.st_size}
    except OSError:
        return {"exists": False, "regular": False, "symlink": False,
                "private_permissions": False, "owned_by_current_user": False,
                "bytes": None}


def inspect(home=None):
    home = home or Path.home()
    backup = home / ".private-mojplaywin-offhost-backups"
    cfg_parent = home / ".config"
    keydir = cfg_parent / "mojplaywin-backup-recovery"
    result = {
        "classification": "READ_ONLY_VPS_BACKUP_FAILURE_METADATA",
        "home": classify_directory(home),
        "backup_dir": classify_directory(backup),
        "key_config_parent": classify_directory(cfg_parent),
        "key_dir": classify_directory(keydir),
        "recovery_key": classify_file(keydir / "recovery-key.bin"),
        "mysql_partial": classify_file(backup / "mojplaywin_20261017_mysql.gcm.partial"),
        "files_partial": classify_file(backup / "mojplaywin_20261017_files.gcm.partial"),
        "mysql_complete": classify_file(backup / "mojplaywin_20261017_mysql.gcm"),
        "files_complete": classify_file(backup / "mojplaywin_20261017_files.gcm"),
        "mysqldump_sent_from_runner": False,
        "isolated_restore_verified": False,
        "release_permitted": False,
    }
    try:
        s = os.statvfs(home)
        result["disk_free_bytes"] = s.f_bavail * s.f_frsize
    except OSError:
        result["disk_free_bytes"] = None
    try:
        from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
        key = b"t" * 32
        enc = Cipher(algorithms.AES(key), modes.GCM(b"t" * 12)).encryptor()
        enc.update(b"test") + enc.finalize()
        result["aes_gcm_in_memory_works"] = len(enc.tag) == 16
    except Exception:
        result["aes_gcm_in_memory_works"] = False
    return result


if __name__ == "__main__":
    try:
        print(json.dumps(inspect(), sort_keys=True))
    except Exception:
        print(json.dumps({"classification":"READ_ONLY_VPS_BACKUP_PROBE_FAILED",
                          "release_permitted":False}))
        raise SystemExit(1)
