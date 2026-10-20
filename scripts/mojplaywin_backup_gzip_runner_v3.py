#!/usr/bin/env python3
"""Owner-triggered v3 compressed encrypted scoped backup over an ALREADY pinned SSH config.

Run only in a protected operator job after an independently authorized action.
The operator first creates the same ephemeral host-key-pinned SSH config as the
existing read-only cPanel inventory workflow; this runner does NOT read or
manage credentials, mutate sites, import SQL, restart Passenger, remove older
backups, delete partials, or publish goods.

A failed transfer leaves a uniquely versioned .partial in a private VPS dir,
and MUST NOT be described as a verified backup or release approval.
"""
from __future__ import annotations
import argparse
import base64
import json
import os
import re
import shlex
import signal
import stat
import subprocess
import sys
from pathlib import Path

EXPECTED_SOURCE = "scripts/mojplaywin_backup_gzip_source_v3.py"
EXPECTED_DEST = "scripts/mojplaywin_backup_encrypt_vps_gpg.py"


def checked_config(path: Path):
    if path.is_symlink() or not path.is_file():
        raise ValueError("SSH_CONFIG_ABSENT")
    st = path.stat()
    if st.st_mode & 0o077 or st.st_uid != os.getuid():
        raise ValueError("SSH_CONFIG_PERMISSIONS")
    data = path.read_text("ascii")
    if "StrictHostKeyChecking yes" not in data or "BatchMode yes" not in data:
        raise ValueError("SSH_STRICT_HOST_POLICY_REQUIRED")
    if "ProxyJump saeit-vps" not in data or "Host saeit-cpanel" not in data:
        raise ValueError("EXPECTED_SCOPED_RELAY_NOT_CONFIGURED")
    return path


def script_bytes(path, basename):
    src = Path(path)
    if src.is_symlink() or not src.is_file() or src.name != basename:
        raise ValueError("UNEXPECTED_BACKUP_SOURCE")
    payload = src.read_bytes()
    if not 1024 < len(payload) <= 100000:
        raise ValueError("UNBOUNDED_BACKUP_CODE")
    return base64.b64encode(payload).decode("ascii")


def remote_command(encoded, kind, *, stem=None):
    if kind not in ("mysql", "files"):
        raise ValueError("UNKNOWN_BACKUP_KIND")
    if stem is None:
        code = ("import base64,sys;"
                "payload,kind=sys.argv[1:3];"
                "sys.argv=['backup_source',kind];"
                "exec(base64.b64decode(payload))")
        arguments = [encoded, kind]
    else:
        if not re.fullmatch(r"mojplaywin_20\d{6}", stem):
            raise ValueError("INVALID_BACKUP_VERSION")
        code = ("import base64,json,sys;"
                "payload,kind,stem=sys.argv[1:4];"
                "scope={'__name__':'v3_backup_receiver'};"
                "exec(base64.b64decode(payload),scope);"
                "receipt=scope['store'](sys.stdin.buffer,kind,stem=stem,"
                "source_encoding='gzip-with-footer-v1');"
                "print(json.dumps(receipt,sort_keys=True))")
        arguments = [encoded, kind, stem]
    return "python3 -c " + shlex.quote(code) + " " + " ".join(map(shlex.quote, arguments))


def transfer(config, source, receiver, kind, *, stem, timeout=7200):
    if not 1 <= timeout <= 7200:
        raise ValueError("BACKUP_TIMEOUT_OUTSIDE_SAFE_BOUNDS")
    src_remote = remote_command(source, kind)
    dst_remote = remote_command(receiver, kind, stem=stem)
    src_args = ["ssh", "-T", "-F", str(config), "saeit-cpanel", src_remote]
    dst_args = ["ssh", "-T", "-F", str(config), "saeit-vps", dst_remote]
    producer = subprocess.Popen(src_args, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                start_new_session=True)
    consumer = None
    try:
        consumer = subprocess.Popen(dst_args, stdin=producer.stdout,
                                    stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                    start_new_session=True)
        producer.stdout.close()
        response, _ = consumer.communicate(timeout=timeout)
        source_rc = producer.wait(timeout=60)
        if source_rc or consumer.returncode or len(response) > 8192:
            raise RuntimeError("PRIVATE_ENCRYPTED_STREAM_INCOMPLETE")
        try:
            receipt = json.loads(response.decode("ascii"))
        except (ValueError, UnicodeError):
            raise RuntimeError("MISSING_VERIFIED_PRIVATE_RECEIPT") from None
        if (receipt.get("kind") != kind or
            receipt.get("gpg_aes256_backup_created") is not True or
            receipt.get("decryption_verified") is not True or
            receipt.get("source_complete") is not True or
            receipt.get("source_encoding") != "gzip-with-footer-v1" or
            receipt.get("release_permitted") is not False):
            raise RuntimeError("INCOMPLETE_BACKUP_VERIFICATION")
        return {
            "kind": kind,
            "source_complete": True,
            "encrypted_archive_roundtrip_verified": True,
            "isolated_restore_verified": False,
            "release_permitted": False,
        }
    finally:
        for child in (consumer, producer):
            if child is not None and child.poll() is None:
                try:
                    os.killpg(child.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                child.wait()


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--ssh-config", required=True)
    p.add_argument("--date", required=True)
    p.add_argument("--source", default=EXPECTED_SOURCE)
    p.add_argument("--receiver", default=EXPECTED_DEST)
    p.add_argument("--owner-approved", action="store_true")
    p.add_argument("--fixture", action="store_true")
    args = p.parse_args()
    if not re.fullmatch(r"20\d{6}", args.date):
        raise ValueError("BAD_BACKUP_DATE")
    stem = "mojplaywin_" + args.date
    source = script_bytes(args.source, EXPECTED_SOURCE)
    receiver = script_bytes(args.receiver, EXPECTED_DEST)
    if args.fixture:
        for kind in ("mysql", "files"):
            a = remote_command(source, kind)
            b = remote_command(receiver, kind, stem=stem)
            assert "python3 -c " in a and "python3 -c " in b
        print("V3_BACKUP_DRIVER_FIXTURE=PASS")
        return
    if not args.owner_approved:
        raise RuntimeError("EXPLICIT_OWNER_BACKUP_APPROVAL_REQUIRED")
    config = checked_config(Path(args.ssh_config))
    for kind in ("mysql", "files"):
        receipt = transfer(config, source, receiver, kind, stem=stem)
        print(json.dumps(receipt, sort_keys=True))
    print("V3_PRIVATE_SCOPED_BACKUP_ENCRYPTED_AND_VERIFIED; ISOLATED_RESTORE_STILL_REQUIRED")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        # Never print full remote errors or credentials / SQL / paths.
        print("V3_PRIVATE_BACKUP_NOT_VERIFIED_NO_RELEASE", file=sys.stderr)
        raise SystemExit(1)
