#!/usr/bin/env python3
"""Bounded read-only metadata inventory for existing factory SQLite snapshots.

Does not read database pages, create backups, hash files, or change services.
Never prints private filenames or paths. This is NOT backup or restore proof.
"""
import argparse
import datetime as dt
import json
import os
import re
import stat
from pathlib import Path

PATTERN = re.compile(r"^master-before-[0-9]{8}T[0-9]{6}Z[.]sqlite3$")
SCAN_LIMIT = 5000
UTC = dt.timezone.utc

def inspection(root: Path):
    try:
        for part in (root, *root.parents):
            if part.is_symlink():
                return {"status": "BLOCKED", "reason": "LINKED_ANCESTOR"}
        root_stat = root.stat()
        if not stat.S_ISDIR(root_stat.st_mode):
            return {"status": "BLOCKED", "reason": "ROOT_NOT_DIRECTORY"}
    except OSError:
        return {"status": "BLOCKED", "reason": "ROOT_UNAVAILABLE"}
    backups = root / "operations" / "backups"
    samples = []
    scanned = 0
    truncated = False
    try:
        if (root / "operations").is_symlink() or backups.is_symlink() or not backups.is_dir():
            return {"status": "BLOCKED", "reason": "BACKUPS_UNAVAILABLE"}
        with os.scandir(backups) as it:
            for e in it:
                scanned += 1
                if scanned > SCAN_LIMIT:
                    truncated = True
                    break
                if not PATTERN.fullmatch(e.name) or e.is_symlink():
                    continue
                info = e.stat(follow_symlinks=False)
                if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                    continue
                samples.append((info.st_mtime_ns, info.st_size))
    except OSError:
        return {"status": "BLOCKED", "reason": "BACKUPS_ENUMERATION_FAILED"}
    samples.sort(reverse=True)
    v = os.statvfs(root)
    try:
        load = [round(x, 2) for x in os.getloadavg()]
    except OSError:
        load = None
    top = [{"bytes": size,
            "mtime_utc": dt.datetime.fromtimestamp(mtime / 1e9, UTC).isoformat()}
           for mtime, size in samples[:3]]
    return {"schema": "f01-backup-source-inventory.v1",
            "status": "INSPECT_ONLY" if not truncated else "INCOMPLETE",
            "observed_utc": dt.datetime.now(UTC).isoformat(),
            "read_only": True,
            "existing_snapshot_count": len(samples),
            "newest_three_metadata_only": top,
            "scanned_entries": min(scanned, SCAN_LIMIT),
            "truncated": truncated,
            "root_unprivileged_available_bytes": v.f_bavail * v.f_frsize,
            "root_total_free_bytes_including_privileged": v.f_bfree * v.f_frsize,
            "guest_loadavg": load,
            "database_consistency_verified": False,
            "offhost_backup_exists_verified": False,
            "restore_verified": False,
            "transfer_allowed": False,
            "reboot_allowed": False}

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", required=True)
    a = p.parse_args()
    result = inspection(Path(a.root).absolute())
    print(json.dumps(result, sort_keys=True))
    return 0 if result["status"] == "INSPECT_ONLY" else 2

if __name__ == "__main__":
    raise SystemExit(main())
