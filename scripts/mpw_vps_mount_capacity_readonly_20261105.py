#!/usr/bin/env python3
"""Inventory distinct local VPS filesystems without disclosing mount paths.

Metadata only: no file contents, backups, database connections, writes,
directory creation, disk mounting, service changes, or container operations.
The resulting candidate is never automatically approved for a restore.
"""

import json
import os
import re
from pathlib import Path


GIB = 1024 ** 3
RESTORE_SCREEN_BYTES = 40 * GIB
# Ignore virtual, removable, network and unknown mounts rather than mistake
# their capacity for a suitable independent local restore target.
LOCAL_TYPES = frozenset({"ext2", "ext3", "ext4", "xfs", "btrfs", "zfs", "f2fs"})
MAX_MOUNTS = 4096
_OCTAL = re.compile(r"\\([0-7]{3})")


def decode_mount_path(escaped):
    """Decode mountinfo's octal-escaped whitespace without shell execution."""
    return _OCTAL.sub(lambda match: chr(int(match.group(1), 8)), escaped)


def parse_local_mounts(lines):
    """Extract only local mountpoints; never return them in final JSON."""
    found = []
    for line in lines:
        left, separator, right = line.partition(" - ")
        if not separator:
            continue
        fields = left.split()
        source = right.split()
        if len(fields) < 5 or not source or source[0] not in LOCAL_TYPES:
            continue
        path = decode_mount_path(fields[4])
        if path.startswith("/"):
            found.append((path, source[0]))
    return found


def _device_record(path):
    """Read only kernel-owned stat metadata, never access file contents."""
    if os.path.islink(path):
        return None
    stat = os.stat(path)
    fs = os.statvfs(path)
    return {
        "device": stat.st_dev,
        "free_bytes": max(0, fs.f_bavail * fs.f_frsize),
        "writable_hint": bool(os.access(path, os.W_OK | os.X_OK)),
    }


def inspect(mountinfo_path="/proc/self/mountinfo", home=None):
    home = Path.home() if home is None else Path(home)
    home_info = _device_record(home)
    if home_info is None:
        raise OSError("home is not a regular directory")

    mount_lines = []
    inventory_truncated = False
    with open(mountinfo_path, encoding="utf-8", errors="replace") as stream:
        for index, line in enumerate(stream):
            if index >= MAX_MOUNTS:
                inventory_truncated = True
                break
            mount_lines.append(line)

    unique = {}
    skipped_unreadable = 0
    for path, _fs_type in parse_local_mounts(mount_lines):
        try:
            candidate = _device_record(path)
        except (OSError, ValueError):
            skipped_unreadable += 1
            continue
        if candidate is None or candidate["device"] == home_info["device"]:
            continue
        device = candidate["device"]
        if device not in unique:
            unique[device] = candidate
        else:
            # Bind mounts of the same filesystem must never be summed.
            unique[device]["writable_hint"] |= candidate["writable_hint"]

    candidates = sorted(unique.values(), key=lambda item: item["free_bytes"], reverse=True)
    viable = [item for item in candidates if item["free_bytes"] >= RESTORE_SCREEN_BYTES
              and item["writable_hint"]]
    return {
        "classification": "READ_ONLY_MPW_VPS_DISTINCT_LOCAL_MOUNTS",
        "home_free_bytes": home_info["free_bytes"],
        "required_free_bytes_screen": RESTORE_SCREEN_BYTES,
        "independent_local_device_count": len(candidates),
        "largest_independent_free_bytes": candidates[0]["free_bytes"] if candidates else 0,
        "independent_devices_meeting_size_floor": sum(
            item["free_bytes"] >= RESTORE_SCREEN_BYTES for item in candidates),
        "independent_devices_with_write_hint_and_size_floor": len(viable),
        "inventory_complete": not inventory_truncated and not skipped_unreadable,
        "mount_records_truncated": inventory_truncated,
        "unreadable_local_mount_count": skipped_unreadable,
        "private_paths_or_device_ids_reported": False,
        "storage_isolation_approved": False,
        "isolated_restore_performed": False,
        "live_services_modified": False,
        "release_permitted": False,
    }


if __name__ == "__main__":
    try:
        result = inspect()
    except (OSError, ValueError):
        print("READ_ONLY_MOUNT_INVENTORY_UNAVAILABLE_NO_RELEASE")
        raise SystemExit(1)
    print(json.dumps(result, sort_keys=True))
