"""No-funds, isolated ETH/TRX signed-text verification for customer checkout.

Input: one JSON request from the trusted Django process. Output: one boolean.
Never loads private keys, sends tokens, approves allowances, or calls networks.
Designed to run using a separate minimal Python venv, not live Django's venv.
"""
import hashlib
import json
import re
import sys

BASE58="123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"


def tron_address_to_hex(address):
    if not isinstance(address,str) or not 30<=len(address)<=36:
        raise ValueError("Invalid TRON address")
    n=0
    for char in address:
        n=n*58+BASE58.index(char)
    value=n.to_bytes(25,"big")
    if (value[:1]!=b"\x41" or
        hashlib.sha256(hashlib.sha256(value[:21]).digest()).digest()[:4]!=value[21:]):
        raise ValueError("Invalid TRON checksum")
    return value[:21].hex()


def verify_message(request):
    if not isinstance(request,dict) or set(request)!={"asset","address","message","signature"}:
        return False
    asset,address,message,signature=(request[k] for k in
                                     ("asset","address","message","signature"))
    if (asset not in ("ETH","TRX") or not isinstance(address,str) or
        not isinstance(message,str) or not 50<=len(message)<=1500 or
        not isinstance(signature,str) or
        re.fullmatch(r"(?:0x)?[a-fA-F0-9]{130}",signature) is None):
        return False
    if asset=="ETH" and re.fullmatch(r"0x[a-fA-F0-9]{40}",address) is None:
        return False
    if asset=="TRX":
        try:
            expected_tron=tron_address_to_hex(address)
        except (ValueError,OverflowError):
            return False
    raw=bytes.fromhex(signature[2:] if signature.startswith("0x") else signature)
    recovery=raw[-1]-27 if raw[-1]>=27 else raw[-1]
    if recovery not in (0,1):
        return False
    if asset=="ETH":
        from eth_account import Account
        from eth_account.messages import encode_defunct
        recovered=Account.recover_message(
            encode_defunct(text=message),signature=raw,
        )
        return recovered.lower()==address.lower()
    from eth_keys import keys
    from eth_utils import keccak
    payload=message.encode("utf-8")
    digest=keccak(b"\x19TRON Signed Message:\n"+
                  str(len(payload)).encode("ascii")+payload)
    public=keys.Signature(
        signature_bytes=raw[:64]+bytes([recovery])
    ).recover_public_key_from_msg_hash(digest)
    return ("41"+keccak(public.to_bytes())[-20:].hex())==expected_tron


def main():
    try:
        doc=sys.stdin.buffer.read(4097)
        if len(doc)>4096:
            raise ValueError("Signature request too large")
        checked=verify_message(json.loads(doc.decode("utf-8")))
    except Exception:
        checked=False
    sys.stdout.write('{"verified":'+("true" if checked else "false")+"}\n")
    return 0 if checked else 1


if __name__=="__main__":
    raise SystemExit(main())
