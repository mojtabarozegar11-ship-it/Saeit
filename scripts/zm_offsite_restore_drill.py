#!/usr/bin/env python3
"""Verify a Zomorod business DB GitHub artifact by restoring it offline.

This tool never connects to production and never retains decrypted data. The
password-protected RSA private key stays on the owner's isolated workstation,
not in GitHub Secrets, Actions, a server, or a chat.
"""
import argparse
import hashlib
import os
from pathlib import Path
import re
import sqlite3
import stat
import sys
import tempfile
from urllib.parse import quote
import zipfile

from f01_encrypted_stream_v1 import decrypt

CIPHER = "business.sqlite3.f01enc"
MANIFEST = "manifest.txt"
FORMAT = "F01ENC-RSA3072-AES256GCM-V1"
MAX_ZIP_BYTES = 250 * 1024 * 1024
MAX_CIPHER_BYTES = 210 * 1024 * 1024
REQUIRED_TABLES = {"users", "journal_entries", "journal_lines", "invoices"}


def digest(path):
    result = hashlib.sha256()
    with path.open("rb") as source:
        for part in iter(lambda: source.read(1024 * 1024), b""):
            result.update(part)
    return result.hexdigest()


def private_file(path):
    if path.is_symlink() or not path.is_file():
        raise ValueError("PRIVATE_FILE_INVALID")
    if stat.S_IMODE(path.stat().st_mode) & 0o077:
        raise PermissionError("PRIVATE_FILE_PERMISSIONS")


def read_artifact(archive, directory):
    if archive.is_symlink() or not archive.is_file():
        raise ValueError("ARTIFACT_INVALID")
    if not 1 <= archive.stat().st_size <= MAX_ZIP_BYTES:
        raise ValueError("ARTIFACT_SIZE")
    with zipfile.ZipFile(archive, "r") as bundle:
        infos = bundle.infolist()
        if len(infos) != 2 or {z.filename for z in infos} != {CIPHER, MANIFEST}:
            raise ValueError("ARTIFACT_ENTRIES")
        for entry in infos:
            if entry.is_dir() or stat.S_ISLNK(entry.external_attr >> 16):
                raise ValueError("ARTIFACT_LINK_OR_DIRECTORY")
        size = {z.filename: z.file_size for z in infos}
        if not 1 <= size[CIPHER] <= MAX_CIPHER_BYTES or not 1 <= size[MANIFEST] <= 1024:
            raise ValueError("ARTIFACT_ENTRY_SIZE")
        raw_manifest = bundle.read(MANIFEST).decode("ascii")
        lines = raw_manifest.splitlines()
        if len(lines) != 2 or len(set(lines)) != 2:
            raise ValueError("ARTIFACT_MANIFEST_SHAPE")
        fields = {}
        for line in lines:
            if line.count("=") != 1:
                raise ValueError("ARTIFACT_MANIFEST_FORMAT")
            name, value = line.split("=", 1)
            if name in fields:
                raise ValueError("ARTIFACT_MANIFEST_DUPLICATE")
            fields[name] = value
        if set(fields) != {"format", "snapshot_sha256"} or fields["format"] != FORMAT:
            raise ValueError("ARTIFACT_MANIFEST_SCHEMA")
        if not re.fullmatch(r"[a-f0-9]{64}", fields["snapshot_sha256"]):
            raise ValueError("ARTIFACT_MANIFEST_SHA")
        cipher_path = directory / CIPHER
        with bundle.open(CIPHER, "r") as source, cipher_path.open("xb") as output:
            os.chmod(cipher_path, 0o600)
            while True:
                chunk = source.read(1024 * 1024)
                if not chunk:
                    break
                output.write(chunk)
        if cipher_path.stat().st_size != size[CIPHER]:
            raise ValueError("ARTIFACT_COPY_SIZE")
    return cipher_path, fields["snapshot_sha256"]


def verify_sqlite(path):
    uri = "file:" + quote(str(path), safe="/") + "?mode=ro&immutable=1"
    with sqlite3.connect(uri, uri=True, timeout=10) as db:
        db.execute("PRAGMA query_only=ON")
        if db.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise ValueError("SQLITE_INTEGRITY")
        tables = {
            row[0]
            for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        if not REQUIRED_TABLES.issubset(tables):
            raise ValueError("SQLITE_REQUIRED_TABLES")
        if db.execute("SELECT COUNT(*) FROM users").fetchone()[0] < 1:
            raise ValueError("SQLITE_NO_USERS")
        for name in ("journal_entries", "journal_lines", "invoices"):
            db.execute("SELECT COUNT(*) FROM " + name).fetchone()
    return len(tables)


def run(archive, private_key, passphrase_file, scratch_root=None, expected_sha=None):
    private_file(private_key)
    private_file(passphrase_file)
    if scratch_root is not None:
        if not scratch_root.is_dir() or scratch_root.is_symlink():
            raise ValueError("SCRATCH_ROOT_INVALID")
        if stat.S_IMODE(scratch_root.stat().st_mode) & 0o077:
            raise PermissionError("SCRATCH_ROOT_PERMISSIONS")
    with tempfile.TemporaryDirectory(prefix="zm-offline-restore-", dir=scratch_root) as d:
        directory = Path(d)
        cipher_path, manifest_sha = read_artifact(archive, directory)
        if expected_sha is not None and expected_sha != manifest_sha:
            raise ValueError("EXPECTED_SNAPSHOT_MISMATCH")
        restored_path = directory / "restored-business.sqlite3"
        password = passphrase_file.read_bytes().strip()
        if not password:
            raise ValueError("EMPTY_PASSPHRASE")
        decrypt(cipher_path, restored_path, private_key, password)
        os.chmod(restored_path, 0o600)
        if digest(restored_path) != manifest_sha:
            raise ValueError("DECRYPTED_SHA256_MISMATCH")
        table_count = verify_sqlite(restored_path)
    # TemporaryDirectory has removed both ciphertext and plaintext before success.
    return {"verified": True, "f01_authenticated": True,
            "manifest_sha256_matched": True, "sqlite_integrity": "ok",
            "required_tables_present": True, "table_count": table_count,
            "plaintext_retained": False, "production_touched": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact-zip", type=Path, required=True)
    parser.add_argument("--private-key", type=Path, required=True)
    parser.add_argument("--passphrase-file", type=Path, required=True)
    parser.add_argument("--scratch-root", type=Path, default=None,
                        help="Existing owner-private directory on an isolated encrypted volume")
    parser.add_argument("--expected-snapshot-sha256", default=None)
    args = parser.parse_args()
    if args.expected_snapshot_sha256 is not None and not re.fullmatch(
        r"[a-f0-9]{64}", args.expected_snapshot_sha256
    ):
        parser.error("Expected snapshot SHA-256 must be 64 lowercase hex digits")
    try:
        result = run(args.artifact_zip, args.private_key, args.passphrase_file,
                     args.scratch_root, args.expected_snapshot_sha256)
        print("OFFSITE_RESTORE_VERIFIED=true")
        for name, value in result.items():
            print(f"OFFSITE_{name.upper()}={str(value).lower()}")
        return 0
    except Exception as exc:
        # Never print path names, database contents, plaintext, or key material.
        print("OFFSITE_RESTORE_VERIFIED=false", file=sys.stderr)
        print("OFFSITE_RESTORE_ERROR_CLASS=" + type(exc).__name__, file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
