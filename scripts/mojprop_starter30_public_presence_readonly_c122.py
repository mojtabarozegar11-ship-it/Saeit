#!/usr/bin/env python3
"""P0 Moj Prop: owner-only metadata audit of three approved *public* static assets.

No network, HTTP requests, DB, shell, checkout, customers or filesystem writes.
An exact file match proves bytes exist in this docroot, not delivery over
HTTPS, authorized sale, TRX processing, or a funded prop challenge.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import pwd
import stat

OWNER = "zomorod2"
HOME = Path("/home/zomorod2")
DOCROOT = HOME / "mojplaywin.com"
STATIC_DIR = DOCROOT / "moj-prop" / "starter-30-trx"
REVIEWED_BLOBS = {
    "index.html": "c4185051020aa66405da8a9d8aaae3b22b90f7f6",
    "journal-template.csv": "2d732321f1c1f431685e514789cf26bf2a977d84",
    "journal-guide.txt": "7a8978ca6f3db31064552a41b2bdfb6c7de56036",
}
MAX_FILE_BYTES = 90000
ALLOWED_STATES = frozenset(("missing", "unsafe", "unavailable",
                            "reviewed_exact", "unreviewed_bytes"))


def git_blob_sha(data: bytes) -> str:
    return hashlib.sha1(
        b"blob " + str(len(data)).encode("ascii") + bytes([0]) + data
    ).hexdigest()


def _safe_fixed_parents(path: Path, base: Path) -> bool:
    if path == base or base not in path.parents:
        return False
    cursor = path.parent
    while True:
        try:
            meta = cursor.lstat()
        except OSError:
            return False
        if (not stat.S_ISDIR(meta.st_mode) or meta.st_uid != os.geteuid()
                or meta.st_mode & 0o022):
            return False
        if cursor == base:
            return True
        if base not in cursor.parents:
            return False
        cursor = cursor.parent


def inventory_one(path: Path, *, expected_blob: str) -> str:
    """Fixed public filenames only; descriptor-bound, bounded direct read."""
    if not _safe_fixed_parents(path, base=HOME):
        return "unsafe"
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    except FileNotFoundError:
        return "missing"
    except OSError:
        return "unavailable"
    try:
        meta = os.fstat(fd)
        if (not stat.S_ISREG(meta.st_mode)
                or meta.st_uid != os.geteuid()
                or meta.st_nlink != 1
                or meta.st_mode & 0o022
                or not 10 <= meta.st_size <= MAX_FILE_BYTES):
            return "unsafe"
        with os.fdopen(fd, "rb", closefd=False) as source:
            data = source.read(MAX_FILE_BYTES + 1)
        if len(data) != meta.st_size:
            return "unavailable"
        return "reviewed_exact" if git_blob_sha(data) == expected_blob else "unreviewed_bytes"
    finally:
        os.close(fd)


def inspect() -> dict:
    report = {
        "schema": "mojprop.owner_starter30_public_static.readonly.c122.v1",
        "read_only": True,
        "owner_identity_verified": False,
        "assets": {name: "unavailable" for name in REVIEWED_BLOBS},
        "all_three_reviewed_files_present": False,
        "contact_index_metadata_present": False,
        "http_public_delivery_proven": False,
        "email_lead_received": False,
        "database_accessed": False,
        "customer_data_accessed": False,
        "trx_payment_collected": False,
        "funded_prop_challenge_available": False,
        "no_payment_scope": True,
        "production_deployment_authorized": False,
        "new_cost_incurred": False,
    }
    try:
        if pwd.getpwuid(os.geteuid()).pw_name != OWNER:
            return report
        report["owner_identity_verified"] = True
        if set(REVIEWED_BLOBS) != {"index.html", "journal-template.csv", "journal-guide.txt"}:
            return report
        states = {
            name: inventory_one(STATIC_DIR / name, expected_blob=blob)
            for name, blob in REVIEWED_BLOBS.items()
        }
        report["assets"] = states
        report["all_three_reviewed_files_present"] = all(
            state == "reviewed_exact" for state in states.values()
        )
        contact_index = DOCROOT / "moj-prop" / "contact" / "index.html"
        report["contact_index_metadata_present"] = (
            inventory_one(contact_index, expected_blob="0" * 40) == "unreviewed_bytes"
        )
    except (OSError, ValueError, KeyError):
        pass
    return report


if __name__ == "__main__":
    print("MOJPROP_C122_STATIC_OWNER_READONLY=" +
          json.dumps(inspect(), sort_keys=True, separators=(",", ":")))
