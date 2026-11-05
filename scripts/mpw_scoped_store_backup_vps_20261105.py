#!/usr/bin/env python3
"""Encrypt and verify a store-only scoped SQL gzip stream on private VPS.

Requires the already-established owner recovery key. No plaintext filesystem
backup, no source database access, no production writes. Distinct namespace
ensures a scoped store dump can never masquerade as a complete backup pair.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import zlib
from pathlib import Path

ID_RE = re.compile(r"^mpw_store_[0-9]{8}T[0-9]{6}Z_[0-9a-f]{16}$")
MARKER = b"\n-- MPW-STORE-SCOPED-20261105-COMPLETE --\n"
MAX_GZIP_BYTES = 800_000_000
MAX_PLAIN_BYTES = 4 * 1024**3
MIN_REMAIN_FREE = 3 * 1024**3
ROOT = Path.home() / ".private-mojplaywin-offhost-backups" / "store-scoped-v1"
KEYROOT = Path.home() / ".config" / "mojplaywin-backup-recovery"


def disk_free(path):
    s = os.statvfs(path)
    return s.f_bavail * s.f_frsize


def secure_dir(p, *, create):
    if p.is_symlink():
        raise RuntimeError("SYMLINK_DIRECTORY")
    if create:
        p.mkdir(parents=True, exist_ok=True, mode=0o700)
    stat_result = p.stat()
    if not stat.S_ISDIR(stat_result.st_mode) or stat_result.st_uid != os.getuid() or stat_result.st_mode & 0o077:
        raise RuntimeError("PRIVATE_DIRECTORY_REQUIRED")


def key_bytes():
    secure_dir(KEYROOT, create=False)
    secure_dir(KEYROOT / "gnupg-v2", create=False)
    key = KEYROOT / "recovery-key.bin"
    if key.is_symlink():
        raise RuntimeError("KEY_SYMLINK")
    s = key.stat()
    if not stat.S_ISREG(s.st_mode) or s.st_uid != os.getuid() or s.st_mode & 0o177:
        raise RuntimeError("KEY_PRIVACY_REQUIRED")
    result = key.read_bytes()
    if len(result) != 32:
        raise RuntimeError("KEY_LENGTH_INVALID")
    return result


def gpg(key, options, *, encrypted_output=None):
    phrase = hashlib.sha256(key + b":MJWP:GPG-AES256:20261017:v2").hexdigest().encode() + b"\n"
    r, w = os.pipe()
    try:
        os.write(w, phrase)
    finally:
        os.close(w)
    try:
        return subprocess.Popen([
            "gpg", "--homedir", str(KEYROOT / "gnupg-v2"), "--batch", "--no-tty",
            "--pinentry-mode", "loopback", "--passphrase-fd", str(r),
            "--no-options", *options,
        ], stdin=subprocess.PIPE if encrypted_output is not None else subprocess.DEVNULL,
            stdout=encrypted_output if encrypted_output is not None else subprocess.PIPE,
            stderr=subprocess.DEVNULL, pass_fds=(r,))
    finally:
        os.close(r)


def paths(identity):
    if not ID_RE.fullmatch(identity):
        raise RuntimeError("UNSAFE_SCOPE_ID")
    base = ROOT / identity
    return base.with_suffix(".sql.gz.gpg"), base.with_suffix(".manifest.json")


def inspect_plain_gzip(chunks, sink=None):
    digest = hashlib.sha256()
    raw_digest = hashlib.sha256()
    decompressor = zlib.decompressobj(zlib.MAX_WBITS + 16)
    compressed_size = expanded_size = 0
    tail = b""
    for block in chunks:
        compressed_size += len(block)
        if compressed_size > MAX_GZIP_BYTES:
            raise RuntimeError("SCOPED_GZIP_CAPACITY_GATE")
        digest.update(block)
        if sink is not None:
            sink.write(block)
        decoded = decompressor.decompress(block)
        expanded_size += len(decoded)
        if expanded_size > MAX_PLAIN_BYTES:
            raise RuntimeError("SCOPED_SQL_CAPACITY_GATE")
        raw_digest.update(decoded)
        tail = (tail + decoded)[-len(MARKER):]
        if decompressor.unused_data:
            raise RuntimeError("UNEXPECTED_GZIP_TRAILING_BYTES")
    if not decompressor.eof or tail != MARKER or expanded_size < 1024:
        raise RuntimeError("SCOPED_SQL_FOOTER_OR_GZIP_INVALID")
    return {
        "gzip_bytes": compressed_size,
        "gzip_sha256": digest.hexdigest(),
        "sql_bytes": expanded_size,
        "sql_sha256": raw_digest.hexdigest(),
    }


def decrypt_stream(path, key, sink=None):
    proc = gpg(key, ["--decrypt", "--output", "-", str(path)])
    try:
        assert proc.stdout is not None
        result = inspect_plain_gzip(iter(lambda: proc.stdout.read(32768), b""), sink)
        if proc.wait(timeout=60):
            raise RuntimeError("SCOPED_GPG_INTEGRITY_FAILURE")
        if sink is not None:
            sink.flush()
        return result
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait()


def store(identity):
    secure_dir(ROOT.parent, create=False)
    secure_dir(ROOT, create=True)
    if shutil.which("gpg") is None or disk_free(ROOT) < MIN_REMAIN_FREE + 800_000_000:
        raise RuntimeError("SCOPED_VPS_STORAGE_NO_GO")
    key = key_bytes()
    path, manifest = paths(identity)
    partial = Path(str(path) + ".partial")
    if any(p.exists() or p.is_symlink() for p in (path, manifest, partial)):
        raise RuntimeError("SCOPED_ARCHIVE_COLLISION")
    fd = os.open(str(partial), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    process = None
    try:
        try:
            process = gpg(key, [
                "--symmetric", "--cipher-algo", "AES256", "--compress-algo", "none",
                "--s2k-digest-algo", "SHA256", "--s2k-mode", "3",
                "--s2k-count", "65011712", "--output", "-",
            ], encrypted_output=fd)
        finally:
            os.close(fd)
        total = 0
        assert process.stdin is not None
        for block in iter(lambda: sys.stdin.buffer.read(32768), b""):
            total += len(block)
            if total > MAX_GZIP_BYTES or disk_free(ROOT) < MIN_REMAIN_FREE or partial.stat().st_size > MAX_GZIP_BYTES:
                raise RuntimeError("SCOPED_VPS_STORAGE_NO_GO")
            process.stdin.write(block)
        process.stdin.close()
        if total < 1024 or process.wait(timeout=90):
            raise RuntimeError("SCOPED_GPG_ENCRYPT_FAILED")
        if partial.stat().st_size > MAX_GZIP_BYTES or disk_free(ROOT) < MIN_REMAIN_FREE:
            raise RuntimeError("SCOPED_VPS_STORAGE_NO_GO")
        verified = decrypt_stream(partial, key)
        if verified["gzip_bytes"] != total:
            raise RuntimeError("SCOPED_CIPHERTEXT_MISMATCH")
        os.rename(partial, path)
        info = {
            "scope": "mpw_store_16_tables_fk_closure_and_migrations",
            "full_database_backup": False,
            "restore_verified": False,
            "encryption": "gpg-aes256-existing-owner-key",
            "identity": identity,
            "encrypted_bytes": path.stat().st_size,
            **verified,
        }
        fd = os.open(str(manifest), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        with os.fdopen(fd, "w") as output:
            json.dump(info, output, sort_keys=True)
            output.write("\n")
            output.flush()
            os.fsync(output.fileno())
        print("MPW_SCOPED_GPG_BACKUP_CREATED=" + json.dumps({
            "id": identity,
            "encrypted_bytes": info["encrypted_bytes"],
            "gzip_bytes": info["gzip_bytes"],
            "sql_bytes": info["sql_bytes"],
            "archive_integrity_verified": True,
            "isolated_restore_verified": False,
        }, sort_keys=True))
    finally:
        if process is not None and process.poll() is None:
            process.kill()
            process.wait()
        partial.unlink(missing_ok=True)


def stream(identity):
    secure_dir(ROOT, create=False)
    key = key_bytes()
    path, manifest = paths(identity)
    if path.is_symlink() or manifest.is_symlink():
        raise RuntimeError("SCOPED_ARCHIVE_SYMLINK")
    info = json.loads(manifest.read_text("utf-8"))
    if info.get("identity") != identity or info.get("full_database_backup") is not False or info.get("scope") != "mpw_store_16_tables_fk_closure_and_migrations":
        raise RuntimeError("SCOPED_MANIFEST_IDENTITY_MISMATCH")
    if info.get("encrypted_bytes") != path.stat().st_size:
        raise RuntimeError("SCOPED_ARCHIVE_SIZE_MISMATCH")
    result = decrypt_stream(path, key, sink=sys.stdout.buffer)
    if any(result[k] != info.get(k) for k in result):
        raise RuntimeError("SCOPED_ARCHIVE_CHECKSUM_MISMATCH")
    print("MPW_SCOPED_GPG_RESTREAM_INTEGRITY_PASS", file=sys.stderr)


if __name__ == "__main__":
    try:
        if len(sys.argv) < 3 or sys.argv[-2] not in ("store", "stream"):
            raise RuntimeError("SCOPED_UNKNOWN_OPERATION")
        operation, identity = sys.argv[-2:]
        if operation == "store":
            store(identity)
        else:
            stream(identity)
    except Exception as error:
        # No SQL/customer/key/paths or unexpected error strings in Actions logs.
        allowed = {"SCOPED_VPS_STORAGE_NO_GO", "SCOPED_ARCHIVE_COLLISION",
                   "SCOPED_GPG_ENCRYPT_FAILED", "SCOPED_CIPHERTEXT_MISMATCH",
                   "SCOPED_MANIFEST_IDENTITY_MISMATCH", "SCOPED_ARCHIVE_SIZE_MISMATCH",
                   "SCOPED_ARCHIVE_CHECKSUM_MISMATCH", "SCOPED_UNKNOWN_OPERATION",
                   "UNSAFE_SCOPE_ID"}
        category = str(error) if str(error) in allowed else "SCOPED_VPS_UNCLASSIFIED"
        print("MPW_SCOPED_VPS_ABORT=" + category, file=sys.stderr)
        raise SystemExit(1)
