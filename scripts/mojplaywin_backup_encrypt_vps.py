#!/usr/bin/env python3
"""On-VPS ONE-TIME AES-256-GCM + GZIP stream receiver and integrity rehearsal.

Receives SQL dump or GNU tar from stdin over pinned SSH, directly compresses
and encrypts on the VPS. NEVER writes plaintext to disk. Master recovery key
stays in private mode-0600 VPS key directory, not GitHub or cPanel.
Authenticated decrypt+decompress+completion-footer check occurs before manifest.
This is not a MySQL import or all-tenants full restore test.
"""
from __future__ import annotations

import hashlib
import json
import os
import stat
import sys
import zlib
from pathlib import Path

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

HEADER = b"MJWPv1"
MARKER = b"\n-- MJWP-RECOVERY-20261017-COMPLETE-F91D7C40 --\n"
MAX_SOURCE_BYTES = 12 * 1024**3
MAX_STORED_BYTES = 12 * 1024**3
MIN_START_FREE = 14 * 1024**3
READ_BLOCK = 128 * 1024
BASENAME = "mojplaywin_20261017"


def make_private_directory(path: Path):
    if path.is_symlink():
        raise RuntimeError("symlink directory forbidden")
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    s = path.stat()
    if not stat.S_ISDIR(s.st_mode) or s.st_uid != os.getuid() or (s.st_mode & 0o077):
        raise RuntimeError("backup directory must be owned by this account, mode 0700")


def get_key(path: Path):
    if path.is_symlink():
        raise RuntimeError("key symlink refused")
    if not path.exists():
        fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(os.urandom(32))
                handle.flush()
                os.fsync(handle.fileno())
        except Exception:
            raise
    info = path.stat()
    if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or (info.st_mode & 0o177):
        raise RuntimeError("recovery key permissions invalid")
    key = path.read_bytes()
    if len(key) != 32:
        raise RuntimeError("recovery key length invalid")
    return key


def storage_free(path: Path) -> int:
    v = os.statvfs(path)
    return v.f_bavail * v.f_frsize


def verification(path: Path, key: bytes):
    length = path.stat().st_size
    if length < len(HEADER) + 12 + 16 + 1:
        raise RuntimeError("encrypted file incomplete")
    output_hash = hashlib.sha256()
    tail = b""
    total = 0
    with path.open("rb") as f:
        header = f.read(len(HEADER))
        if header != HEADER:
            raise RuntimeError("invalid header")
        nonce = f.read(12)
        f.seek(-16, os.SEEK_END)
        tag = f.read(16)
        f.seek(len(HEADER) + 12)
        cipher = Cipher(algorithms.AES(key), modes.GCM(nonce, tag)).decryptor()
        decomp = zlib.decompressobj(wbits=31)
        left = length - len(HEADER) - 12 - 16
        while left:
            b = f.read(min(READ_BLOCK, left))
            if not b:
                raise RuntimeError("unexpected ciphertext EOF")
            left -= len(b)
            plain = decomp.decompress(cipher.update(b))
            total += len(plain)
            if total > MAX_SOURCE_BYTES:
                raise RuntimeError("verified source size beyond cap")
            output_hash.update(plain)
            tail = (tail + plain)[-len(MARKER):]
        trailer = cipher.finalize()
        final_plain = decomp.decompress(trailer) + decomp.flush()
        total += len(final_plain)
        output_hash.update(final_plain)
        tail = (tail + final_plain)[-len(MARKER):]
        if not decomp.eof or decomp.unused_data or tail != MARKER:
            raise RuntimeError("authenticated stream lacks verified source success footer")
    return {"plaintext_bytes": total, "sha256": output_hash.hexdigest(), "authenticated": True}


def store(stream, kind: str, *, root: Path | None = None, keyroot: Path | None = None,
          min_start_free: int = MIN_START_FREE):
    if kind not in ("mysql", "files"):
        raise RuntimeError("unsupported backup stream kind")
    base = Path.home() if root is None else root
    folder = base / ".private-mojplaywin-offhost-backups"
    secrets = (Path.home() if keyroot is None else keyroot) / ".config" / "mojplaywin-backup-recovery"
    make_private_directory(folder)
    make_private_directory(secrets)
    if storage_free(folder) < min_start_free:
        raise RuntimeError("insufficient offhost backup capacity")
    key = get_key(secrets / "recovery-key.bin")
    out = folder / (BASENAME + "_" + kind + ".gcm")
    partial = folder / (BASENAME + "_" + kind + ".gcm.partial")
    manifest = folder / (BASENAME + "_" + kind + ".manifest.json")
    if any(p.exists() or p.is_symlink() for p in (out, partial, manifest)):
        raise RuntimeError("one-time backup already exists; no overwrites")
    fd = os.open(str(partial), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    nonce = os.urandom(12)
    c = Cipher(algorithms.AES(key), modes.GCM(nonce)).encryptor()
    comp = zlib.compressobj(level=1, wbits=31)
    total = 0
    digest = hashlib.sha256()
    seen_tail = b""
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(HEADER + nonce)
            while True:
                b = stream.read(READ_BLOCK)
                if not b:
                    break
                total += len(b)
                if total > MAX_SOURCE_BYTES:
                    raise RuntimeError("source size cap exceeded")
                digest.update(b)
                seen_tail = (seen_tail + b)[-len(MARKER):]
                encrypted = c.update(comp.compress(b))
                if encrypted:
                    handle.write(encrypted)
                if handle.tell() > MAX_STORED_BYTES or storage_free(folder) < 3 * 1024**3:
                    raise RuntimeError("backup volume near disk safety limit")
            if total < len(MARKER) + 1024 or seen_tail != MARKER:
                raise RuntimeError("source did not finish a complete dump/archive")
            handle.write(c.update(comp.flush()))
            handle.write(c.finalize())
            handle.write(c.tag)
            handle.flush()
            os.fsync(handle.fileno())
        result = verification(partial, key)
        if result["plaintext_bytes"] != total or result["sha256"] != digest.hexdigest():
            raise RuntimeError("authenticated stream digest mismatch")
        os.rename(partial, out)
        summary = {
            "type": "MJWP-AES256-GCM-GZIP-20261017",
            "scope": "single cPanel MySQL DB" if kind == "mysql" else "two MojPlayWin main source roots",
            "kind": kind,
            "encrypted_bytes": out.stat().st_size,
            "plaintext_bytes": total,
            "plaintext_sha256": digest.hexdigest(),
            "authenticated_decryption_passed": True,
            "source_completion_footer_verified": True,
            "database_import_restored": False,
            "all_unknown_child_sites_included": False,
            "key_recovery_copy_outside_vps_verified": False,
            "release_permitted": False,
        }
        fdmanifest = os.open(str(manifest), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fdmanifest, "w", encoding="utf-8") as m:
            json.dump(summary, m, sort_keys=True)
            m.write("\n")
            m.flush()
            os.fsync(m.fileno())
        # Sanitized output: no private paths, database names, ciphertext, key, or hashes.
        return {"kind": kind, "encrypted_backup_created": True,
                "authenticated_decrypt_verified": True,
                "source_completion_verified": True,
                "encrypted_bytes": summary["encrypted_bytes"],
                "plaintext_bytes": total,
                "separate_key_export_verified": False,
                "isolated_restore_passed": False,
                "all_children_covered": False,
                "release_permitted": False}
    except Exception:
        # Failures leave a .partial file for forensic inspection; never overwrite or
        # claim completion; no sensitive exception text is printed.
        raise


if __name__ == "__main__":
    try:
        if len(sys.argv) != 2:
            raise RuntimeError("kind missing")
        result = store(sys.stdin.buffer, sys.argv[1])
        print(json.dumps(result, sort_keys=True))
    except Exception:
        print("VPS_ENCRYPTED_BACKUP_FAILED_NO_RELEASE", file=sys.stderr)
        raise SystemExit(1)
