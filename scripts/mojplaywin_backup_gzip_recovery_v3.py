#!/usr/bin/env python3
"""Independent offline recovery reader for versioned MojPlayWin GPGv2 gzip streams.

Modes:
  check     only bounded private-file and manifest metadata, no decryption
  validate  authenticate/decrypt/decompress BOTH streams; discard data in memory
  mysql     validate first, then stream private decoded SQL to stdout
  files     validate first, then stream private decoded TAR to stdout

IMPORTANT: mysql/files STDOUT IS PRIVATE BINARY; it must be directed ONLY into
an isolated recovery process, never a GitHub log or a production DB.
No production DB connections, SQL import, filesystem extraction, or site writes.
"""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import zlib

STEM = "mojplaywin_20261020"
MARKER = b"\n-- MJWP-RECOVERY-20261017-COMPLETE-F91D7C40 --\n"
MAX_BYTES = 12 * 1024 ** 3
MAX_ARCHIVE_BYTES = 12 * 1024 ** 3
BLOCK = 128 * 1024


def safe_file(p):
    try:
        if p.is_symlink():
            return False
        s = p.stat()
        return stat.S_ISREG(s.st_mode) and s.st_uid == os.getuid() and not s.st_mode & 0o177
    except OSError:
        return False


def details(kind, *, home=None, stem=STEM):
    if kind not in ("mysql", "files") or not isinstance(stem, str) or not re.fullmatch(r"mojplaywin_20\d{6}", stem):
        raise RuntimeError("invalid scope")
    home = Path.home() if home is None else Path(home)
    storage = home / ".private-mojplaywin-offhost-backups"
    keys = home / ".config" / "mojplaywin-backup-recovery"
    ghome = keys / "gnupg-v2"
    if any(x.is_symlink() or not x.is_dir() for x in (storage, keys, ghome)):
        raise RuntimeError("unverified private location")
    archive = storage / (stem + "_" + kind + "_gpgv2.gpg")
    manifest = storage / (stem + "_" + kind + "_gpgv2.manifest.json")
    keyfile = keys / "recovery-key.bin"
    if not all(safe_file(x) for x in (archive, manifest, keyfile)):
        raise RuntimeError("private archive, manifest or key missing")
    if archive.stat().st_size > MAX_ARCHIVE_BYTES or manifest.stat().st_size > 16384:
        raise RuntimeError("unsafe archive metadata size")
    meta = json.loads(manifest.read_text("ascii"))
    if (meta.get("kind") != kind or
        meta.get("format") != "OpenPGP-AES256-GPGv2" or
        meta.get("source_encoding") != "gzip-with-footer-v1" or
        meta.get("source_completion_footer_verified") is not True or
        meta.get("ciphertext_roundtrip_integrity_verified") is not True or
        meta.get("encrypted_bytes") != archive.stat().st_size or
        type(meta.get("plaintext_bytes")) is not int or
        not 1024 <= meta["plaintext_bytes"] <= MAX_BYTES or
        type(meta.get("uncompressed_source_bytes")) is not int or
        not 1024 <= meta["uncompressed_source_bytes"] <= MAX_BYTES or
        not isinstance(meta.get("plaintext_sha256"), str) or
        not re.fullmatch(r"[0-9a-f]{64}", meta["plaintext_sha256"])):
        raise RuntimeError("incomplete or invalid backup manifest")
    key = keyfile.read_bytes()
    if len(key) != 32:
        raise RuntimeError("invalid recovery key")
    return archive, meta, ghome, key


class Decode:
    def __init__(self, out=None):
        self._tail = b""
        self._z = zlib.decompressobj(wbits=31)
        self.count = 0
        self.out = out

    def feed(self, block):
        joined = self._tail + block
        if len(joined) <= len(MARKER):
            self._tail = joined
            return
        compressed, self._tail = joined[:-len(MARKER)], joined[-len(MARKER):]
        if self._z.eof:
            raise RuntimeError("unexpected data after gzip")
        while compressed:
            chunk = self._z.decompress(compressed, 1024 * 1024)
            self.count += len(chunk)
            if self.count > MAX_BYTES:
                raise RuntimeError("zip-bomb safety guard")
            if self.out is not None and chunk:
                self.out.write(chunk)
            compressed = self._z.unconsumed_tail
            if self._z.eof:
                if self._z.unused_data or compressed:
                    raise RuntimeError("second member or trailing gzip data")
                break

    def finish(self, expected):
        if self._tail != MARKER or not self._z.eof or self._z.unused_data:
            raise RuntimeError("incomplete gzip stream/footer/CRC")
        if self.count != expected:
            raise RuntimeError("uncompressed byte count mismatch")
        if self.out is not None:
            self.out.flush()
        return self.count


def decode_archive(kind, *, home=None, stem=STEM, out=None):
    archive, meta, gnupg, key = details(kind, home=home, stem=stem)
    phrase = hashlib.sha256(key + b":MJWP:GPG-AES256:20261017:v2").hexdigest().encode() + b"\n"
    r, w = os.pipe()
    try:
        os.write(w, phrase)
    finally:
        os.close(w)
    try:
        proc = subprocess.Popen([
            "gpg", "--homedir", str(gnupg), "--batch", "--no-tty",
            "--pinentry-mode", "loopback", "--passphrase-fd", str(r),
            "--no-options", "--decrypt", "--output", "-", str(archive)
        ], stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
           pass_fds=(r,))
    finally:
        os.close(r)
    encoded_length = 0
    sha = hashlib.sha256()
    decoder = Decode(out)
    try:
        assert proc.stdout is not None
        for chunk in iter(lambda: proc.stdout.read(BLOCK), b""):
            encoded_length += len(chunk)
            if encoded_length > MAX_BYTES:
                raise RuntimeError("encrypted envelope too large")
            sha.update(chunk)
            decoder.feed(chunk)
        if proc.wait(timeout=120) != 0:
            raise RuntimeError("GPG integrity check failed")
        if encoded_length != meta["plaintext_bytes"] or sha.hexdigest() != meta["plaintext_sha256"]:
            raise RuntimeError("authenticated envelope size or hash mismatch")
        return decoder.finish(meta["uncompressed_source_bytes"])
    finally:
        if proc.stdout is not None:
            proc.stdout.close()
        if proc.poll() is None:
            proc.kill()
            proc.wait()


def both_ready(*, home=None, stem=STEM):
    try:
        for kind in ("mysql", "files"):
            details(kind, home=home, stem=stem)
        return True
    except (RuntimeError, OSError, ValueError, KeyError, TypeError):
        return False


if __name__ == "__main__":
    try:
        if len(sys.argv) != 2:
            raise RuntimeError("mode required")
        mode = sys.argv[1]
        if mode == "check":
            ok = both_ready()
            print(json.dumps({"classification": "V3_BACKUP_METADATA_READY",
                              "both_scoped_streams_complete": ok,
                              "isolated_restore_verified": False,
                              "protected_child_site_coverage_verified": False,
                              "release_permitted": False}, sort_keys=True))
            raise SystemExit(0 if ok else 1)
        if mode == "validate":
            count = {kind: decode_archive(kind) for kind in ("mysql", "files")}
            print(json.dumps({"classification": "V3_BACKUP_CONTENT_AUTHENTICATED",
                              "both_scoped_streams_crc_verified": True,
                              "raw_bytes_by_kind": count,
                              "isolated_restore_verified": False,
                              "release_permitted": False}, sort_keys=True))
        elif mode in ("mysql", "files"):
            # Two-pass validation: do not emit a byte before complete verification.
            verified = decode_archive(mode)
            emitted = decode_archive(mode, out=sys.stdout.buffer)
            if verified != emitted:
                raise RuntimeError("private archive changed during extraction")
            print("V3_PRIVATE_RECOVERY_STREAM_VERIFIED_NO_PRODUCTION_WRITE", file=sys.stderr)
        else:
            raise RuntimeError("unsupported recovery operation")
    except SystemExit:
        raise
    except Exception:
        print("V3_RECOVERY_SOURCE_INVALID_NO_RELEASE", file=sys.stderr)
        raise SystemExit(1)
