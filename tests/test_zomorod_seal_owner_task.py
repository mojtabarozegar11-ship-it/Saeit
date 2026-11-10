"""Independent OpenSSL round-trip checks; never touch GitHub or the live host."""

import base64
import hashlib
import hmac
import json
from pathlib import Path
import subprocess

import pytest

from scripts import zomorod_seal_owner_task as seal


@pytest.fixture(scope="module")
def keys(tmp_path_factory):
    folder = tmp_path_factory.mktemp("owner-keys")
    private_key = folder / "recipient-private.pem"
    public_key = folder / "recipient-public.pem"
    subprocess.run(
        ["openssl", "genpkey", "-algorithm", "RSA",
         "-pkeyopt", "rsa_keygen_bits:3072", "-out", str(private_key)],
        check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        timeout=20,
    )
    subprocess.run(
        ["openssl", "pkey", "-in", str(private_key), "-pubout", "-out", str(public_key)],
        check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        timeout=10,
    )
    return private_key, public_key


@pytest.fixture
def task():
    return {
        "workstream": "operations",
        "priority": "high",
        "risk": "read_only",
        "title": "Audit daily orders",
        "detail": "Check invoices without issuing payments.",
        "deliverable": "Documented order count",
        "acceptance": "Evidence-linked read-only report",
    }


def _openssl(args, payload):
    return subprocess.run(
        ["openssl", *args], input=payload, check=True,
        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=10,
    ).stdout


def test_real_rsa_aes_hmac_roundtrip(keys, task):
    private_key, public_key = keys
    body = seal.seal_task(public_key, task)
    assert body.startswith(seal.MARKER)
    envelope = json.loads(body[len(seal.MARKER):])
    assert set(envelope) == {"v", "alg", "ek", "iv", "ct", "mac"}
    assert envelope["v"] == 1
    assert envelope["alg"] == seal.ALGORITHM
    wrapped = base64.b64decode(envelope["ek"], validate=True)
    iv = base64.b64decode(envelope["iv"], validate=True)
    ciphertext = base64.b64decode(envelope["ct"], validate=True)
    mac = base64.b64decode(envelope["mac"], validate=True)
    unwrapped = _openssl([
        "pkeyutl", "-decrypt", "-inkey", str(private_key),
        "-pkeyopt", "rsa_padding_mode:oaep",
        "-pkeyopt", "rsa_oaep_md:sha256",
    ], wrapped)
    assert len(unwrapped) == 64
    aes_key, mac_key = unwrapped[:32], unwrapped[32:]
    expected = hmac.new(
        mac_key, seal.MAGIC + wrapped + iv + ciphertext, hashlib.sha256,
    ).digest()
    assert hmac.compare_digest(expected, mac)
    plaintext = _openssl([
        "enc", "-d", "-aes-256-cbc", "-nosalt", "-K", aes_key.hex(),
        "-iv", iv.hex(),
    ], ciphertext)
    payload = json.loads(plaintext)
    assert payload["v"] == 1
    assert len(payload["id"]) == 32
    assert payload["task"] == task
    assert body != seal.seal_task(public_key, task)  # Fresh keys and task ID.


@pytest.mark.parametrize("changes", [
    {"risk": "root_shell"},
    {"workstream": "remote_deploy"},
    {"priority": "supercritical"},
    {"detail": "x" * 2001},
    {"title": ""},
    {"acceptance": "bad\x00entry"},
    {"extra": "command"},
])
def test_invalid_task_is_rejected(keys, task, changes):
    task.update(changes)
    with pytest.raises(seal.SealError):
        seal.seal_task(keys[1], task)


def test_duplicate_task_keys_are_rejected():
    original = b'{"workstream":"company","workstream":"finance"}'
    with pytest.raises(seal.SealError, match="DUPLICATE_JSON_KEY"):
        seal.parse_task(original)


def test_cli_creates_private_output_and_refuses_overwrite(keys, task, tmp_path):
    task_file = tmp_path / "owner-task.json"
    task_file.write_text(json.dumps(task), encoding="utf-8")
    output = tmp_path / "sealed-comment.txt"
    argv = ["--public-key", str(keys[1]), "--task-file", str(task_file),
            "--output", str(output)]
    assert seal.main(argv) == 0
    original = output.read_text(encoding="utf-8")
    assert original.startswith(seal.MARKER)
    assert output.stat().st_mode & 0o777 == 0o600
    assert seal.main(argv) == 1
    assert output.read_text(encoding="utf-8") == original


def test_invalid_key_cannot_produce_envelope(keys, task, tmp_path):
    malformed = tmp_path / "not-key.pem"
    malformed.write_text("not a public key", encoding="utf-8")
    with pytest.raises(seal.SealError, match="ENCRYPTION_FAILED"):
        seal.seal_task(malformed, task)
