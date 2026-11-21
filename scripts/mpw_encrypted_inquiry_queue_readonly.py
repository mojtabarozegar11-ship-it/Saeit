#!/usr/bin/env python3
"""Privacy-preserving, read-only pending MojPlayWin commercial inquiry census.

This reads filesystem METADATA ONLY from the cPanel encrypted inquiry queue.
No messages are decrypted, sent, marked read, deleted or acknowledged. Never
prints customer identifiers, paths, record names or any key material.

A dispatch marker means 'queued to local MTA', NOT customer contacted or owner
message delivered. The inquiry form itself does not produce a commercial order.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys
import time

PRIVATE_DIR = Path("/home/zomorod2/.private_mojplaywin_main_agents/revenue-inquiries")
ENTRY = re.compile(r"\A[0-9]{8}-[A-F0-9]{18}\.json\Z")
MARKER = ".owner-dispatched-"
MAX_SCAN = 10000
MAX_SIZE = 12000


def _regular_owned_file(path):
    if path.is_symlink() or not path.is_file():
        return None
    info = path.stat(follow_symlinks=False)
    if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1
            or info.st_uid != os.geteuid()
            or not 0 < info.st_size <= MAX_SIZE):
        return None
    return info


def census(root=PRIVATE_DIR, now=None):
    """Return anonymous, conservative counts, with zero mutation."""
    current = time.time() if now is None else now
    if type(current) not in (int, float) or current <= 0:
        raise ValueError("Invalid reading time")
    result = {
        "scope": "MPW_ENCRYPTED_INQUIRY_QUEUE_METADATA_ONLY",
        "available": False, "files_inspected": 0, "encrypted_record_candidates": 0,
        "not_dispatched_marker": 0, "marker_present": 0,
        "older_than_24h_unmarked": 0, "older_than_72h_unmarked": 0,
        "last_7d_candidates": 0, "last_7d_unmarked": 0,
        "invalid_metadata": 0, "scan_truncated": False,
        "private_payload_read": False, "record_decrypted": False,
        "recipient_identity_read": False, "mail_sent": False,
        "markers_created": False, "files_modified": False,
        "dispatch_marker_is_delivery_proof": False,
        "numbers_are_unverified_encrypted_record_candidates": True,
    }
    root = Path(root)
    if root.is_symlink() or not root.is_dir():
        return result
    rootstat = root.stat(follow_symlinks=False)
    if (rootstat.st_uid != os.geteuid()
            or stat.S_IMODE(rootstat.st_mode) & 0o077):
        return result
    result["available"] = True
    # Sort so repeated scans with a bounded budget have deterministic scope.
    entries = sorted(os.scandir(root), key=lambda ent: ent.name)
    for ent in entries:
        if not ENTRY.fullmatch(ent.name):
            continue
        if result["files_inspected"] >= MAX_SCAN:
            result["scan_truncated"] = True
            break
        result["files_inspected"] += 1
        path = root / ent.name
        info = _regular_owned_file(path)
        if info is None:
            result["invalid_metadata"] += 1
            continue
        result["encrypted_record_candidates"] += 1
        age = max(0, current - info.st_mtime)
        recent = age <= 7 * 86400
        result["last_7d_candidates"] += int(recent)
        marker = root / (MARKER + hashlib.sha256(ent.name.encode("ascii")).hexdigest() + ".json")
        dispatch_info = _regular_owned_file(marker) if marker.exists() or marker.is_symlink() else None
        if dispatch_info is not None:
            result["marker_present"] += 1
        else:
            result["not_dispatched_marker"] += 1
            result["last_7d_unmarked"] += int(recent)
            result["older_than_24h_unmarked"] += int(age > 86400)
            result["older_than_72h_unmarked"] += int(age > 72 * 3600)
    return result


if __name__ == "__main__":
    try:
        report = census()
    except (OSError, ValueError, TypeError) as exc:
        report = {
            "scope": "MPW_ENCRYPTED_INQUIRY_QUEUE_METADATA_ONLY",
            "available": False, "error_class": type(exc).__name__,
            "files_modified": False, "mail_sent": False,
        }
    print("MPW_ENCRYPTED_LEAD_QUEUE_READONLY=" +
          json.dumps(report, sort_keys=True, ensure_ascii=True))
    sys.exit(0 if report.get("available") and not report.get("scan_truncated") else 2)
