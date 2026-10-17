#!/usr/bin/env python3
"""VPS-only direct cPanel backup + isolated file restore; no production writes.
Source streams travel cPanel -> VPS via short-lived forwarded SSH agent.
Only outputs summaries. Never prints SQL, private files, credentials or keys.
"""
from __future__ import annotations
import base64
import json
import os
import re
import subprocess
import sys
import tempfile
import threading
import types
from pathlib import Path

HOST = "zohal.pws-dns.net"
FINGERPRINT = "SHA256:7gQbDdrCVLFQRVdY6DAw8lF70jvlPfbJQslYn787E04"

def module_from_b64(content, name):
    raw = base64.b64decode(content, validate=True)
    if len(raw) > 100000:
        raise RuntimeError("unexpected module size")
    module = types.ModuleType(name)
    module.__file__ = "<validated-repository-source>"
    exec(compile(raw, module.__file__, "exec"), module.__dict__)
    return module

def validated_stem(value):
    if not re.fullmatch(r"mojplaywin_20261017_direct_[0-9]{8,12}", value):
        raise RuntimeError("unsupported fixed run stem")
    return value

def ssh_options(known):
    return ["ssh", "-T", "-p", "1396",
            "-o", "UserKnownHostsFile=" + str(known),
            "-o", "StrictHostKeyChecking=yes",
            "-o", "BatchMode=yes",
            "-o", "ConnectTimeout=12",
            "-o", "ServerAliveInterval=25",
            "-o", "ServerAliveCountMax=3",
            "-o", "ForwardAgent=no",
            "zomorod2@" + HOST]

def verify_host(temp):
    if not os.getenv("SSH_AUTH_SOCK"):
        raise RuntimeError("temporary SSH agent unavailable")
    keyscan = subprocess.run(
        ["ssh-keyscan", "-T", "10", "-p", "1396", "-t", "ed25519", HOST],
        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=20, check=True)
    known = temp / "cpanel.known"
    known.write_bytes(keyscan.stdout)
    fingerprint = subprocess.run(["ssh-keygen", "-lf", str(known), "-E", "sha256"],
                                 stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                 timeout=8, check=True).stdout.decode("ascii")
    if FINGERPRINT not in fingerprint or len(fingerprint.splitlines()) != 1:
        raise RuntimeError("cPanel SSH identity mismatch")
    return known

def direct_backup(args):
    if len(args) != 4:
        raise RuntimeError("source/encrypt/restore/stem required")
    source_code, crypto_code, _unused_restore, stem = args
    stem = validated_stem(stem)
    crypto = module_from_b64(crypto_code, "trusted_mojplaywin_gpg")
    crypto.STEM = stem
    with tempfile.TemporaryDirectory(prefix="mjwp-knownhost-") as td:
        known = verify_host(Path(td))
        for kind in ("mysql", "files"):
            print("DIRECT_BACKUP_" + kind.upper() + "_START", flush=True)
            python = "import base64,sys;code=sys.argv[1];sys.argv=[sys.argv[0]]+sys.argv[2:];exec(base64.b64decode(code))"
            command = ssh_options(known) + [
                "python3 -c '" + python + "' '" + source_code + "' '" + kind + "'"
            ]
            proc = subprocess.Popen(command, stdin=subprocess.DEVNULL,
                                    stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
            stop_heartbeat = threading.Event()
            def heartbeat():
                while not stop_heartbeat.wait(22):
                    parent = Path.home() / ".private-mojplaywin-offhost-backups"
                    part = parent / (stem + "_" + kind + "_" + crypto.VERSION + ".gpg.partial")
                    try:
                        size = part.stat().st_size // (1024 * 1024)
                    except OSError:
                        size = 0
                    print("DIRECT_BACKUP_" + kind.upper() +
                          "_ENCRYPTED_MIB=" + str(size), flush=True)
            pulse = threading.Thread(target=heartbeat, daemon=True)
            pulse.start()
            try:
                if proc.stdout is None:
                    raise RuntimeError("source pipe absent")
                # store is fail-closed: requires source completion marker, GPG
                # decrypt roundtrip and manifest. Never overwrites old archives.
                result = crypto.store(proc.stdout, kind)
                proc.stdout.close()
                if proc.wait(timeout=30) != 0:
                    raise RuntimeError("source SSH ended nonzero")
                print(json.dumps({"step": "DIRECT_BACKUP_VERIFIED",
                                  "kind": kind, "encrypted_bytes": result["encrypted_bytes"],
                                  "plaintext_bytes": result["plaintext_bytes"],
                                  "release_permitted": False}), flush=True)
            finally:
                stop_heartbeat.set()
                pulse.join(timeout=5)
                if proc.poll() is None:
                    proc.kill()
                    proc.wait()

def stream_recovery(args):
    if len(args) != 3:
        raise RuntimeError("recovery module/stem/kind required")
    r64, stem, kind = args
    validated_stem(stem)
    if kind not in ("mysql", "files"):
        raise RuntimeError("invalid recovery kind")
    recovery = module_from_b64(r64, "trusted_mojplaywin_recovery")
    recovery.STEM = stem
    recovery.decrypt_to_stdout(kind)

def restore_files(args):
    if len(args) != 3:
        raise RuntimeError("restorer/recovery/stem required")
    restore64, recovery64, stem = args
    validated_stem(stem)
    restorer = module_from_b64(restore64, "trusted_mojplaywin_safe_restorer")
    python = ("import base64,sys,types;"
              "m=types.ModuleType('recovery');"
              "exec(base64.b64decode(sys.argv[1]),m.__dict__);"
              "m.STEM=sys.argv[2];m.decrypt_to_stdout('files')")
    with tempfile.TemporaryDirectory(prefix=".mjwp-sandbox-recover-", dir=str(Path.home())) as td:
        os.chmod(td, 0o700)
        proc = subprocess.Popen(["python3", "-c", python, recovery64, stem],
                                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        try:
            if proc.stdout is None:
                raise RuntimeError("GPG restore stdout absent")
            report = restorer.recover(proc.stdout, Path(td))
            proc.stdout.close()
            if proc.wait(timeout=90):
                raise RuntimeError("GPG recovery integrity failure")
            if not report.get("restore_complete") or report.get("root_count_restored") != 2:
                raise RuntimeError("not all source roots restored")
            print(json.dumps({"step": "ISOLATED_FILE_RESTORE_VERIFIED",
                              "files": report["regular_files_restored"],
                              "bytes": report["regular_bytes_restored"],
                              "roots": report["root_count_restored"],
                              "production_modified": False}), flush=True)
        finally:
            if proc.poll() is None:
                proc.kill()
                proc.wait()

if __name__ == "__main__":
    try:
        if len(sys.argv) < 2:
            raise RuntimeError("missing mode")
        mode, args = sys.argv[1], sys.argv[2:]
        if mode == "backup":
            direct_backup(args)
        elif mode == "recover-mysql":
            stream_recovery([*args, "mysql"])
        elif mode == "restore-files":
            restore_files(args)
        else:
            raise RuntimeError("invalid mode")
    except Exception as exc:
        print("DIRECT_ONEPASS_FAILED_NO_RELEASE_TYPE=" + type(exc).__name__, file=sys.stderr)
        raise SystemExit(1)
