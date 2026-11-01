#!/usr/bin/env python3
"""Read-only cPanel symlink dependency inventory for MojPlayWin primary roots.

No file contents, database, orders, target names or paths are printed.
No links are followed during traversal; no host files are created or changed.
"""
from __future__ import annotations

from collections import Counter
import json
import os
import posixpath
import pwd
from pathlib import Path, PurePosixPath

HOME = Path("/home/zomorod2")
ROOTS = ("Saeit-staging", "mojplaywin.com")
MAX_WALK_ENTRIES = 200_000


def role_for_target(source_relative, link_target):
    """Coarse location class only, never a path or filename."""
    if not isinstance(link_target, str) or not link_target:
        return "invalid_target"
    if link_target.startswith("/"):
        try:
            rel = PurePosixPath(link_target).relative_to(str(HOME))
        except ValueError:
            return "outside_account"
        candidate = str(rel)
    else:
        candidate = posixpath.normpath(posixpath.join(
            *PurePosixPath(source_relative).parts[:-1], link_target))
    parts = PurePosixPath(candidate).parts
    if not parts or parts[0] == "..":
        return "outside_account"
    if parts[0] in ROOTS:
        return "backed_primary_roots"
    if parts[0] == "virtualenv":
        return "python_runtime_dependency"
    if parts[0] in ("Saeit", "public_html"):
        return "alternative_site_code_root"
    if parts[0] in ("tmp", "logs", ".local", ".cache"):
        return "ephemeral_runtime_path"
    return "other_unbacked_account_root"


def inspect():
    result = {
        "classification": "MPW_LIVE_SYMLINK_DEPENDENCIES_READ_ONLY",
        "production_modified": False, "database_read": False,
        "orders_created": 0, "payments_created": 0,
        "paths_or_targets_logged": False,
        "archive_data_read": False,
        "all_primary_roots_pinned": True,
    }
    if pwd.getpwuid(os.geteuid()).pw_name != "zomorod2":
        raise RuntimeError("UNEXPECTED_OWNER")
    wsgi = HOME / "mojplaywin.com" / "passenger_wsgi.py"
    if (not wsgi.is_file() or wsgi.is_symlink() or
            "APP='/home/zomorod2/Saeit-staging'" not in
            wsgi.read_text("utf8", "replace")):
        raise RuntimeError("PASSENGER_PIN_MISSING")
    for name in ROOTS:
        p = HOME / name
        if not p.is_dir() or p.is_symlink() or p.resolve() != p:
            raise RuntimeError("PRIMARY_ROOT_DRIFT")
    categories, resolution = Counter(), Counter()
    links = entries = 0
    def fail_walk(_error):
        raise RuntimeError("SCAN_UNREADABLE")
    for name in ROOTS:
        for directory, dirs, files in os.walk(
                HOME / name, followlinks=False, onerror=fail_walk):
            entries += len(dirs) + len(files)
            if entries > MAX_WALK_ENTRIES:
                raise RuntimeError("INVENTORY_LIMIT")
            for entry in dirs + files:
                path = Path(directory) / entry
                if not path.is_symlink():
                    continue
                links += 1
                try:
                    raw_target = os.readlink(path)
                    role = role_for_target(str(path.relative_to(HOME)), raw_target)
                    resolved = path.resolve(strict=False)
                    if path.exists():
                        owner = resolved.stat().st_uid == os.geteuid()
                        state = "present_same_owner" if owner else "present_other_owner"
                    else:
                        state = "dangling"
                    categories[role] += 1
                    resolution[role + "_" + state] += 1
                except (OSError, RuntimeError, ValueError):
                    categories["unreadable"] += 1
    result.update({
        "examined_entries_capped": entries,
        "total_symlinks": links,
        "dependency_classes": dict(sorted(categories.items())),
        "dependency_resolution": dict(sorted(resolution.items())),
    })
    return result


if __name__ == "__main__":
    print("MPW_LIVE_LINK_INVENTORY=" + json.dumps(inspect(), sort_keys=True))
