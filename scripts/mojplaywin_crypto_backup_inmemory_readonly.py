#!/usr/bin/env python3
"""VPS-only diagnostics of AES-GCM with in-memory, synthetic bytes.
Never reads filesystem data, wallet keys, backup keys, databases or production
files. Never writes files or starts a backup. Prints exception CLASS only.
"""
import importlib.util
import json
import sys


def _run():
    result = {
        "classification": "READ_ONLY_AES_GCM_IN_MEMORY_DIAGNOSTIC",
        "python_major_minor": list(sys.version_info[:2]),
        "module_detected": importlib.util.find_spec("cryptography") is not None,
        "cipher_api_imported": False,
        "cipher_roundtrip_passed": False,
        "highlevel_api_imported": False,
        "highlevel_roundtrip_passed": False,
        "failure_class": None,
        "backup_created": False,
        "backup_recovery_verified": False,
        "release_permitted": False,
    }
    key = bytes(range(32))
    nonce = bytes(range(12))
    plaintext = b"synthetic-vps-crypto-diagnostic-20261018"
    try:
        from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
        result["cipher_api_imported"] = True
        enc = Cipher(algorithms.AES(key), modes.GCM(nonce)).encryptor()
        cipher = enc.update(plaintext) + enc.finalize()
        dec = Cipher(algorithms.AES(key), modes.GCM(nonce, enc.tag)).decryptor()
        result["cipher_roundtrip_passed"] = (dec.update(cipher) + dec.finalize()) == plaintext
    except Exception as exc:
        result["failure_class"] = type(exc).__name__
    try:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        result["highlevel_api_imported"] = True
        cipher = AESGCM(key).encrypt(nonce, plaintext, b"synthetic")
        result["highlevel_roundtrip_passed"] = AESGCM(key).decrypt(nonce, cipher, b"synthetic") == plaintext
    except Exception as exc:
        if result["failure_class"] is None:
            result["failure_class"] = type(exc).__name__
    return result


if __name__ == "__main__":
    print(json.dumps(_run(), sort_keys=True))
