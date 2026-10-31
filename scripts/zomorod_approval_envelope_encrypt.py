#!/usr/bin/env python3
"""Encrypt one owner-approved private CSV for the cPanel-only approval receiver.

The resulting JSON contains ciphertext only. Never publish the input CSV or key.
"""
import argparse
import base64
import gzip
import hashlib
import json
import os
from pathlib import Path
import secrets
import time

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

PURPOSE = "zomorod-approval-csv-import-20261031-v1"
EXPECTED_SHA = "40c09b1aff17143cf315884177b61a35c6b1d62aa30a445056cfd8303deb3366"
EXPECTED_SIZE = 52072


def b64(data):
    return base64.b64encode(data).decode("ascii")


def envelope(csv_bytes, public_pem, now=None):
    if len(csv_bytes) != EXPECTED_SIZE or hashlib.sha256(csv_bytes).hexdigest() != EXPECTED_SHA:
        raise ValueError("The private CSV does not match the approved source bytes")
    public = serialization.load_pem_public_key(public_pem)
    if not isinstance(public, rsa.RSAPublicKey) or public.key_size < 3072:
        raise ValueError("Recipient public key must be RSA 3072 bits or stronger")
    key = secrets.token_bytes(32)
    nonce = secrets.token_bytes(12)
    issued = int(time.time() if now is None else now)
    aad = f"{PURPOSE}|{EXPECTED_SIZE}|{EXPECTED_SHA}|{issued}".encode("ascii")
    compressed = gzip.compress(csv_bytes, compresslevel=9, mtime=0)
    ciphertext_and_tag = AESGCM(key).encrypt(nonce, compressed, aad)
    wrapped = public.encrypt(key, padding.OAEP(mgf=padding.MGF1(algorithm=hashes.SHA1()), algorithm=hashes.SHA1(), label=None))
    result = {
        "v": 1,
        "purpose": PURPOSE,
        "alg": "RSA-OAEP-SHA1+AES-256-GCM+GZIP",
        "issued_at": issued,
        "sha256": EXPECTED_SHA,
        "plain_size": EXPECTED_SIZE,
        "ek": b64(wrapped),
        "iv": b64(nonce),
        "ct": b64(ciphertext_and_tag[:-16]),
        "tag": b64(ciphertext_and_tag[-16:]),
    }
    return json.dumps(result, separators=(",", ":"), sort_keys=True).encode("ascii")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", type=Path, required=True)
    ap.add_argument("--public-key", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()
    payload = envelope(args.csv.read_bytes(), args.public_key.read_bytes())
    if len(payload) > 22000:
        raise SystemExit("Encrypted envelope exceeds strict transfer cap")
    fd = os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as out:
        out.write(payload + b"\n")
        out.flush()
        os.fsync(out.fileno())
    print("APPROVAL_ENCRYPTED_ENVELOPE=CREATED")
    print("ENVELOPE_BYTES=" + str(len(payload)))
    print("SOURCE_SHA256=" + EXPECTED_SHA)
    print("SOURCE_CONTENT_LOGGED=no")


if __name__ == "__main__":
    main()
