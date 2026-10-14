"""Isolated read-only signing verifier, run in an independent Python venv.

Protocol: one <4KB JSON line on stdin; boolean result on stdout.
Never reads private keys, accesses blockchain, touches database or OpenAI.
This is an alternate runtime to avoid changing the website's pip packages.
"""
import hashlib
import json
import re
import sys

ETH = "0x89149b01f59115B86553561F12438D2ADF517E75"
TRX = "THFNU1iEXHd71WjEgjqUksd2UnMg2pUi73"
ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"


def tron_to_hex(address):
    if not isinstance(address, str) or not 26 <= len(address) <= 36:
        raise ValueError("bad TRON address")
    number = 0
    for c in address:
        number = number * 58 + ALPHABET.index(c)
    value = number.to_bytes(25, "big")
    if (value[0] != 0x41 or
            hashlib.sha256(hashlib.sha256(value[:21]).digest()).digest()[:4]
            != value[21:]):
        raise ValueError("bad TRON checksum")
    return value[:21].hex()


def verify(payload):
    if not isinstance(payload, dict) or set(payload) != {"asset", "message", "signature"}:
        return False
    asset, message, signature = (payload[k] for k in ("asset", "message", "signature"))
    if (asset not in ("ETH","TRX") or not isinstance(message, str) or
        not 60 <= len(message) <= 1000 or not isinstance(signature, str) or
        not re.fullmatch(r"(?:0x)?[0-9A-Fa-f]{130}", signature)):
        return False
    raw = bytes.fromhex(signature[2:] if signature.startswith("0x") else signature)
    recovery = raw[-1] - 27 if raw[-1] >= 27 else raw[-1]
    if recovery not in (0,1):
        return False
    if asset == "ETH":
        from eth_account import Account
        from eth_account.messages import encode_defunct
        return Account.recover_message(
            encode_defunct(text=message), signature=raw,
        ).lower() == ETH.lower()
    from eth_keys import keys
    from eth_utils import keccak
    digest = keccak(b"\x19TRON Signed Message:\n" +
                    str(len(message.encode("utf-8"))).encode("ascii") +
                    message.encode("utf-8"))
    recovered = keys.Signature(
        signature_bytes=raw[:64] + bytes([recovery])
    ).recover_public_key_from_msg_hash(digest)
    return "41" + keccak(recovered.to_bytes())[-20:].hex() == tron_to_hex(TRX)


def main():
    try:
        raw = sys.stdin.buffer.read(4097)
        if len(raw) > 4096:
            raise ValueError("oversize request")
        value = json.loads(raw.decode("utf-8"))
        ok = verify(value)
    except Exception:
        ok = False
    sys.stdout.write('{"verified":' + ('true' if ok else 'false') + "}\n")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
