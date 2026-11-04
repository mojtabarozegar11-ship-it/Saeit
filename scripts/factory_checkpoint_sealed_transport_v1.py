#!/usr/bin/env python3
"""Fail-closed envelope encryption for a verified factory checkpoint.

Seal runs on the factory VPS with ONLY the independently controlled receiver's
pinned RSA public key. Unseal runs on a separate recovery host with the private
key. This script never moves data across the network, creates keys, or signs
off-host restore receipts; it does not authorize factory activation.

Requires the `cryptography` package on each host, otherwise it fails closed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import struct
import tarfile
import tempfile

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

from factory_private_checkpoint_v1 import ARCHIVE, DB_COPY, MANIFEST, verify


SCHEMA = "saeit.factory.encrypted-checkpoint.v1"
MAGIC = b"SAEIT_FACTORY_SEALED_V1\n"
MAX_HEADER = 4096
MAX_BUNDLE = 6 * 1024**3
MAX_PEM = 16 * 1024
MAX_MANIFEST = 8 * 1024 * 1024
NAMES = (MANIFEST, DB_COPY, ARCHIVE)
CHUNK = 1024 * 1024


def _no_symlinks(path: Path) -> None:
    if any(part.is_symlink() for part in (path, *path.parents)):
        raise ValueError("SEALED_SYMLINK_PATH")


def _private_parent(path: Path) -> None:
    _no_symlinks(path)
    parent = path.parent
    st = parent.stat()
    if (not stat.S_ISDIR(st.st_mode) or st.st_uid != os.getuid()
            or st.st_mode & 0o077):
        raise ValueError("SEALED_PARENT_NOT_PRIVATE")


def _read_pem(path: Path) -> bytes:
    _no_symlinks(path)
    st = path.stat()
    if not stat.S_ISREG(st.st_mode) or not 1 <= st.st_size <= MAX_PEM:
        raise ValueError("SEALED_KEY_FILE_UNSAFE")
    return path.read_bytes()


def _fingerprint(public: rsa.RSAPublicKey) -> str:
    der = public.public_bytes(
        serialization.Encoding.DER,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    return hashlib.sha256(der).hexdigest()


def _trusted_public_key(
    path: Path, expected_fingerprint: str, *, require_admin_key: bool = True,
) -> rsa.RSAPublicKey:
    if require_admin_key:
        for part in (path, path.parent):
            st = part.stat()
            if st.st_uid != 0 or st.st_mode & 0o022:
                raise ValueError("SEALED_PUBLIC_KEY_NOT_ADMIN_PROTECTED")
    key = serialization.load_pem_public_key(_read_pem(path))
    if not isinstance(key, rsa.RSAPublicKey) or key.key_size < 3072:
        raise ValueError("SEALED_RECIPIENT_KEY_UNSUPPORTED")
    if len(expected_fingerprint) != 64 or _fingerprint(key) != expected_fingerprint:
        raise ValueError("SEALED_RECIPIENT_PIN_MISMATCH")
    return key


def _trusted_private_key(path: Path) -> rsa.RSAPrivateKey:
    st = path.stat()
    if st.st_uid != os.getuid() or st.st_mode & 0o077:
        raise ValueError("SEALED_PRIVATE_KEY_PERMISSIONS")
    key = serialization.load_pem_private_key(_read_pem(path), password=None)
    if not isinstance(key, rsa.RSAPrivateKey) or key.key_size < 3072:
        raise ValueError("SEALED_PRIVATE_KEY_UNSUPPORTED")
    return key


def _digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(CHUNK), b""):
            digest.update(chunk)
    return digest.hexdigest()


class _SealingWriter:
    def __init__(self, output, encryptor):
        self.output = output
        self.encryptor = encryptor

    def write(self, data: bytes) -> int:
        if data:
            self.output.write(self.encryptor.update(data))
        return len(data)


def seal(
    checkpoint: Path, public_key_path: Path, pinned_fingerprint: str,
    destination: Path, *, require_admin_key: bool = True,
) -> dict:
    """Write ciphertext only, using atomic no-clobber publication."""
    _private_parent(destination)
    if destination.exists() or destination.is_symlink():
        raise ValueError("SEALED_DESTINATION_EXISTS")
    manifest = verify(checkpoint)
    public = _trusted_public_key(
        public_key_path, pinned_fingerprint, require_admin_key=require_admin_key,
    )
    session_key = os.urandom(32)
    nonce = os.urandom(12)
    wrapped = public.encrypt(
        session_key,
        padding.OAEP(mgf=padding.MGF1(algorithm=hashes.SHA256()),
                     algorithm=hashes.SHA256(), label=None),
    )
    header = {
        "schema": SCHEMA,
        "aead": "AES-256-GCM",
        "wrap": "RSA-OAEP-SHA256",
        "public_key_sha256": pinned_fingerprint,
        "nonce_hex": nonce.hex(),
        "wrapped_key_hex": wrapped.hex(),
    }
    header_bytes = json.dumps(header, sort_keys=True, separators=(",", ":")).encode("utf-8")
    if len(header_bytes) > MAX_HEADER:
        raise ValueError("SEALED_HEADER_TOO_LARGE")
    prefix = MAGIC + struct.pack(">I", len(header_bytes)) + header_bytes
    encryptor = Cipher(algorithms.AES(session_key), modes.GCM(nonce)).encryptor()
    encryptor.authenticate_additional_data(prefix)
    fd, temp_name = tempfile.mkstemp(prefix=".sealed-incomplete-", dir=destination.parent)
    temp = Path(temp_name)
    try:
        with os.fdopen(fd, "wb") as output:
            os.fchmod(output.fileno(), 0o600)
            output.write(prefix)
            writer = _SealingWriter(output, encryptor)
            with tarfile.open(fileobj=writer, mode="w|", format=tarfile.USTAR_FORMAT) as archive:
                for name in NAMES:
                    source = checkpoint / name
                    _no_symlinks(source)
                    with source.open("rb") as stream:
                        before = os.fstat(stream.fileno())
                        if not stat.S_ISREG(before.st_mode):
                            raise ValueError("SEALED_SOURCE_NOT_REGULAR")
                        member = tarfile.TarInfo(name)
                        member.size = before.st_size
                        member.mode = 0o600
                        member.mtime = 0
                        archive.addfile(member, stream)
                        after = os.fstat(stream.fileno())
                        if ((before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns)
                                != (after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns)):
                            raise ValueError("SEALED_SOURCE_CHANGED")
                    expected = (
                        manifest["db_sha256"] if name == DB_COPY else
                        manifest["archive_sha256"] if name == ARCHIVE else None
                    )
                    if expected and _digest(source) != expected:
                        raise ValueError("SEALED_SOURCE_CHANGED")
                    if name == MANIFEST and source.stat().st_size > MAX_MANIFEST:
                        raise ValueError("SEALED_MANIFEST_TOO_LARGE")
            output.write(encryptor.finalize())
            output.write(encryptor.tag)
            output.flush()
            os.fsync(output.fileno())
        if temp.stat().st_size > MAX_BUNDLE:
            raise ValueError("SEALED_BUNDLE_TOO_LARGE")
        os.link(temp, destination, follow_symlinks=False)
        temp.unlink()
    finally:
        if temp.exists():
            temp.unlink()
    return {
        "schema": SCHEMA,
        "ciphertext_sha256": _digest(destination),
        "ciphertext_bytes": destination.stat().st_size,
        "recipient_public_key_sha256": pinned_fingerprint,
        "offhost_restore_verified": False,
        "transfer_authorized": False,
        "auto_restore_authorized": False,
    }


def _read_header(stream, file_size: int) -> tuple[dict, bytes, int]:
    prefix = stream.read(len(MAGIC) + 4)
    if len(prefix) != len(MAGIC) + 4 or not prefix.startswith(MAGIC):
        raise ValueError("SEALED_MAGIC_INVALID")
    header_size = struct.unpack(">I", prefix[len(MAGIC):])[0]
    if not 0 < header_size <= MAX_HEADER:
        raise ValueError("SEALED_HEADER_SIZE_INVALID")
    header_bytes = stream.read(header_size)
    if len(header_bytes) != header_size:
        raise ValueError("SEALED_HEADER_TRUNCATED")
    try:
        header = json.loads(header_bytes)
    except (ValueError, UnicodeDecodeError):
        raise ValueError("SEALED_HEADER_INVALID") from None
    if (not isinstance(header, dict) or set(header) != {
            "schema", "aead", "wrap", "public_key_sha256", "nonce_hex", "wrapped_key_hex"
    } or header["schema"] != SCHEMA or header["aead"] != "AES-256-GCM"
            or header["wrap"] != "RSA-OAEP-SHA256"):
        raise ValueError("SEALED_HEADER_UNSUPPORTED")
    ciphertext_bytes = file_size - len(prefix) - header_size - 16
    if ciphertext_bytes <= 0:
        raise ValueError("SEALED_CIPHERTEXT_MISSING")
    return header, prefix + header_bytes, ciphertext_bytes


def _extract_verified_tar(tar_path: Path, target: Path) -> None:
    with tarfile.open(tar_path, "r:") as archive:
        names = []
        total = 0
        for member in archive:
            if not member.isfile() or member.name not in NAMES or member.name in names:
                raise ValueError("SEALED_UNSAFE_TAR_MEMBER")
            if member.size < 0 or member.size > MAX_BUNDLE:
                raise ValueError("SEALED_TAR_MEMBER_TOO_LARGE")
            names.append(member.name)
            total += member.size
            if total > MAX_BUNDLE:
                raise ValueError("SEALED_TAR_TOO_LARGE")
            with archive.extractfile(member) as reader, (target / member.name).open("xb") as output:
                for chunk in iter(lambda: reader.read(CHUNK), b""):
                    output.write(chunk)
            (target / member.name).chmod(0o600)
        if tuple(names) != NAMES:
            raise ValueError("SEALED_INCOMPLETE_CHECKPOINT")


def unseal(bundle: Path, private_key_path: Path, pinned_fingerprint: str, destination: Path) -> dict:
    """Authenticate before reading reconstructed plaintext; recovery-host only."""
    _private_parent(destination)
    if destination.exists() or destination.is_symlink():
        raise ValueError("SEALED_DESTINATION_EXISTS")
    _no_symlinks(bundle)
    bundle_stat = bundle.stat()
    if not stat.S_ISREG(bundle_stat.st_mode) or not 0 < bundle_stat.st_size <= MAX_BUNDLE:
        raise ValueError("SEALED_BUNDLE_UNSAFE")
    key = _trusted_private_key(private_key_path)
    if _fingerprint(key.public_key()) != pinned_fingerprint:
        raise ValueError("SEALED_RECIPIENT_PIN_MISMATCH")
    staging = Path(tempfile.mkdtemp(prefix=".unsealed-incomplete-", dir=destination.parent))
    staging.chmod(0o700)
    try:
        with bundle.open("rb") as source:
            header, prefix, remaining = _read_header(source, bundle_stat.st_size)
            if header["public_key_sha256"] != pinned_fingerprint:
                raise ValueError("SEALED_RECIPIENT_PIN_MISMATCH")
            try:
                nonce = bytes.fromhex(header["nonce_hex"])
                wrapped = bytes.fromhex(header["wrapped_key_hex"])
            except (TypeError, ValueError):
                raise ValueError("SEALED_HEADER_INVALID") from None
            if len(nonce) != 12 or len(wrapped) != key.key_size // 8:
                raise ValueError("SEALED_HEADER_INVALID")
            session_key = key.decrypt(
                wrapped,
                padding.OAEP(mgf=padding.MGF1(algorithm=hashes.SHA256()),
                             algorithm=hashes.SHA256(), label=None),
            )
            if len(session_key) != 32:
                raise ValueError("SEALED_DEK_INVALID")
            source.seek(-16, os.SEEK_END)
            tag = source.read(16)
            decryptor = Cipher(algorithms.AES(session_key), modes.GCM(nonce, tag)).decryptor()
            decryptor.authenticate_additional_data(prefix)
            source.seek(len(prefix))
            tar_path = staging / ".pending-authentication.tar"
            with tar_path.open("xb") as cleartext:
                os.fchmod(cleartext.fileno(), 0o600)
                while remaining:
                    block = source.read(min(CHUNK, remaining))
                    if not block:
                        raise ValueError("SEALED_CIPHERTEXT_TRUNCATED")
                    cleartext.write(decryptor.update(block))
                    remaining -= len(block)
                try:
                    cleartext.write(decryptor.finalize())
                except InvalidTag:
                    raise ValueError("SEALED_AUTHENTICATION_FAILED") from None
                cleartext.flush()
                os.fsync(cleartext.fileno())
            tar_path.chmod(0o600)
        _extract_verified_tar(tar_path, staging)
        tar_path.unlink()
        manifest = verify(staging)
        staging.rename(destination)
        return {
            "schema": SCHEMA,
            "restored_files": manifest["file_count"],
            "checkpoint_verified": True,
            "offhost_receipt_signed": False,
            "auto_restore_authorized": False,
        }
    finally:
        if staging.exists():
            shutil.rmtree(staging)


def main() -> None:
    parser = argparse.ArgumentParser()
    modes = parser.add_subparsers(dest="operation", required=True)
    sealer = modes.add_parser("seal")
    sealer.add_argument("--checkpoint", type=Path, required=True)
    sealer.add_argument("--public-key", type=Path, required=True)
    sealer.add_argument("--recipient-pin", required=True)
    sealer.add_argument("--output", type=Path, required=True)
    unsealer = modes.add_parser("unseal")
    unsealer.add_argument("--bundle", type=Path, required=True)
    unsealer.add_argument("--private-key", type=Path, required=True)
    unsealer.add_argument("--recipient-pin", required=True)
    unsealer.add_argument("--destination", type=Path, required=True)
    args = parser.parse_args()
    if args.operation == "seal":
        result = seal(args.checkpoint, args.public_key, args.recipient_pin, args.output)
        print("F01_SEALED_CHECKPOINT=PASS " + json.dumps(result, sort_keys=True))
    else:
        result = unseal(args.bundle, args.private_key, args.recipient_pin, args.destination)
        print("F01_AUTHENTICATED_UNSEAL=PASS " + json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
