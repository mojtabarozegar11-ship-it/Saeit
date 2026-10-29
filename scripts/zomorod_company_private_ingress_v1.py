#!/usr/bin/env python3
"""Encrypted, authenticated ingress for the private Zomorod task bridge.

The GitHub relay carries ciphertext only. The HMAC key and the one-use RSA
private key stay in the cPanel private directory. Accepted commands create
reviewable tasks; this module never executes company work.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import importlib.util
import json
import os
import re
import secrets
import subprocess
import sys
import time
from pathlib import Path

MAX_ENVELOPE = 24_000
MAX_PLAINTEXT = 8_192
HEX32 = re.compile(r"^[0-9a-f]{32}$")
OUTER_FIELDS = frozenset(("v", "alg", "ek", "iv", "ct", "mac"))
INNER_FIELDS = frozenset(("v", "id", "task"))
MAGIC = b"ZOMOROD-CHAT-COMMAND-V1\x00"


class Reject(Exception):
    pass


def load_bridge():
    local = Path(__file__).with_name("company_bridge.py")
    if not local.exists():
        local = Path(__file__).with_name("zomorod_company_private_bridge_v4.py")
    spec = importlib.util.spec_from_file_location("company_bridge", local)
    if spec is None or spec.loader is None:
        raise Reject("bridge_unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise Reject("duplicate_json_key")
        result[key] = value
    return result


def _json(raw: bytes):
    try:
        return json.loads(raw.decode("utf-8"), object_pairs_hook=_pairs,
                          parse_constant=lambda _: (_ for _ in ()).throw(Reject("nonfinite")))
    except (ValueError, UnicodeError) as exc:
        raise Reject("malformed_json") from exc


def _b64(value, maximum):
    if not isinstance(value, str) or len(value) > maximum * 2:
        raise Reject("invalid_base64")
    try:
        return base64.b64decode(value, validate=True)
    except (ValueError, TypeError) as exc:
        raise Reject("invalid_base64") from exc


def _safe_private_key(path: Path, bridge) -> Path:
    bridge.private_path(path)
    if path.stat().st_mode & 0o077:
        raise Reject("unsafe_recipient_key_permissions")
    return path


def public_key_pem(private_key: Path) -> bytes:
    result = subprocess.run(
        ["openssl", "pkey", "-in", str(private_key), "-pubout"],
        stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL, timeout=8, check=False,
    )
    if result.returncode or not result.stdout.startswith(b"-----BEGIN PUBLIC KEY-----"):
        raise Reject("recipient_key_unavailable")
    return result.stdout


def initialize_or_rotate_key(private_key: Path, bridge, *, rotate: bool = False) -> None:
    bridge.private_path(private_key, must_exist=False)
    if private_key.exists() and not rotate:
        _safe_private_key(private_key, bridge)
        public_key_pem(private_key)
        return
    temporary = private_key.with_name(private_key.name + ".next")
    if temporary.exists() or temporary.is_symlink():
        raise Reject("key_rotation_incomplete")
    result = subprocess.run(
        ["openssl", "genpkey", "-algorithm", "RSA", "-pkeyopt",
         "rsa_keygen_bits:3072", "-out", str(temporary)],
        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL, timeout=30, check=False,
    )
    if result.returncode or not temporary.is_file() or temporary.is_symlink():
        temporary.unlink(missing_ok=True)
        raise Reject("recipient_key_generation_failed")
    os.chmod(temporary, 0o600)
    public_key_pem(temporary)
    os.replace(temporary, private_key)
    os.chmod(private_key, 0o600)


def decrypt(raw: bytes, private_key: Path, bridge) -> tuple[str, dict]:
    if not 2 <= len(raw) <= MAX_ENVELOPE:
        raise Reject("invalid_envelope_size")
    envelope = _json(raw)
    if not isinstance(envelope, dict) or frozenset(envelope) != OUTER_FIELDS:
        raise Reject("invalid_envelope_fields")
    if envelope["v"] != 1 or envelope["alg"] != "RSA-OAEP-256+A256CBC-HS256":
        raise Reject("unsupported_envelope")
    wrapped = _b64(envelope["ek"], 1_024)
    iv = _b64(envelope["iv"], 32)
    ciphertext = _b64(envelope["ct"], MAX_PLAINTEXT + 64)
    supplied_mac = _b64(envelope["mac"], 64)
    if len(wrapped) != 384 or len(iv) != 16 or not ciphertext or len(ciphertext) % 16 or len(supplied_mac) != 32:
        raise Reject("invalid_ciphertext_shape")

    decrypted = subprocess.run(
        ["openssl", "pkeyutl", "-decrypt", "-inkey", str(private_key),
         "-pkeyopt", "rsa_padding_mode:oaep", "-pkeyopt", "rsa_oaep_md:sha256"],
        input=wrapped, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
        timeout=8, check=False,
    )
    if decrypted.returncode or len(decrypted.stdout) != 64:
        raise Reject("key_unwrap_failed")
    aes_key, mac_key = decrypted.stdout[:32], decrypted.stdout[32:]
    expected_mac = hmac.new(mac_key, MAGIC + wrapped + iv + ciphertext, hashlib.sha256).digest()
    if not hmac.compare_digest(expected_mac, supplied_mac):
        raise Reject("ciphertext_authentication_failed")

    opened = subprocess.run(
        ["openssl", "enc", "-d", "-aes-256-cbc", "-nosalt", "-K",
         aes_key.hex(), "-iv", iv.hex()],
        input=ciphertext, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
        timeout=8, check=False,
    )
    if opened.returncode or len(opened.stdout) > MAX_PLAINTEXT:
        raise Reject("payload_decryption_failed")
    payload = _json(opened.stdout)
    if not isinstance(payload, dict) or frozenset(payload) != INNER_FIELDS:
        raise Reject("invalid_command_fields")
    if type(payload["v"]) is not int or payload["v"] != 1:
        raise Reject("invalid_command_version")
    if not isinstance(payload["id"], str) or not HEX32.fullmatch(payload["id"]):
        raise Reject("invalid_command_id")
    if not isinstance(payload["task"], dict):
        raise Reject("invalid_task")
    return payload["id"], payload["task"]


def accept(raw: bytes, db: Path, hmac_key: Path, recipient_key: Path, now=None) -> str:
    bridge = load_bridge()
    _safe_private_key(hmac_key, bridge)
    _safe_private_key(recipient_key, bridge)
    command_id, task = decrypt(raw, recipient_key, bridge)
    now = int(time.time() if now is None else now)
    body = {"v": 1, "id": command_id, "ts": now, "op": "task.create", "task": task}
    signature = hmac.new(bridge.read_key(hmac_key), bridge.canonical_body(body),
                         hashlib.sha256).hexdigest()
    signed = {**body, "sig": signature}
    result = bridge.import_task(db, bridge.canonical_body(signed),
                                bridge.read_key(hmac_key), now)
    if result == "ACCEPTED":
        initialize_or_rotate_key(recipient_key, bridge, rotate=True)
    return result


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("init-recipient", "show-public-key", "accept"))
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--hmac-key", type=Path, required=True)
    parser.add_argument("--recipient-key", type=Path, required=True)
    args = parser.parse_args()
    try:
        bridge = load_bridge()
        if args.action == "init-recipient":
            initialize_or_rotate_key(args.recipient_key, bridge)
            print("RECIPIENT_KEY=READY")
        elif args.action == "show-public-key":
            _safe_private_key(args.recipient_key, bridge)
            print("COMMAND_PUBLIC_KEY_BEGIN")
            sys.stdout.buffer.write(public_key_pem(args.recipient_key))
            print("COMMAND_PUBLIC_KEY_END")
        else:
            raw = sys.stdin.buffer.read(MAX_ENVELOPE + 1)
            result = accept(raw, args.db, args.hmac_key, args.recipient_key)
            print("COMMAND_RECEIPT=" + result)
            if result == "ACCEPTED":
                print("COMMAND_QUEUE=UPDATED")
                print("COMMAND_PUBLIC_KEY_BEGIN")
                sys.stdout.buffer.write(public_key_pem(args.recipient_key))
                print("COMMAND_PUBLIC_KEY_END")
            else:
                print("COMMAND_QUEUE=UNCHANGED")
        return 0
    except (Reject, OSError, subprocess.SubprocessError, ValueError):
        print("PRIVATE_COMMAND_INGRESS=REJECTED", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
