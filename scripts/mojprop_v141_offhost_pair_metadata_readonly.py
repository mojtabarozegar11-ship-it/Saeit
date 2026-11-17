#!/usr/bin/env python3
"""READ-ONLY private VPS backup pair inventory for MOJ PROP release gating.

Names, ownership, lengths and limited JSON manifest metadata only.
Never decrypt ciphertext, open a private recovery key, stream SQL, log names,
upload files, inspect website user accounts, or authorize a deployment.
A producer's manifest is NOT a verified restoration receipt.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import stat
import time

BACKUP_SUBDIR = ".private-mojplaywin-offhost-backups"
NAME = re.compile(
    r"^(mojplaywin_[0-9]{8}T[0-9]{6}Z_[0-9a-f]{16})_(mysql|files)_gpgv2\."
    r"(gpg|manifest[.]json)$"
)
MAX_ENTRIES = 3000
MAX_MANIFEST = 32768
FRESH_SECONDS = 72 * 3600
MAX_SQL_BYTES = 48 * 1024**3
MAX_FILES_BYTES = 12 * 1024**3


def _private_regular(path: Path, uid: int):
    try:
        s = path.lstat()
        if not (stat.S_ISREG(s.st_mode) and s.st_uid == uid and
                not (s.st_mode & 0o177)):
            return None
        return s
    except OSError:
        return None


def _manifest_valid(path: Path, archive: Path, stem: str, kind: str, uid: int):
    st = _private_regular(path, uid)
    cipher = _private_regular(archive, uid)
    if (st is None or cipher is None or st.st_size < 20
            or st.st_size > MAX_MANIFEST or cipher.st_size <= 0):
        return False
    try:
        # Read only a *small manifest*, never ciphertext or recovery keys.
        with path.open("rb") as fp:
            raw = fp.read(MAX_MANIFEST + 1)
        if len(raw) != st.st_size:
            return False
        obj = json.loads(raw.decode("utf-8"))
        if type(obj) is not dict:
            return False
        max_plain = MAX_SQL_BYTES if kind == "mysql" else MAX_FILES_BYTES
        name = f"{stem}_{kind}_gpgv2.gpg"
        return all((
            obj.get("format") == "OpenPGP-AES256-GPGv2",
            obj.get("kind") == kind,
            obj.get("backup_set_stem") == stem,
            obj.get("explicit_backup_set_id") is True,
            obj.get("source_completion_footer_verified") is True,
            obj.get("ciphertext_roundtrip_integrity_verified") is True,
            obj.get("release_permitted") is False,
            obj.get("archive_name") == name,
            type(obj.get("encrypted_bytes")) is int,
            obj["encrypted_bytes"] == cipher.st_size,
            type(obj.get("plaintext_bytes")) is int,
            1024 <= obj["plaintext_bytes"] <= max_plain,
            type(obj.get("plaintext_sha256")) is str,
            re.fullmatch(r"[0-9a-f]{64}", obj["plaintext_sha256"]) is not None,
        ))
    except (OSError, ValueError, UnicodeError, TypeError, KeyError):
        return False


def inspect(home: Path | None = None, *, uid: int | None = None,
            now: float | None = None) -> dict:
    home = Path.home() if home is None else Path(home)
    uid = os.getuid() if uid is None else uid
    now = time.time() if now is None else now
    root = home / BACKUP_SUBDIR
    base = {
        "classification": "MOJPROP_OFFHOST_ENCRYPTED_PAIR_METADATA_READ_ONLY",
        "private_backup_directory_verified": False,
        "inventory_complete": False,
        "regular_file_count": 0,
        "partial_file_count": 0,
        "candidate_backup_set_count": 0,
        "complete_pair_with_consistent_manifest_count": 0,
        "fresh_pair_metadata_count": 0,
        "newest_complete_pair_age_hours": None,
        "ciphertext_bytes_read": False,
        "recovery_key_bytes_read": False,
        "database_rows_read": False,
        "full_backup_coverage_verified": False,
        "ciphertext_authenticated_independently": False,
        "isolated_restore_verified": False,
        "offhost_independent_device_verified": False,
        "paid_release_authorized": False,
    }
    try:
        base_stat = root.lstat()
        if not (stat.S_ISDIR(base_stat.st_mode) and
                base_stat.st_uid == uid and not (base_stat.st_mode & 0o077)):
            return base
        base["private_backup_directory_verified"] = True
        entries = {}
        count = 0
        with os.scandir(root) as iterator:
            for entry in iterator:
                count += 1
                if count > MAX_ENTRIES:
                    return base
                try:
                    info = entry.stat(follow_symlinks=False)
                    if not stat.S_ISREG(info.st_mode):
                        continue
                    base["regular_file_count"] += 1
                    if entry.name.endswith(".partial"):
                        base["partial_file_count"] += 1
                    match = NAME.fullmatch(entry.name)
                    if match is not None:
                        stem, kind, ext = match.groups()
                        entries.setdefault(stem, {})[(kind, ext)] = root / entry.name
                except OSError:
                    return base
        base["inventory_complete"] = True
        base["candidate_backup_set_count"] = len(entries)
        best_age = None
        for stem, files in entries.items():
            ready = True
            stamps = []
            for kind in ("mysql", "files"):
                a = files.get((kind, "gpg"))
                m = files.get((kind, "manifest.json"))
                if a is None or m is None or not _manifest_valid(m, a, stem, kind, uid):
                    ready = False
                    break
                stamps.extend((a.lstat().st_mtime, m.lstat().st_mtime))
            if ready:
                base["complete_pair_with_consistent_manifest_count"] += 1
                age = max(0, (now - min(stamps)) / 3600)
                best_age = age if best_age is None else min(best_age, age)
                if age <= FRESH_SECONDS / 3600:
                    base["fresh_pair_metadata_count"] += 1
        if best_age is not None:
            base["newest_complete_pair_age_hours"] = round(best_age, 2)
        return base
    except (OSError, ValueError, OverflowError):
        return base


if __name__ == "__main__":
    try:
        print(json.dumps(inspect(), sort_keys=True))
    except Exception:
        print(json.dumps({"classification": "MOJPROP_BACKUP_METADATA_UNAVAILABLE",
                          "paid_release_authorized": False}))
        raise SystemExit(1)
