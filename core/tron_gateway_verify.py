"""Independent, read-only proof of a finalized native TRX transfer.

The caller must supply the immutable invoice quote. Buyer-supplied transaction
hashes are candidates, never payment evidence by themselves. No private keys.
"""
from __future__ import annotations

import hashlib
import json
import re
import urllib.request

ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
MAINNET_RECEIVER = "THFNU1iEXHd71WjEgjqUksd2UnMg2pUi73"
SOURCES = (
    ("publicnode", "https://tron-solidity-rpc.publicnode.com"),
    ("trongrid", "https://api.trongrid.io"),
)
TX_PATTERN = re.compile(r"[0-9a-fA-F]{64}\Z")


class PaymentNotFinal(Exception):
    """Proof unavailable, malformed, not finalized or not equal to the invoice."""


def address_hex(address: str) -> str:
    if not isinstance(address, str) or len(address) != 34:
        raise PaymentNotFinal("Invalid TRON address")
    value = 0
    try:
        for ch in address:
            value = value * 58 + ALPHABET.index(ch)
    except ValueError as exc:
        raise PaymentNotFinal("Invalid TRON alphabet") from exc
    raw = value.to_bytes(25, "big")
    if (raw[0] != 0x41 or
            hashlib.sha256(hashlib.sha256(raw[:21]).digest()).digest()[:4] != raw[21:]):
        raise PaymentNotFinal("Invalid TRON mainnet checksum")
    return raw[:21].hex()


def _https_rpc(base: str, endpoint: str, txid: str) -> dict:
    if base not in tuple(x[1] for x in SOURCES):
        raise PaymentNotFinal("Unapproved RPC")
    request = urllib.request.Request(
        base + endpoint,
        data=json.dumps({"value": txid}).encode("ascii"),
        headers={"Accept": "application/json", "Content-Type": "application/json",
                 "User-Agent": "Zomorod-Tron-ReadOnly/1"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=9) as response:
            if response.status != 200:
                raise PaymentNotFinal("RPC unavailable")
            data = response.read(65537)
            if len(data) > 65536:
                raise PaymentNotFinal("Oversized RPC evidence")
        result = json.loads(data)
        if type(result) is not dict or result.get("Error"):
            raise PaymentNotFinal("Invalid RPC evidence")
        return result
    except (OSError, ValueError, TypeError) as exc:
        raise PaymentNotFinal("RPC failed") from exc


def _single_proof(txid: str, receiver_hex: str, sun: int,
                  issued_ms: int, expires_ms: int, body: dict, receipt: dict):
    if (type(body.get("txID")) is not str or
            type(receipt.get("id")) is not str or
            body["txID"].lower() != txid or receipt["id"].lower() != txid):
        raise PaymentNotFinal("Transaction ID does not match")
    contracts = (body.get("raw_data") or {}).get("contract")
    if type(contracts) is not list or len(contracts) != 1:
        raise PaymentNotFinal("Not a single native TRX transfer")
    contract = contracts[0]
    if type(contract) is not dict or contract.get("type") != "TransferContract":
        raise PaymentNotFinal("Wrong asset type")
    data = (contract.get("parameter") or {}).get("value")
    if type(data) is not dict:
        raise PaymentNotFinal("Transfer body missing")
    if (str(data.get("to_address", "")).lower() != receiver_hex or
            type(data.get("amount")) is not int or data["amount"] != sun):
        raise PaymentNotFinal("Destination or amount does not match invoice")
    result = body.get("ret")
    if (type(result) is not list or len(result) != 1 or
            type(result[0]) is not dict or result[0].get("contractRet") != "SUCCESS"):
        raise PaymentNotFinal("Transaction did not execute successfully")
    execution = receipt.get("receipt", {})
    if type(execution) is not dict or execution.get("result", "SUCCESS") != "SUCCESS":
        raise PaymentNotFinal("Transaction execution failed")
    height = receipt.get("blockNumber")
    timestamp = receipt.get("blockTimeStamp")
    if (type(height) is not int or height <= 0 or
            type(timestamp) is not int or
            not issued_ms - 10_000 <= timestamp <= expires_ms + 60_000):
        raise PaymentNotFinal("Deposit outside invoice window")
    sender = data.get("owner_address")
    if type(sender) is not str or not re.fullmatch(r"41[0-9a-fA-F]{40}", sender):
        raise PaymentNotFinal("Sender unavailable")
    return (height, timestamp, sender.lower())


def verify_native_trx(txid: str, recipient: str, expected_sun: int,
                      issued_ms: int, expires_ms: int, rpc=_https_rpc) -> dict:
    """Require the same solidified native TRX transfer from TWO separate RPCs."""
    if (type(txid) is not str or TX_PATTERN.fullmatch(txid) is None or
            type(expected_sun) is not int or not 0 < expected_sun < 10**18 or
            type(issued_ms) is not int or type(expires_ms) is not int or
            not issued_ms < expires_ms):
        raise PaymentNotFinal("Invalid invoice evidence")
    txid = txid.lower()
    receiver_hex = address_hex(recipient)
    observations = []
    for _, base in SOURCES:
        body = rpc(base, "/walletsolidity/gettransactionbyid", txid)
        receipt = rpc(base, "/walletsolidity/gettransactioninfobyid", txid)
        if type(body) is not dict or type(receipt) is not dict:
            raise PaymentNotFinal("Invalid finalized RPC payload")
        observations.append(_single_proof(
            txid, receiver_hex, expected_sun, issued_ms, expires_ms, body, receipt))
    if observations[0] != observations[1]:
        raise PaymentNotFinal("Independent finalized RPCs disagree")
    height, timestamp, sender = observations[0]
    digest = hashlib.sha256(
        f"tron-mainnet|{txid}|{receiver_hex}|{expected_sun}|{height}|{timestamp}|{sender}".encode("ascii")
    ).hexdigest()
    return {"txid": txid, "sender_hex": sender, "block_height": height,
            "block_time_ms": timestamp, "proof_digest": digest, "finality": "solidified"}
