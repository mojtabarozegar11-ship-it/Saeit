#!/usr/bin/env python3
"""Metadata-only GPGv2 MojPlayWin backup pair inventory on the existing VPS.

Never reads archives, manifests, recovery keys, SQL, customer data, env files,
or private paths into public output. Does not create/delete/copy any file.
A candidate pair is NOT an authenticated backup and is NOT release approval.
"""
from __future__ import annotations

import json
import os
import re
import stat
from itertools import islice
from pathlib import Path

MAX_ENTRIES = 2048
FILE_NAME = re.compile(
    r"^(mojplaywin_(?:20261017|[0-9]{8}T[0-9]{6}Z_[0-9a-f]{16}))_"
    r"(mysql|files)_gpgv2\.(gpg|manifest\.json)$"
)


def _private_directory(path: Path, uid: int) -> bool:
    try:
        st = path.lstat()
        return stat.S_ISDIR(st.st_mode) and st.st_uid == uid and (st.st_mode & 0o077) == 0
    except OSError:
        return False


def _private_regular(path: Path, uid: int, exact_bytes=None) -> bool:
    try:
        st = path.lstat()
        return (
            stat.S_ISREG(st.st_mode)
            and st.st_uid == uid
            and (st.st_mode & 0o177) == 0
            and st.st_size > 0
            and (exact_bytes is None or st.st_size == exact_bytes)
        )
    except OSError:
        return False


def inspect(home: Path | None = None, uid: int | None = None) -> dict:
    home = Path.home() if home is None else Path(home)
    uid = os.geteuid() if uid is None else uid
    root = home / ".private-mojplaywin-offhost-backups"
    keydir = home / ".config" / "mojplaywin-backup-recovery"
    root_safe = _private_directory(root, uid)
    keydir_safe = _private_directory(keydir, uid)
    key_safe = keydir_safe and _private_regular(keydir / "recovery-key.bin", uid, exact_bytes=32)
    scanned = 0
    truncated = False
    ignored_unsafe = 0
    # Map is in-memory only; never print filenames, stems, paths or file hashes.
    grouped: dict[str, set[str]] = {}
    if root_safe:
        try:
            for entry in islice(root.iterdir(), MAX_ENTRIES + 1):
                scanned += 1
                if scanned > MAX_ENTRIES:
                    truncated = True
                    break
                match = FILE_NAME.fullmatch(entry.name)
                if match is None:
                    continue
                if not _private_regular(entry, uid):
                    ignored_unsafe += 1
                    continue
                stem, kind, format_name = match.groups()
                grouped.setdefault(stem, set()).add(kind + ":" + format_name)
        except OSError:
            truncated = True

    required = {"mysql:gpg", "mysql:manifest.json", "files:gpg", "files:manifest.json"}
    candidate_count = sum(required <= present for present in grouped.values()) if not truncated else 0
    return {
        "classification": "READ_ONLY_EXISTING_MPW_ENCRYPTED_BACKUP_METADATA",
        "private_backup_directory_owner_only": root_safe,
        "recovery_key_directory_owner_only": keydir_safe,
        "recovery_key_existing_32byte_owner_only": key_safe,
        "scanned_entries_capped": min(scanned, MAX_ENTRIES),
        "inventory_complete": root_safe and not truncated,
        "insecure_or_nonregular_matching_files_ignored": ignored_unsafe,
        "candidate_complete_same_id_gpgv2_pair_count": candidate_count,
        "candidate_archives_authenticity_verified": False,
        "source_completion_and_database_consistency_verified": False,
        "decryption_performed": False,
        "isolated_restore_performed": False,
        "private_identifiers_or_paths_printed": False,
        "file_contents_or_recovery_key_read": False,
        "files_modified": False,
        "release_permitted": False,
        "important_limitation": (
            "Metadata matching four owner-only files does not verify their ciphertext, "
            "contents, same-customer recovery coverage, historical purchase ledger or restorable database."
        ),
    }


if __name__ == "__main__":
    print(json.dumps(inspect(), sort_keys=True))
