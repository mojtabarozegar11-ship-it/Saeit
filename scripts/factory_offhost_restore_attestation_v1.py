#!/usr/bin/env python3
"""Independent-host restore rehearsal and signed evidence validation.

The off-host command *does not sign*. A separately administered private key
must sign the exact receipt bytes after rehearsal; no private key belongs on
the factory VPS, in GitHub, or in the generated checkpoint.
"""

from __future__ import annotations

import argparse
from contextlib import closing
from datetime import datetime, timezone, timedelta
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import sqlite3
import stat
import subprocess
import tarfile
import tempfile

from factory_private_checkpoint_v1 import ARCHIVE, DB_COPY, MANIFEST, verify as verify_checkpoint


SCHEMA = "saeit.factory.offhost-restore-receipt.v1"
MAX_RECEIPT = 64 * 1024
MAX_SIGNATURE = 4096
MAX_KEY = 16 * 1024
MAX_RECEIPT_AGE = timedelta(hours=24)


def _hash_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _no_symlink_path(path: Path) -> None:
    if any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError("OFFHOST_SYMLINK_PATH")


def _read_bounded(path: Path, limit: int) -> bytes:
    _no_symlink_path(path)
    mode = path.lstat().st_mode
    if not stat.S_ISREG(mode) or not 0 < path.stat().st_size <= limit:
        raise ValueError("OFFHOST_INVALID_INPUT_FILE")
    data = path.read_bytes()
    if not 0 < len(data) <= limit:
        raise ValueError("OFFHOST_INVALID_INPUT_SIZE")
    return data


def _trusted_admin_key(path: Path) -> None:
    _read_bounded(path, MAX_KEY)
    for entry in (path, path.parent, path.parent.parent):
        info = entry.stat()
        if info.st_uid != 0 or info.st_mode & 0o022:
            raise ValueError("OFFHOST_KEY_NOT_ADMIN_PROTECTED")


def _manifest_fingerprint(checkpoint: Path) -> tuple[dict, str]:
    manifest = verify_checkpoint(checkpoint)
    raw = _read_bounded(checkpoint / MANIFEST, 8 * 1024 * 1024)
    return manifest, _hash_bytes(raw)


def rehearse(checkpoint: Path, backup_host_id: str, receipt_path: Path) -> dict:
    """Physically reconstruct backup data into an isolated temporary directory."""
    if (not backup_host_id or len(backup_host_id) > 128
            or not all(c.isascii() and (c.isalnum() or c in ".-_") for c in backup_host_id)):
        raise ValueError("OFFHOST_INVALID_HOST_ID")
    _no_symlink_path(receipt_path)
    if receipt_path.exists() or receipt_path.is_symlink():
        raise ValueError("OFFHOST_RECEIPT_ALREADY_EXISTS")
    if checkpoint == receipt_path.parent or checkpoint in receipt_path.parents:
        raise ValueError("OFFHOST_RECEIPT_INSIDE_CHECKPOINT")
    if not receipt_path.parent.is_dir():
        raise ValueError("OFFHOST_RECEIPT_PARENT_MISSING")
    manifest, fingerprint = _manifest_fingerprint(checkpoint)
    with tempfile.TemporaryDirectory(prefix="factory-restore-rehearsal-") as name:
        destination = Path(name)
        state = destination / "private-restored"
        state.mkdir(mode=0o700)
        restored = 0
        restored_bytes = 0
        with tarfile.open(checkpoint / ARCHIVE, "r:gz") as archive:
            for member in archive:
                if not member.isfile():
                    raise ValueError("OFFHOST_UNSAFE_ARCHIVE_MEMBER")
                rel = PurePosixPath(member.name)
                if rel.is_absolute() or ".." in rel.parts:
                    raise ValueError("OFFHOST_UNSAFE_RELATIVE_PATH")
                target = state.joinpath(*rel.parts)
                target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
                digest = hashlib.sha256()
                with archive.extractfile(member) as reader, target.open("xb") as writer:
                    for piece in iter(lambda: reader.read(1024 * 1024), b""):
                        digest.update(piece)
                        writer.write(piece)
                target.chmod(0o600)
                file_record = manifest["files"][restored]
                if (digest.hexdigest() != file_record["sha256"]
                        or target.stat().st_size != file_record["size"]
                        or member.name != file_record["path"]):
                    raise ValueError("OFFHOST_RESTORED_DATA_MISMATCH")
                restored += 1
                restored_bytes += member.size
        if restored != manifest["file_count"] or restored_bytes != manifest["uncompressed_bytes"]:
            raise ValueError("OFFHOST_RESTORED_FILE_COUNT_MISMATCH")
        restored_db = destination / "restored.sqlite3"
        shutil.copyfile(checkpoint / DB_COPY, restored_db)
        restored_db.chmod(0o600)
        if _hash_bytes(restored_db.read_bytes()) != manifest["db_sha256"]:
            raise ValueError("OFFHOST_RESTORED_DB_MISMATCH")
        with closing(sqlite3.connect(restored_db.as_uri() + "?mode=ro", uri=True)) as database:
            if database.execute("PRAGMA integrity_check").fetchone() != ("ok",):
                raise ValueError("OFFHOST_RESTORED_DB_INTEGRITY_FAILURE")
            database.execute("SELECT COUNT(*) FROM sqlite_master").fetchone()
    receipt = {
        "schema": SCHEMA,
        "status": "restored_and_verified_offhost",
        "backup_host_id": backup_host_id,
        "checkpoint_manifest_sha256": fingerprint,
        "checkpoint_archive_sha256": manifest["archive_sha256"],
        "checkpoint_db_sha256": manifest["db_sha256"],
        "restored_file_count": restored,
        "restored_uncompressed_bytes": restored_bytes,
        "restore_verified_utc": datetime.now(timezone.utc).isoformat(),
        "source_offhost_verified_claim": True,
        "auto_restore_authorized": False,
    }
    with receipt_path.open("x", encoding="utf-8") as stream:
        json.dump(receipt, stream, sort_keys=True, separators=(",", ":"))
        stream.write("\n")
    receipt_path.chmod(0o600)
    return receipt


def verify_signed_receipt(
    checkpoint: Path,
    receipt_path: Path,
    signature_path: Path,
    public_key_path: Path,
    expected_host_id: str,
    *,
    require_root_key: bool = True,
) -> dict:
    """Verify exact signed bytes and their binding to the local checkpoint."""
    if require_root_key:
        _trusted_admin_key(public_key_path)
    else:
        _read_bounded(public_key_path, MAX_KEY)
    receipt_bytes = _read_bounded(receipt_path, MAX_RECEIPT)
    _read_bounded(signature_path, MAX_SIGNATURE)
    result = subprocess.run(
        ["openssl", "dgst", "-sha256", "-verify", str(public_key_path),
         "-signature", str(signature_path)],
        input=receipt_bytes, capture_output=True, timeout=8, check=False,
    )
    if result.returncode != 0:
        raise ValueError("OFFHOST_RECEIPT_SIGNATURE_INVALID")
    receipt = json.loads(receipt_bytes.decode("utf-8"))
    if not isinstance(receipt, dict):
        raise ValueError("OFFHOST_RECEIPT_NOT_OBJECT")
    manifest, fingerprint = _manifest_fingerprint(checkpoint)
    if (receipt.get("schema") != SCHEMA
            or receipt.get("status") != "restored_and_verified_offhost"
            or receipt.get("backup_host_id") != expected_host_id
            or receipt.get("checkpoint_manifest_sha256") != fingerprint
            or receipt.get("checkpoint_archive_sha256") != manifest["archive_sha256"]
            or receipt.get("checkpoint_db_sha256") != manifest["db_sha256"]
            or receipt.get("restored_file_count") != manifest["file_count"]
            or receipt.get("restored_uncompressed_bytes") != manifest["uncompressed_bytes"]
            or receipt.get("source_offhost_verified_claim") is not True
            or receipt.get("auto_restore_authorized") is not False):
        raise ValueError("OFFHOST_RECEIPT_CONTENT_MISMATCH")
    try:
        timestamp = datetime.fromisoformat(receipt["restore_verified_utc"])
    except (TypeError, ValueError, KeyError):
        raise ValueError("OFFHOST_RECEIPT_TIME_INVALID") from None
    if timestamp.tzinfo is None:
        raise ValueError("OFFHOST_RECEIPT_TIME_INVALID")
    age = datetime.now(timezone.utc) - timestamp
    if not -timedelta(minutes=5) <= age <= MAX_RECEIPT_AGE:
        raise ValueError("OFFHOST_RECEIPT_STALE_OR_FUTURE")
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="operation", required=True)
    offhost = commands.add_parser("rehearse")
    offhost.add_argument("--checkpoint", type=Path, required=True)
    offhost.add_argument("--host-id", required=True)
    offhost.add_argument("--receipt", type=Path, required=True)
    check = commands.add_parser("verify")
    check.add_argument("--checkpoint", type=Path, required=True)
    check.add_argument("--receipt", type=Path, required=True)
    check.add_argument("--signature", type=Path, required=True)
    check.add_argument("--public-key", type=Path, required=True)
    check.add_argument("--expected-host-id", required=True)
    args = parser.parse_args()
    if args.operation == "rehearse":
        receipt = rehearse(args.checkpoint, args.host_id, args.receipt)
        print(f"OFFHOST_RESTORATION_REHEARSED=PASS FILES={receipt['restored_file_count']}")
        print("OFFHOST_RECEIPT_UNSIGNED=YES SIGN_EXTERNALLY_WITH_PROTECTED_KEY")
    else:
        receipt = verify_signed_receipt(
            args.checkpoint, args.receipt, args.signature, args.public_key,
            args.expected_host_id
        )
        print(f"OFFHOST_SIGNED_RESTORE_VERIFIED=PASS HOST={receipt['backup_host_id']}")


if __name__ == "__main__":
    main()
