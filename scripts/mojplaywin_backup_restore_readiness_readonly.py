#!/usr/bin/env python3
"""Bounded, read-only backup prerequisites for the *live* MojPlayWin Django host.

Uses filesystem metadata only. No SQL connections, secrets, env file reads,
server writes, tar/compression, migrations, Passenger restart or file contents.
Do not infer recovery ability from a few candidate paths. This never grants
permission to deploy PR #390 or modify ANY independent child subsite.
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path

HOME = Path("/home/zomorod2")
APP = HOME / "Saeit-staging"
DOCROOT = HOME / "mojplaywin.com"
MAX_ENTRIES = 12000
MAX_SECONDS = 8.0
MAX_DEPTH = 7


def file_stat(path: Path) -> dict:
    try:
        if path.is_symlink() or not path.is_file():
            return {"exists_regular": False, "bytes": None}
        return {"exists_regular": True, "bytes": path.stat().st_size}
    except OSError:
        return {"exists_regular": False, "bytes": None}


def scan_media(root: Path, *, limit=MAX_ENTRIES, time_limit=MAX_SECONDS) -> dict:
    data = {
        "directory_exists": False, "sample_file_count": 0, "sample_bytes": 0,
        "visited_entries": 0, "symlinks_skipped": 0, "complete": False,
    }
    try:
        if root.is_symlink() or not root.is_dir():
            return data
        data["directory_exists"] = True
        stack = [(root, 0)]
        deadline = time.monotonic() + time_limit
        while stack:
            if time.monotonic() > deadline or data["visited_entries"] >= limit:
                return data
            directory, depth = stack.pop()
            with os.scandir(directory) as entries:
                for item in entries:
                    data["visited_entries"] += 1
                    if data["visited_entries"] > limit or time.monotonic() > deadline:
                        return data
                    try:
                        if item.is_symlink():
                            data["symlinks_skipped"] += 1
                        elif item.is_file(follow_symlinks=False):
                            data["sample_file_count"] += 1
                            data["sample_bytes"] += item.stat(follow_symlinks=False).st_size
                        elif item.is_dir(follow_symlinks=False):
                            if depth >= MAX_DEPTH:
                                return data
                            stack.append((Path(item.path), depth + 1))
                    except OSError:
                        return data
        data["complete"] = True
    except OSError:
        return data
    return data


def disk_snapshot(home: Path) -> dict:
    try:
        if home.is_symlink() or not home.is_dir():
            return {"measured": False, "available_bytes": None}
        stat = os.statvfs(home)
        return {"measured": True, "available_bytes": stat.f_bavail * stat.f_frsize}
    except OSError:
        return {"measured": False, "available_bytes": None}


def inspect(home: Path = HOME, app: Path = APP, docroot: Path = DOCROOT) -> dict:
    return {
        "classification": "READ_ONLY_FULL_BACKUP_PREREQUISITES",
        "live_app_root_directory": app.is_dir() and not app.is_symlink(),
        "site_document_root_directory": docroot.is_dir() and not docroot.is_symlink(),
        "sqlite_candidate": file_stat(app / "db.sqlite3"),
        "sqlite_wal_candidate": file_stat(app / "db.sqlite3-wal"),
        "sqlite_shm_candidate": file_stat(app / "db.sqlite3-shm"),
        "candidate_media_roots": {
            "shared_django_media": scan_media(app / "media"),
            "shared_django_uploads": scan_media(app / "uploads"),
            "public_docroot_media": scan_media(docroot / "media"),
            "public_docroot_uploads": scan_media(docroot / "uploads"),
        },
        "hosting_account_disk": disk_snapshot(home),
        "database_engine_live_confirmed": False,
        "all_db_and_media_locations_found": False,
        "db_consistent_snapshot_created": False,
        "complete_production_backup_created": False,
        "offhost_independent_backup_verified": False,
        "isolated_restore_rehearsal_passed": False,
        "protected_subsite_backup_coverage_verified": False,
        "route_isolation_proven": False,
        "release_permitted": False,
        "limitations": [
            "A SQLite candidate file does NOT establish that production uses SQLite.",
            "Candidate media paths are NOT a complete inventory of user files and unknown subsites.",
            "Disk space measurement alone does NOT prove a usable offsite backup or snapshot.",
            "No database connection, backup creation or restoration was performed.",
        ],
    }


if __name__ == "__main__":
    print(json.dumps(inspect(), sort_keys=True))
