"""READ-ONLY on-chain verification: no signing keys, no automated withdrawals.

Only native ETH on Ethereum mainnet and native TRX on TRON mainnet.
An API response is not enough: recipient, amount, inclusion, and confirmations
must all match an independently issued order quote.
"""
import hashlib
import json
import re
import urllib.request
from urllib.parse import urlsplit
from dataclasses import dataclass


class VerificationError(Exception):
    pass


@dataclass(frozen=True)
class Proof:
    height: int
    confirmations: int


def _post(url, payload, headers=None):
    if urlsplit(url).scheme != "https":
        raise VerificationError("A secure HTTPS blockchain endpoint is required.")
    request = urllib.request.Request(
        url, data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", **(headers or {})}, method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=8) as response:
            if response.status != 200:
                raise VerificationError("Blockchain endpoint is unavailable.")
            return json.load(response)
    except (OSError, ValueError, KeyError) as exc:
        raise VerificationError("Blockchain endpoint could not be verified.") from exc


def _to_int(value):
    if isinstance(value, bool):
        raise VerificationError("Invalid numeric chain field.")
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value, 16) if value.startswith("0x") else int(value, 10)
        except ValueError as exc:
            raise VerificationError("Invalid numeric chain field.") from exc
    raise VerificationError("Missing numeric chain field.")


def _rpc(url, method, params):
    response = _post(url, {"jsonrpc": "2.0", "id": 1, "method": method, "params": params})
    if not isinstance(response, dict) or response.get("error") or "result" not in response:
        raise VerificationError("Ethereum RPC failed.")
    return response["result"]


def verify_eth(tx_hash, merchant, atomic_amount, rpc_url, min_conf=12):
    if not re.fullmatch(r"(?:0x)?[0-9a-fA-F]{64}", tx_hash):
        raise VerificationError("Invalid Ethereum transaction hash.")
    if not re.fullmatch(r"0x[0-9a-fA-F]{40}", merchant):
        raise VerificationError("Invalid Ethereum merchant address.")
    if _to_int(_rpc(rpc_url, "eth_chainId", [])) != 1:
        raise VerificationError("Wrong Ethereum network.")
    txid = tx_hash if tx_hash.startswith("0x") else "0x" + tx_hash
    transaction = _rpc(rpc_url, "eth_getTransactionByHash", [txid])
    receipt = _rpc(rpc_url, "eth_getTransactionReceipt", [txid])
    if not isinstance(transaction, dict) or not isinstance(receipt, dict):
        raise VerificationError("Transaction is not mined yet.")
    if str(transaction.get("to", "")).lower() != merchant.lower():
        raise VerificationError("Incorrect ETH recipient.")
    if _to_int(transaction.get("value")) != int(atomic_amount):
        raise VerificationError("Incorrect ETH amount.")
    if _to_int(receipt.get("status")) != 1:
        raise VerificationError("ETH transfer execution failed.")
    block = _to_int(transaction.get("blockNumber"))
    if block != _to_int(receipt.get("blockNumber")):
        raise VerificationError("Ethereum block data mismatch.")
    head = _to_int(_rpc(rpc_url, "eth_blockNumber", []))
    confirmations = head - block + 1
    if confirmations < min_conf:
        raise VerificationError("Awaiting additional ETH confirmations.")
    return Proof(block, confirmations)


_B58 = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"


def _tron_address_hex(text):
    if not isinstance(text, str) or len(text) != 34:
        raise VerificationError("Invalid TRON merchant address.")
    number = 0
    for character in text:
        if character not in _B58:
            raise VerificationError("Invalid TRON address.")
        number = number * 58 + _B58.index(character)
    raw = number.to_bytes(25, "big")
    if raw[0] != 0x41 or hashlib.sha256(hashlib.sha256(raw[:21]).digest()).digest()[:4] != raw[21:]:
        raise VerificationError("Invalid TRON address checksum.")
    return raw[:21].hex().upper()


def verify_trx(tx_hash, merchant, atomic_amount, api_key="", min_conf=20):
    if not re.fullmatch(r"[0-9a-fA-F]{64}", tx_hash):
        raise VerificationError("Invalid TRON transaction hash.")
    recipient = _tron_address_hex(merchant)
    base = "https://api.trongrid.io"  # Pin to TRON mainnet. No caller-controlled network.
    headers = {"TRON-PRO-API-KEY": api_key} if api_key else {}
    def call(name, payload):
        result = _post(base + "/wallet/" + name, payload, headers)
        if not isinstance(result, dict):
            raise VerificationError("Malformed TRON chain response.")
        return result
    txid = tx_hash.lower()
    transaction = call("gettransactionbyid", {"value": txid})
    receipt = call("gettransactioninfobyid", {"value": txid})
    tip = call("getnowblock", {})
    contracts = transaction.get("raw_data", {}).get("contract", [])
    if transaction.get("txID", "").lower() != txid or len(contracts) != 1:
        raise VerificationError("TRON transfer was not found.")
    transfer = contracts[0]
    if transfer.get("type") != "TransferContract":
        raise VerificationError("Only native TRX transfers are supported.")
    transfer_data = transfer.get("parameter", {}).get("value", {})
    if str(transfer_data.get("to_address", "")).upper() != recipient:
        raise VerificationError("Incorrect TRX recipient.")
    if _to_int(transfer_data.get("amount")) != int(atomic_amount):
        raise VerificationError("Incorrect TRX amount.")
    ret = transaction.get("ret", [])
    if not ret or ret[0].get("contractRet") != "SUCCESS":
        raise VerificationError("TRON transaction unsuccessful.")
    if receipt.get("id", "").lower() != txid or receipt.get("receipt", {}).get("result") != "SUCCESS":
        raise VerificationError("TRON receipt unsuccessful.")
    block = _to_int(receipt.get("blockNumber"))
    tip_height = _to_int(tip.get("block_header", {}).get("raw_data", {}).get("number"))
    confirmations = tip_height - block + 1
    if confirmations < min_conf:
        raise VerificationError("Awaiting additional TRX confirmations.")
    return Proof(block, confirmations)
