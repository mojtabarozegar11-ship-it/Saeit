#!/usr/bin/env python3
"""Isolated VPS-only temporary GPGv2 performance check on synthetic stdin.

Uses a NEW random, ephemeral key and temp directory, never existing backup
keys, customer data, app folders, production MySQL or real archives.
Encrypted temporary fixture is decrypted and hash/byte equality checked.
Only booleans and timings printed; temporary ciphertext removed on exit.
"""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time

MAX_BYTES = 16 * 1024 * 1024
EXPECTED_BYTES = MAX_BYTES


def gpg(key, folder, options, *, stdin=None, stdout=subprocess.PIPE):
    phrase = hashlib.sha256(key + b":SYNTHETIC-GPG-CHECK").hexdigest().encode("ascii") + b"\n"
    r, w = os.pipe()
    try:
        os.write(w, phrase)
    finally:
        os.close(w)
    try:
        proc = subprocess.Popen(
            ["gpg", "--homedir", str(folder), "--batch", "--no-tty",
             "--pinentry-mode", "loopback", "--passphrase-fd", str(r),
             "--no-options"] + options,
            stdin=stdin, stdout=stdout, stderr=subprocess.DEVNULL,
            pass_fds=(r,),
        )
    finally:
        os.close(r)
    return proc


def test():
    if shutil.which("gpg") is None:
        raise RuntimeError("GPG not present")
    start = time.monotonic()
    key = os.urandom(32)
    with tempfile.TemporaryDirectory(prefix="mjwp-synthetic-gpg-") as folder_name:
        folder = Path(folder_name)
        gpghome = folder / "gpghome"
        gpghome.mkdir(mode=0o700)
        target = folder / "synthetic.gpg"
        digest = hashlib.sha256()
        total = 0
        with target.open("xb") as out:
            proc = gpg(key, gpghome, [
                "--symmetric", "--cipher-algo", "AES256",
                "--compress-algo", "zlib", "--s2k-digest-algo", "SHA256",
                "--s2k-mode", "3", "--s2k-count", "65011712",
                "--output", "-"
            ], stdin=subprocess.PIPE, stdout=out)
            try:
                while total < MAX_BYTES:
                    block = sys.stdin.buffer.read(min(131072, MAX_BYTES - total))
                    if not block:
                        break
                    digest.update(block)
                    total += len(block)
                    proc.stdin.write(block)
                if proc.stdin:
                    proc.stdin.close()
                if proc.wait(timeout=50) != 0:
                    raise RuntimeError("GPG encryption failed")
            finally:
                if proc.poll() is None:
                    proc.kill()
                    proc.wait()
        if total != EXPECTED_BYTES or sys.stdin.buffer.read(1):
            raise RuntimeError("Wrong synthetic source stream size")
        encrypted_bytes = target.stat().st_size
        verified_digest = hashlib.sha256()
        decrypted_total = 0
        decryptor = gpg(key, gpghome, ["--decrypt", "--output", "-", str(target)])
        try:
            for block in iter(lambda: decryptor.stdout.read(131072), b""):
                decrypted_total += len(block)
                if decrypted_total > EXPECTED_BYTES:
                    raise RuntimeError("Unexpected decrypted size")
                verified_digest.update(block)
            if decryptor.wait(timeout=50) != 0:
                raise RuntimeError("GPG integrity check failed")
        finally:
            if decryptor.poll() is None:
                decryptor.kill()
                decryptor.wait()
        verified = decrypted_total == total and verified_digest.digest() == digest.digest()
        if not verified:
            raise RuntimeError("Round-trip mismatch")
        elapsed = max(time.monotonic() - start, 0.001)
        return {
            "classification": "ISOLATED_SYNTHETIC_GPGV2_STREAM",
            "fixture_bytes": total,
            "ciphertext_bytes": encrypted_bytes,
            "roundtrip_integrity_verified": verified,
            "elapsed_seconds": round(elapsed, 2),
            "source_mib_per_second": round(total / elapsed / 1048576, 2),
            "production_source_data_read": False,
            "real_backup_modified": False,
            "temp_fixture_removed_on_success": True,
            "release_permitted": False,
        }


if __name__ == "__main__":
    try:
        result = test()
    except Exception as exc:
        print(json.dumps({
            "classification": "ISOLATED_SYNTHETIC_GPGV2_STREAM",
            "failure_class": type(exc).__name__,
            "roundtrip_integrity_verified": False,
            "real_backup_modified": False,
            "release_permitted": False
        }, sort_keys=True))
        raise SystemExit(2)
    print(json.dumps(result, sort_keys=True))
