#!/usr/bin/env python3
"""Bind independent encrypted-copy recovery to a signed, replay-resistant receipt.

The recovery host alone runs `rehearse-sealed`. A separate administrator signs
the resulting receipt bytes. The VPS runs `verify-signed` with public signing
key, original local checkpoint and original ciphertext. No transfer, signing,
factory activation, key generation or production state mutation is performed.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
import tempfile

from factory_private_checkpoint_v1 import verify as verify_checkpoint
from factory_checkpoint_sealed_transport_v1 import unseal
from factory_offhost_restore_attestation_v1 import (
    _no_symlink_path,
    _read_bounded,
    _trusted_admin_key,
    rehearse,
    MAX_KEY,
    MAX_RECEIPT,
    MAX_RECEIPT_AGE,
    MAX_SIGNATURE,
)


SCHEMA = "saeit.factory.offhost-sealed-recovery-receipt.v1"
CHUNK = 1024 * 1024
FIELDS = frozenset({
    "schema", "status", "backup_host_id", "ciphertext_sha256",
    "ciphertext_bytes", "recipient_public_key_sha256",
    "checkpoint_manifest_sha256", "checkpoint_archive_sha256",
    "checkpoint_db_sha256", "restored_file_count",
    "restored_uncompressed_bytes", "restore_verified_utc",
    "source_offhost_verified_claim", "auto_restore_authorized",
})


def _digest(path: Path) -> tuple[str, int]:
    _no_symlink_path(path)
    data = path.stat()
    if not stat.S_ISREG(data.st_mode) or data.st_size <= 0:
        raise ValueError("SEALED_RECEIPT_BUNDLE_UNSAFE")
    hash_value = hashlib.sha256()
    with path.open("rb") as reader:
        for block in iter(lambda: reader.read(CHUNK), b""):
            hash_value.update(block)
    return hash_value.hexdigest(), data.st_size


def _private_directory(path: Path) -> None:
    _no_symlink_path(path)
    data = path.stat()
    if (not stat.S_ISDIR(data.st_mode) or data.st_uid != os.getuid()
            or data.st_mode & 0o077):
        raise ValueError("SEALED_RECEIPT_WORKDIR_NOT_PRIVATE")


def rehearse_sealed(
    encrypted_bundle: Path,
    decryption_private_key: Path,
    recipient_pin: str,
    backup_host_id: str,
    work_parent: Path,
    receipt_path: Path,
) -> dict:
    """Recover ciphertext and independently reconstruct all factory private data."""
    _private_directory(work_parent)
    _private_directory(receipt_path.parent)
    _no_symlink_path(receipt_path)
    if receipt_path.exists() or receipt_path.is_symlink():
        raise ValueError("SEALED_RECEIPT_ALREADY_EXISTS")
    first_digest = _digest(encrypted_bundle)
    with tempfile.TemporaryDirectory(prefix=".factory-offhost-receipt-", dir=work_parent) as folder:
        scratch = Path(folder)
        restored_checkpoint = scratch / "checkpoint"
        state = unseal(
            encrypted_bundle, decryption_private_key, recipient_pin, restored_checkpoint,
        )
        if state.get("checkpoint_verified") is not True:
            raise ValueError("SEALED_RECEIPT_UNSEAL_NOT_VERIFIED")
        rehearsal = rehearse(
            restored_checkpoint, backup_host_id, scratch / "intermediate-rehearsal.json",
        )
        if _digest(encrypted_bundle) != first_digest:
            raise ValueError("SEALED_RECEIPT_BUNDLE_CHANGED_DURING_RESTORE")
    receipt = {
        "schema": SCHEMA,
        "status": "encrypted_offhost_restored_and_rehearsed",
        "backup_host_id": backup_host_id,
        "ciphertext_sha256": first_digest[0],
        "ciphertext_bytes": first_digest[1],
        "recipient_public_key_sha256": recipient_pin,
        "checkpoint_manifest_sha256": rehearsal["checkpoint_manifest_sha256"],
        "checkpoint_archive_sha256": rehearsal["checkpoint_archive_sha256"],
        "checkpoint_db_sha256": rehearsal["checkpoint_db_sha256"],
        "restored_file_count": rehearsal["restored_file_count"],
        "restored_uncompressed_bytes": rehearsal["restored_uncompressed_bytes"],
        "restore_verified_utc": rehearsal["restore_verified_utc"],
        "source_offhost_verified_claim": True,
        "auto_restore_authorized": False,
    }
    fd = os.open(receipt_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as stream:
        json.dump(receipt, stream, sort_keys=True, separators=(",", ":"))
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    return receipt


def verify_signed_sealed_receipt(
    checkpoint: Path,
    encrypted_bundle: Path,
    receipt_path: Path,
    signature_path: Path,
    independent_signing_public_key: Path,
    expected_host_id: str,
    expected_recipient_pin: str,
    *,
    require_admin_key: bool = True,
) -> dict:
    """On the VPS, validate the signed evidence against BOTH local artifacts."""
    if require_admin_key:
        _trusted_admin_key(independent_signing_public_key)
    else:
        _read_bounded(independent_signing_public_key, MAX_KEY)
    raw = _read_bounded(receipt_path, MAX_RECEIPT)
    _read_bounded(signature_path, MAX_SIGNATURE)
    signature = subprocess.run(
        ["openssl", "dgst", "-sha256", "-verify", str(independent_signing_public_key),
         "-signature", str(signature_path)],
        input=raw, capture_output=True, timeout=8, check=False,
    )
    if signature.returncode:
        raise ValueError("SEALED_RECEIPT_SIGNATURE_INVALID")
    try:
        receipt = json.loads(raw)
    except (ValueError, UnicodeDecodeError):
        raise ValueError("SEALED_RECEIPT_NOT_JSON") from None
    if not isinstance(receipt, dict) or set(receipt) != FIELDS:
        raise ValueError("SEALED_RECEIPT_FIELDS_INVALID")
    manifest = verify_checkpoint(checkpoint)
    manifest_sha = _digest(checkpoint / "manifest.json")[0]
    bundle_hash, bundle_size = _digest(encrypted_bundle)
    if (
        receipt["schema"] != SCHEMA
        or receipt["status"] != "encrypted_offhost_restored_and_rehearsed"
        or receipt["backup_host_id"] != expected_host_id
        or receipt["recipient_public_key_sha256"] != expected_recipient_pin
        or receipt["checkpoint_manifest_sha256"] != manifest_sha
        or receipt["checkpoint_archive_sha256"] != manifest["archive_sha256"]
        or receipt["checkpoint_db_sha256"] != manifest["db_sha256"]
        or receipt["restored_file_count"] != manifest["file_count"]
        or receipt["restored_uncompressed_bytes"] != manifest["uncompressed_bytes"]
        or receipt["ciphertext_sha256"] != bundle_hash
        or receipt["ciphertext_bytes"] != bundle_size
        or receipt["source_offhost_verified_claim"] is not True
        or receipt["auto_restore_authorized"] is not False
    ):
        raise ValueError("SEALED_RECEIPT_CONTENT_MISMATCH")
    try:
        stamp = datetime.fromisoformat(receipt["restore_verified_utc"])
    except (KeyError, ValueError, TypeError):
        raise ValueError("SEALED_RECEIPT_TIME_INVALID") from None
    if stamp.tzinfo is None:
        raise ValueError("SEALED_RECEIPT_TIME_INVALID")
    age = datetime.now(timezone.utc) - stamp
    if not -timedelta(minutes=5) <= age <= MAX_RECEIPT_AGE:
        raise ValueError("SEALED_RECEIPT_STALE_OR_FUTURE")
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="operation", required=True)
    proof = commands.add_parser("rehearse-sealed")
    proof.add_argument("--bundle", type=Path, required=True)
    proof.add_argument("--private-key", type=Path, required=True)
    proof.add_argument("--recipient-pin", required=True)
    proof.add_argument("--backup-host-id", required=True)
    proof.add_argument("--work-parent", type=Path, required=True)
    proof.add_argument("--receipt", type=Path, required=True)
    check = commands.add_parser("verify-signed")
    check.add_argument("--checkpoint", type=Path, required=True)
    check.add_argument("--bundle", type=Path, required=True)
    check.add_argument("--receipt", type=Path, required=True)
    check.add_argument("--signature", type=Path, required=True)
    check.add_argument("--signer-public-key", type=Path, required=True)
    check.add_argument("--expected-host-id", required=True)
    check.add_argument("--recipient-pin", required=True)
    args = parser.parse_args()
    if args.operation == "rehearse-sealed":
        receipt = rehearse_sealed(
            args.bundle, args.private_key, args.recipient_pin,
            args.backup_host_id, args.work_parent, args.receipt,
        )
        print(f"SEALED_OFFHOST_REHEARSAL=PASS BYTES={receipt['ciphertext_bytes']}")
        print("SEALED_RECEIPT_UNSIGNED=YES SIGN_ON_INDEPENDENT_HOST")
    else:
        receipt = verify_signed_sealed_receipt(
            args.checkpoint, args.bundle, args.receipt, args.signature,
            args.signer_public_key, args.expected_host_id, args.recipient_pin,
        )
        print(f"SEALED_SIGNED_RECOVERY=PASS HOST={receipt['backup_host_id']}")


if __name__ == "__main__":
    main()
