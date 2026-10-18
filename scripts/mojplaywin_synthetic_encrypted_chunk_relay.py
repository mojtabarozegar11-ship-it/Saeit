#!/usr/bin/env python3
"""Synthetic-only encrypted chunk upload/resume/restore rehearsal over pinned VPS SSH.

The source and 32-byte throwaway key live ONLY in GitHub runner temp memory/disk.
VPS receives ciphertext plus signed metadata, NEVER decryption key/plaintext.
Uses an owner-private 0700 temporary directory on VPS. No source cPanel files,
MySQL rows, real wallets or site paths are touched.
"""
from __future__ import annotations

import hashlib
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

from mojplaywin_chunked_encrypted_snapshot import stage, verify, restore

CHUNK = 1024 * 1024
FIXTURE = 2 * CHUNK + 287
TEMP_RE = re.compile(r"^/tmp/mjwp-crypto-synth-[A-Za-z0-9]{6,24}$")


def ssh(config, command, payload=None, timeout=35):
    args = ["ssh", "-T", "-F", config, "saeit-vps", command]
    run = subprocess.run(
        args, input=payload, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
        timeout=timeout, check=False,
    )
    if run.returncode != 0:
        raise RuntimeError("Pinned SSH operation failed")
    if len(run.stdout) > 8 * 1024 * 1024:
        raise RuntimeError("Oversized remote response")
    return run.stdout


def run(config):
    with tempfile.TemporaryDirectory(prefix="mjwp-synth-chunk-ci-") as td:
        root = Path(td)
        os.chmod(root, 0o700)
        source = root / "synthetic-source.bin"
        original = os.urandom(FIXTURE)
        source.write_bytes(original)
        key = root / "throwaway.key"
        fd = os.open(str(key), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "wb") as f:
            f.write(os.urandom(32))
        staging = root / "encrypted"
        state = stage(source, staging, "synthetic-ci-001", key, CHUNK)
        if state.get("status") != "verified_complete":
            raise RuntimeError("Local staging failed")
        datafolder = staging / "synthetic-ci-001"
        remote = ssh(config, "umask 077; mktemp -d /tmp/mjwp-crypto-synth-XXXXXXXX").decode("ascii").strip()
        if not TEMP_RE.fullmatch(remote):
            raise RuntimeError("Unsafe remote fixture path; refusing all writes")
        try:
            def remote_hash(name):
                value = ssh(config, "sha256sum '" + remote + "/" + name + "' 2>/dev/null || true", timeout=25).decode("ascii").strip()
                return value.split(" ", 1)[0] if re.fullmatch(r"[0-9a-fA-F]{64}  .+", value) else ""

            def send_if_missing(name):
                payload = (datafolder / name).read_bytes()
                sha = hashlib.sha256(payload).hexdigest()
                if remote_hash(name) == sha:
                    return False
                if remote_hash(name):
                    raise RuntimeError("Remote ciphertext differs; never overwrite")
                ssh(config, "umask 077; test ! -e '" + remote + "/" + name + "' && cat > '" + remote + "/" + name + "'", payload=payload, timeout=50)
                if remote_hash(name) != sha:
                    raise RuntimeError("Remote ciphertext SHA256 not verified")
                return True

            # Simulate interrupted transfer: only one chunk is sent initially.
            send_if_missing("part-000000.bin")
            sent_after_resume = 0
            for name in ("part-000000.bin", "part-000001.bin", "part-000002.bin", "plan.json", "manifest.json"):
                sent_after_resume += int(send_if_missing(name))
            if sent_after_resume != 4:
                raise RuntimeError("Resume unexpectedly rewrote an existing valid chunk")

            received = root / "received"
            received.mkdir(mode=0o700)
            inner = received / "synthetic-ci-001"
            inner.mkdir(mode=0o700)
            for name in ("plan.json", "manifest.json", "part-000000.bin", "part-000001.bin", "part-000002.bin"):
                expected = (datafolder / name).read_bytes()
                actual = ssh(config, "cat '" + remote + "/" + name + "'", timeout=50)
                if hashlib.sha256(actual).digest() != hashlib.sha256(expected).digest():
                    raise RuntimeError("Downloaded ciphertext digest did not match")
                (inner / name).write_bytes(actual)
                os.chmod(inner / name, 0o600)
            verify(received, "synthetic-ci-001", key)
            output = root / "recovered.bin"
            restore(received, "synthetic-ci-001", key, output)
            if output.read_bytes() != original:
                raise RuntimeError("Recovered synthetic file mismatch")
            return {
                "classification": "MOJPLAYWIN_SYNTHETIC_ENCRYPTED_CHUNK_RELAY",
                "chunk_count": 3,
                "fixture_bytes": FIXTURE,
                "first_chunk_reused": True,
                "resumed_chunks_and_metadata_transferred": sent_after_resume,
                "ciphertext_hashes_match": True,
                "signed_manifest_and_authentication_valid": True,
                "isolated_plaintext_recovery_verified": True,
                "private_key_sent_to_vps": False,
                "production_data_read": False,
                "release_permitted": False,
            }
        finally:
            # Only remove the exact temporary path allocated in this run.
            try:
                ssh(config, "rm -rf -- '" + remote + "'", timeout=35)
            except (OSError, RuntimeError, subprocess.TimeoutExpired):
                # A leftover synthetic fixture must be handled separately;
                # never attempt broad cleanup.
                pass


if __name__ == "__main__":
    import json
    try:
        if len(sys.argv) != 2:
            raise ValueError("Missing trusted SSH config")
        print(json.dumps(run(sys.argv[1]), sort_keys=True))
    except Exception as exc:
        print(json.dumps({
            "classification": "MOJPLAYWIN_SYNTHETIC_ENCRYPTED_CHUNK_RELAY",
            "failure_class": type(exc).__name__,
            "real_backup_created": False,
            "release_permitted": False,
        }, sort_keys=True))
        raise SystemExit(2)
