#!/usr/bin/env python3
"""Version 2: AES-256 OpenPGP streaming encrypted off-host backup.

Uses GnuPG's symmetrical AES-256 encryption + built-in integrity protection,
NOT the broken VPS Python cryptography installation. Source bytes travel only
over pinned SSH and are NEVER persisted as plaintext. Passphrase is derived from
the owner-only 32-byte recovery key via SHA256; fed to GPG on a private FD,
never shell args, logs, repo or environment. No site, DB, Passenger writes.
"""
from __future__ import annotations

import hashlib
import io
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
from pathlib import Path

MARKER = b"\n-- MJWP-RECOVERY-20261017-COMPLETE-F91D7C40 --\n"
MAX_SOURCE_BYTES = 12 * 1024**3
MAX_ENCRYPTED_BYTES = 12 * 1024**3
MIN_START_FREE = 14 * 1024**3
BLOCK = 128 * 1024
STEM = "mojplaywin_20261017"
VERSION = "gpgv2"


def make_private(p: Path):
    if p.is_symlink():
        raise RuntimeError("symlink rejected")
    p.mkdir(mode=0o700, parents=True, exist_ok=True)
    s = p.stat()
    if not stat.S_ISDIR(s.st_mode) or s.st_uid != os.getuid() or (s.st_mode & 0o077):
        raise RuntimeError("directory ownership or permissions invalid")


def recovery_key(path: Path) -> bytes:
    if path.is_symlink():
        raise RuntimeError("key symlink rejected")
    if not path.exists():
        fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "wb") as file:
            file.write(os.urandom(32))
            file.flush()
            os.fsync(file.fileno())
    s = path.stat()
    if not stat.S_ISREG(s.st_mode) or s.st_uid != os.getuid() or (s.st_mode & 0o177):
        raise RuntimeError("key privacy invalid")
    key = path.read_bytes()
    if len(key) != 32:
        raise RuntimeError("key bytes invalid")
    return key


def gpg_process(key: bytes, home: Path, options: list[str], *,
                input_pipe: bool, stdout, timeout_unused=False):
    # The passphrase is never included in environment/argv/history, and no
    # plaintext passphrase file is created, even temporarily.
    phrase = hashlib.sha256(key + b":MJWP:GPG-AES256:20261017:v2").hexdigest().encode() + b"\n"
    r, w = os.pipe()
    try:
        os.write(w, phrase)
    finally:
        os.close(w)
    argv = [
        "gpg", "--homedir", str(home), "--batch", "--no-tty",
        "--pinentry-mode", "loopback", "--passphrase-fd", str(r),
        "--no-options", *options,
    ]
    try:
        process = subprocess.Popen(
            argv, stdin=subprocess.PIPE if input_pipe else subprocess.DEVNULL,
            stdout=stdout, stderr=subprocess.DEVNULL, pass_fds=(r,),
        )
    finally:
        os.close(r)
    return process


def disk_free(path: Path) -> int:
    s = os.statvfs(path)
    return s.f_bavail * s.f_frsize


def encrypt_stream_to_file(stream, target: Path, gpg_home: Path, key: bytes):
    fd = os.open(str(target), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        proc = gpg_process(key, gpg_home, [
            "--symmetric", "--cipher-algo", "AES256", "--compress-algo", "zlib",
            "--s2k-digest-algo", "SHA256", "--s2k-mode", "3",
            "--s2k-count", "65011712", "--output", "-",
        ], input_pipe=True, stdout=fd)
    finally:
        os.close(fd)
    total = 0
    digest = hashlib.sha256()
    tail = b""
    try:
        assert proc.stdin is not None
        while True:
            chunk = stream.read(BLOCK)
            if not chunk:
                break
            total += len(chunk)
            if total > MAX_SOURCE_BYTES:
                raise RuntimeError("source exceeds safety maximum")
            digest.update(chunk)
            tail = (tail + chunk)[-len(MARKER):]
            proc.stdin.write(chunk)
            if target.stat().st_size > MAX_ENCRYPTED_BYTES or disk_free(target.parent) < 3 * 1024**3:
                raise RuntimeError("VPS storage safety cap")
        proc.stdin.close()
        if proc.wait(timeout=120):
            raise RuntimeError("GPG encryption process failed")
        if total < 1024 + len(MARKER) or tail != MARKER:
            raise RuntimeError("source completion footer absent")
        return total, digest.hexdigest()
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait()


def verify_stream(target: Path, gpg_home: Path, key: bytes):
    proc = gpg_process(key, gpg_home, ["--decrypt", "--output", "-", str(target)],
                       input_pipe=False, stdout=subprocess.PIPE)
    n = 0
    digest = hashlib.sha256()
    tail = b""
    try:
        assert proc.stdout is not None
        while True:
            b = proc.stdout.read(BLOCK)
            if not b:
                break
            n += len(b)
            if n > MAX_SOURCE_BYTES:
                raise RuntimeError("decryption exceeds source maximum")
            digest.update(b)
            tail = (tail + b)[-len(MARKER):]
        if proc.wait(timeout=120):
            raise RuntimeError("OpenPGP message integrity check failed")
        if tail != MARKER:
            raise RuntimeError("authenticated plaintext source footer absent")
        return n, digest.hexdigest()
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait()


def store(stream, kind: str, *, root: Path | None = None, keyroot: Path | None = None,
          minimum_free: int = MIN_START_FREE):
    if kind not in ("mysql", "files"):
        raise RuntimeError("unsupported kind")
    root = Path.home() if root is None else root
    keyroot = Path.home() if keyroot is None else keyroot
    backups = root / ".private-mojplaywin-offhost-backups"
    secrets = keyroot / ".config" / "mojplaywin-backup-recovery"
    gnupg = secrets / "gnupg-v2"
    make_private(backups)
    make_private(secrets)
    make_private(gnupg)
    if shutil.which("gpg") is None or disk_free(backups) < minimum_free:
        raise RuntimeError("GPG unavailable or destination capacity insufficient")
    key = recovery_key(secrets / "recovery-key.bin")
    partial = backups / (STEM + "_" + kind + "_" + VERSION + ".gpg.partial")
    complete = backups / (STEM + "_" + kind + "_" + VERSION + ".gpg")
    manifest = backups / (STEM + "_" + kind + "_" + VERSION + ".manifest.json")
    if any(x.exists() or x.is_symlink() for x in (partial,complete,manifest)):
        raise RuntimeError("one-time output already exists; refusing overwrite")
    total, digest = encrypt_stream_to_file(stream, partial, gnupg, key)
    verified_total, verified_digest = verify_stream(partial, gnupg, key)
    if total != verified_total or digest != verified_digest:
        raise RuntimeError("OpenPGP round-trip integrity or size mismatch")
    os.rename(partial, complete)
    summary = {
        "kind": kind, "format": "OpenPGP-AES256-GPGv2",
        "encrypted_bytes": complete.stat().st_size,
        "plaintext_bytes": total, "plaintext_sha256": digest,
        "source_completion_footer_verified": True,
        "ciphertext_roundtrip_integrity_verified": True,
        "key_exported_off_vps": False,
        "all_independent_subsites_backed_up": False,
        "isolated_restoration_completed": False,
        "release_permitted": False,
    }
    fd = os.open(str(manifest), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as f:
        json.dump(summary, f, sort_keys=True)
        f.write("\n")
        f.flush()
        os.fsync(f.fileno())
    return {"kind": kind, "gpg_aes256_backup_created": True,
            "encrypted_bytes": summary["encrypted_bytes"],
            "plaintext_bytes": total, "decryption_verified": True,
            "source_complete": True, "full_tenant_backup": False,
            "isolated_restore_verified": False, "release_permitted": False}


def selftest():
    # Generates ONLY arbitrary synthetic test bytes in an isolated temporary
    # VPS path and removes those test files. Never touches source/production.
    if not shutil.which("gpg"):
        return False
    with tempfile.TemporaryDirectory(prefix="mjwp-gpg-selftest-") as td:
        d = Path(td)
        g = d / "gnupg"
        make_private(g)
        key = os.urandom(32)
        path = d / "fixture.gpg"
        payload = b"synthetic not customer data\n" * 80 + MARKER
        count, digest = encrypt_stream_to_file(io.BytesIO(payload), path, g, key)
        check_count, check_hash = verify_stream(path, g, key)
        return count == check_count == len(payload) and digest == check_hash


if __name__ == "__main__":
    try:
        if len(sys.argv) != 2:
            raise RuntimeError("missing operation")
        if sys.argv[1] == "selftest":
            good = selftest()
            print(json.dumps({"classification": "VPS_GPG_AES256_SYNTHETIC_SELFTEST",
                              "pass": good, "backup_written": False,
                              "release_permitted": False}))
            raise SystemExit(0 if good else 1)
        result = store(sys.stdin.buffer, sys.argv[1])
        print(json.dumps(result, sort_keys=True))
    except SystemExit:
        raise
    except Exception:
        # Deliberately do not print errors, paths, filenames, key or DB content.
        print("VPS_GPG_BACKUP_FAILED_NO_RELEASE", file=sys.stderr)
        raise SystemExit(1)
