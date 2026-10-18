#!/usr/bin/env python3
"""Metadata-only GPGv2 backup state and recovery key escrow diagnostic (VPS).

Does not read file bodies, keys or manifests, print filename locations/contents,
remove/rename files, restore, decrypt or change any server data.
"""
import json
import os
import stat
from pathlib import Path

STEM = "mojplaywin_20261017"


def describe(path):
    try:
        s = path.lstat()
        return {
            "exists": True,
            "regular": stat.S_ISREG(s.st_mode),
            "symlink": stat.S_ISLNK(s.st_mode),
            "private": not bool(s.st_mode & 0o177),
            "owned": s.st_uid == os.getuid(),
            "bytes": s.st_size,
        }
    except OSError:
        return {"exists": False, "regular": False, "symlink": False, "private": False, "owned": False, "bytes": None}


def inspect(home=None):
    base = Path.home() if home is None else Path(home)
    backups = base / ".private-mojplaywin-offhost-backups"
    keyroot = base / ".config" / "mojplaywin-backup-recovery"
    groups = {}
    for kind in ("mysql", "files"):
        prefix = STEM + "_" + kind + "_gpgv2"
        groups[kind] = {
            "partial": describe(backups / (prefix + ".gpg.partial")),
            "complete": describe(backups / (prefix + ".gpg")),
            "manifest": describe(backups / (prefix + ".manifest.json")),
        }
    return {
        "classification": "READ_ONLY_GPGV2_BACKUP_METADATA",
        "artifacts": groups,
        "gpg_v2_private_homedir": {"exists": (keyroot / "gnupg-v2").is_dir(), "symlink": (keyroot / "gnupg-v2").is_symlink()},
        "recovery_key": describe(keyroot / "recovery-key.bin"),
        "off_vps_key_escrow_verified": False,
        "content_integrity_verified": False,
        "complete_recoverable_backup_verified": False,
        "backup_created": False,
        "release_permitted": False,
    }


if __name__ == "__main__":
    print(json.dumps(inspect(), sort_keys=True))
