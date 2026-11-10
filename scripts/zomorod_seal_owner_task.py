"""Offline-only envelope generator for the existing cPanel owner-command ingress.

This tool writes an encrypted GitHub Issue comment body, never posts it.
The corresponding private recipient key remains on cPanel and is rotated after
every accepted task; always obtain the *current* public key before sealing.

Example:
  python3 scripts/zomorod_seal_owner_task.py \
      --public-key current-recipient-public.pem \
      --task-file owner-task.json --output sealed-comment.txt

Do not send the output to issue #1600 without explicit owner authorization.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import hmac
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys


MARKER = "ZMR-SEALED-COMMAND-V1\n"
MAGIC = b"ZOMOROD-CHAT-COMMAND-V1\x00"
ALGORITHM = "RSA-OAEP-256+A256CBC-HS256"
MAX_PLAINTEXT = 8192
MAX_ENVELOPE = 24000
WORKSTREAMS = frozenset((
    "company", "finance", "sales", "inventory", "personnel",
    "projects", "research", "operations",
))
PRIORITIES = frozenset(("normal", "high", "critical"))
RISKS = frozenset(("read_only", "internal_write", "high_impact"))
TASK_FIELDS = frozenset((
    "workstream", "priority", "risk", "title", "detail",
    "deliverable", "acceptance",
))
TEXT_LIMITS = {"title": 160, "detail": 2000, "deliverable": 500, "acceptance": 1000}


class SealError(ValueError):
    """Safe error that does not include plaintext or cryptographic material."""


def _no_duplicates(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise SealError("DUPLICATE_JSON_KEY")
        result[key] = value
    return result


def parse_task(raw: bytes) -> dict[str, str]:
    if not 0 < len(raw) <= MAX_PLAINTEXT:
        raise SealError("TASK_INPUT_SIZE_INVALID")
    try:
        task = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=_no_duplicates,
            parse_constant=lambda _: (_ for _ in ()).throw(SealError("INVALID_NUMBER")),
        )
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise SealError("TASK_JSON_INVALID") from exc
    if not isinstance(task, dict) or frozenset(task) != TASK_FIELDS:
        raise SealError("TASK_FIELDS_INVALID")
    if any(not isinstance(v, str) for v in task.values()):
        raise SealError("TASK_TEXT_REQUIRED")
    if task["workstream"] not in WORKSTREAMS:
        raise SealError("WORKSTREAM_INVALID")
    if task["priority"] not in PRIORITIES or task["risk"] not in RISKS:
        raise SealError("TASK_CLASSIFICATION_INVALID")
    for field, limit in TEXT_LIMITS.items():
        value = task[field].strip()
        if (
            not value or len(value) > limit
            or any(ord(ch) < 32 and ch not in "\t\n" for ch in value)
        ):
            raise SealError("TASK_TEXT_INVALID")
    return task


def _openssl(*args: str, input_bytes: bytes) -> bytes:
    try:
        result = subprocess.run(
            ["openssl", *args], input=input_bytes, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, timeout=10, check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise SealError("OPENSSL_UNAVAILABLE") from exc
    if result.returncode != 0:
        raise SealError("ENCRYPTION_FAILED")
    return result.stdout


def seal_task(public_key: Path, task: dict[str, str]) -> str:
    if not public_key.is_file() or public_key.is_symlink():
        raise SealError("PUBLIC_KEY_UNAVAILABLE")
    if not 0 < public_key.stat().st_size < 8192:
        raise SealError("PUBLIC_KEY_SIZE_INVALID")
    # Validate again even for programmatic callers.
    task = parse_task(json.dumps(task, ensure_ascii=False).encode("utf-8"))
    payload = {"v": 1, "id": secrets.token_hex(16), "task": task}
    plaintext = json.dumps(
        payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True,
    ).encode("utf-8")
    if len(plaintext) > MAX_PLAINTEXT:
        raise SealError("PLAINTEXT_TOO_LARGE")

    aes_key = secrets.token_bytes(32)
    mac_key = secrets.token_bytes(32)
    iv = secrets.token_bytes(16)
    wrapped = _openssl(
        "pkeyutl", "-encrypt", "-pubin", "-inkey", str(public_key),
        "-pkeyopt", "rsa_padding_mode:oaep",
        "-pkeyopt", "rsa_oaep_md:sha256",
        input_bytes=aes_key + mac_key,
    )
    if len(wrapped) != 384:  # Current private ingress uses RSA-3072.
        raise SealError("PUBLIC_KEY_SIZE_MISMATCH")
    ciphertext = _openssl(
        "enc", "-aes-256-cbc", "-nosalt", "-K", aes_key.hex(),
        "-iv", iv.hex(), input_bytes=plaintext,
    )
    mac = hmac.new(mac_key, MAGIC + wrapped + iv + ciphertext, hashlib.sha256).digest()
    envelope = {
        "v": 1, "alg": ALGORITHM,
        "ek": base64.b64encode(wrapped).decode("ascii"),
        "iv": base64.b64encode(iv).decode("ascii"),
        "ct": base64.b64encode(ciphertext).decode("ascii"),
        "mac": base64.b64encode(mac).decode("ascii"),
    }
    encoded = json.dumps(envelope, separators=(",", ":"), sort_keys=True)
    if len(encoded.encode("utf-8")) > MAX_ENVELOPE:
        raise SealError("ENVELOPE_TOO_LARGE")
    return MARKER + encoded + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--public-key", required=True, type=Path)
    parser.add_argument("--task-file", required=True, type=Path)
    parser.add_argument("--output", type=Path, help="New file; created mode 0600; no overwrite")
    args = parser.parse_args(argv)
    try:
        if not args.task_file.is_file() or args.task_file.is_symlink():
            raise SealError("TASK_FILE_UNAVAILABLE")
        task = parse_task(args.task_file.read_bytes())
        sealed = seal_task(args.public_key, task)
        if args.output is None:
            sys.stdout.write(sealed)
        else:
            fd = os.open(
                args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                0o600,
            )
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(sealed)
                handle.flush()
                os.fsync(handle.fileno())
            print("SEALED_COMMAND_FILE_CREATED")
        return 0
    except (SealError, OSError) as exc:
        reason = str(exc) if isinstance(exc, SealError) else "FILE_OPERATION_FAILED"
        print("SEAL_FAILED=" + reason, file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
