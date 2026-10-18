#!/usr/bin/env python3
"""End-to-end synthetic cPanel source-side encryption -> VPS ciphertext -> CI recovery.

The staging source is a temporary 2MiB random fixture on cPanel, not customer
data. cPanel generates and holds the throwaway key. The key is returned solely
to the trusted temporary CI runner (test-only), never sent to VPS or logs.
All remote writes are limited to freshly allocated private /tmp directories.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time

from mojplaywin_chunked_encrypted_snapshot import verify, restore

FIXTURE_BYTES = 2 * 1024 * 1024 + 117
NAMES = ["plan.json", "manifest.json", "part-000000.bin", "part-000001.bin", "part-000002.bin"]
TEMP_PATTERN = re.compile(r"^/tmp/mjwp-srcaead-[A-Za-z0-9]{8}$")


def command(config, host, cmd, data=None, timeout=40):
    process = subprocess.run(
        ["ssh", "-T", "-F", config, host, cmd],
        input=data, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
        timeout=timeout, check=False,
    )
    if process.returncode != 0:
        raise RuntimeError("SSH source/destination stage failed")
    if len(process.stdout) > 4 * 1024 * 1024:
        raise RuntimeError("Unexpectedly large remote output")
    return process.stdout


def transfer_cipher(config, src, dest):
    sender = subprocess.Popen(
        ["ssh", "-T", "-F", config, "saeit-cpanel", "cat '" + src + "'"],
        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
    )
    receiver = None
    try:
        receiver = subprocess.Popen(
            ["ssh", "-T", "-F", config, "saeit-vps",
             "umask 077; test ! -e '" + dest + "' && cat > '" + dest + "'"],
            stdin=sender.stdout, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
        )
        sender.stdout.close()
        receiver.communicate(timeout=48)
        sender.wait(timeout=5)
        if sender.returncode or receiver.returncode:
            raise RuntimeError("Incomplete encrypted chunk transfer")
    finally:
        for proc in (sender, receiver):
            if proc is not None and proc.poll() is None:
                proc.kill()
                proc.wait()


def sha(config, host, path):
    out = command(config, host, "sha256sum '" + path + "'", timeout=30).decode("ascii").split()
    if len(out) < 2 or not re.fullmatch(r"[a-f0-9]{64}", out[0]):
        raise RuntimeError("Remote ciphertext checksum unavailable")
    return out[0]


def stage_code(source_path):
    lib = base64.b64encode(Path(source_path).read_bytes()).decode("ascii")
    return (
        "import base64,hashlib,json,os,sys\n"
        "from pathlib import Path\n"
        "base=Path(sys.argv[1])\n"
        "if not base.is_dir() or base.is_symlink(): raise RuntimeError('Unsafe fixture')\n"
        "ns={'__name__':'mjwp_experimental_chunk_library'}\n"
        f"exec(compile(base64.b64decode({lib!r}), '<offline_backup_code>', 'exec'),ns)\n"
        "key=base/'ephemeral.key'\n"
        "fd=os.open(str(key),os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)\n"
        "with os.fdopen(fd,'wb') as f: f.write(os.urandom(32))\n"
        f"data=os.urandom({FIXTURE_BYTES})\n"
        "snapshot=base/'random-fixture.bin'\n"
        "snapshot.write_bytes(data)\n"
        "res=ns['stage'](snapshot,base/'chunks','source-test-001',key,1048576)\n"
        "if res.get('status')!='verified_complete': raise RuntimeError('Stage failed')\n"
        "print(json.dumps({'source_digest':hashlib.sha256(data).hexdigest(),'chunks':3,'staged':True},sort_keys=True))\n"
    )


def main(config, offline_chunk_module):
    source_dir = None
    vps_dir = None
    try:
        source_dir = command(config, "saeit-cpanel",
                             "umask 077; mktemp -d /tmp/mjwp-srcaead-XXXXXXXX").decode("ascii").strip()
        vps_dir = command(config, "saeit-vps",
                          "umask 077; mktemp -d /tmp/mjwp-srcaead-XXXXXXXX").decode("ascii").strip()
        if not TEMP_PATTERN.fullmatch(source_dir) or not TEMP_PATTERN.fullmatch(vps_dir):
            raise RuntimeError("Temporary path is not restricted")
        info = json.loads(command(config, "saeit-cpanel",
                    "python3 - '" + source_dir + "'",
                    stage_code(offline_chunk_module).encode("ascii"), timeout=75))
        if not info.get("staged") or info.get("chunks") != 3:
            raise RuntimeError("Source-side encryption never completed")
        stagepath = source_dir + "/chunks/source-test-001"
        source_hash = info.get("source_digest")
        if not isinstance(source_hash, str) or not re.fullmatch(r"[0-9a-f]{64}", source_hash):
            raise RuntimeError("Source digest missing")
        vpsstage = vps_dir
        # Intentionally interrupt after first chunk; it must be reused on resume.
        first = NAMES[2]
        transfer_cipher(config, stagepath + "/" + first, vpsstage + "/" + first)
        if sha(config, "saeit-cpanel", stagepath + "/" + first) != sha(config, "saeit-vps", vpsstage + "/" + first):
            raise RuntimeError("First chunk corrupted")
        resumed = 0
        for name in NAMES:
            source_sha = sha(config, "saeit-cpanel", stagepath + "/" + name)
            if name == first:
                if sha(config, "saeit-vps", vpsstage + "/" + name) != source_sha:
                    raise RuntimeError("Resume digest mismatch")
                continue
            transfer_cipher(config, stagepath + "/" + name, vpsstage + "/" + name)
            if sha(config, "saeit-vps", vpsstage + "/" + name) != source_sha:
                raise RuntimeError("Ciphertext changed in transfer")
            resumed += 1
        with tempfile.TemporaryDirectory(prefix="mjwp-synthetic-cpanel-restoration-") as td:
            root = Path(td)
            os.chmod(root, 0o700)
            key_bytes = command(config, "saeit-cpanel", "cat '" + source_dir + "/ephemeral.key'", timeout=30)
            if len(key_bytes) != 32:
                raise RuntimeError("Invalid synthetic test key")
            key = root / "ephemeral.key"
            fd = os.open(str(key), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "wb") as out:
                out.write(key_bytes)
            recvroot = root / "ciphertext"
            recvroot.mkdir(mode=0o700)
            recvfolder = recvroot / "source-test-001"
            recvfolder.mkdir(mode=0o700)
            for name in NAMES:
                blob = command(config, "saeit-vps", "cat '" + vpsstage + "/" + name + "'", timeout=45)
                (recvfolder / name).write_bytes(blob)
                os.chmod(recvfolder / name, 0o600)
            verify(recvroot, "source-test-001", key)
            recovered = root / "recovered.bin"
            restore(recvroot, "source-test-001", key, recovered)
            if recovered.stat().st_size != FIXTURE_BYTES or hashlib.sha256(recovered.read_bytes()).hexdigest() != source_hash:
                raise RuntimeError("Source and restored fixture differ")
        return {
            "classification": "CPANEL_TO_VPS_SYNTHETIC_ENCRYPTED_CHUNK_RECOVERY",
            "source_encryption_performed_on_cpanel": True,
            "chunks": 3,
            "ciphertext_parts_resumed": resumed,
            "source_checksum_matches_restored_file": True,
            "key_transmitted_to_vps": False,
            "isolated_recovery_complete": True,
            "real_production_backup_created": False,
            "release_permitted": False,
        }
    finally:
        for host, folder in (("saeit-cpanel", source_dir), ("saeit-vps", vps_dir)):
            if folder and TEMP_PATTERN.fullmatch(folder):
                try:
                    command(config, host, "rm -rf -- '" + folder + "' && test ! -e '" + folder + "'", timeout=40)
                except (OSError, RuntimeError, subprocess.TimeoutExpired):
                    # Failure is logged as status of the separate test; never widen deletion.
                    pass


if __name__ == "__main__":
    try:
        if len(sys.argv) != 3:
            raise ValueError("Need SSH config and local offline chunk source")
        print(json.dumps(main(sys.argv[1], sys.argv[2]), sort_keys=True))
    except Exception as exc:
        print(json.dumps({
            "classification": "CPANEL_TO_VPS_SYNTHETIC_ENCRYPTED_CHUNK_RECOVERY",
            "error_type": type(exc).__name__,
            "real_production_backup_created": False,
            "release_permitted": False,
        }, sort_keys=True))
        raise SystemExit(2)
