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
    timestamp_ms: int


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
    header = _rpc(rpc_url, "eth_getBlockByNumber", [hex(block), False])
    if not isinstance(header, dict) or _to_int(header.get("number")) != block:
        raise VerificationError("Ethereum block header mismatch.")
    if not all(
        isinstance(value, str) and re.fullmatch(r"0x[0-9a-fA-F]{64}", value)
        for value in (header.get("hash"), transaction.get("blockHash"), receipt.get("blockHash"))
    ) or len({header["hash"].lower(), transaction["blockHash"].lower(), receipt["blockHash"].lower()}) != 1:
        raise VerificationError("Ethereum block hash mismatch.")
    if str(transaction.get("hash", "")).lower() != txid.lower() or str(receipt.get("transactionHash", "")).lower() != txid.lower():
        raise VerificationError("Ethereum transaction reference mismatch.")
    block_timestamp_ms = _to_int(header.get("timestamp")) * 1000
    head = _to_int(_rpc(rpc_url, "eth_blockNumber", []))
    confirmations = head - block + 1
    if confirmations < min_conf:
        raise VerificationError("Awaiting additional ETH confirmations.")
    return Proof(block, confirmations, block_timestamp_ms)


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
    # A full-node receipt only proves that a transaction was included in a
    # recent block. Check SolidityNode to require finalized canonical inclusion.
    def solid(name, payload):
        response = _post(base + "/walletsolidity/" + name, payload, headers)
        if not isinstance(response, dict) or response.get("Error"):
            raise VerificationError("Invalid finalized TRON node response.")
        return response

    transaction = solid("gettransactionbyid", {"value": txid})
    receipt = solid("gettransactioninfobyid", {"value": txid})
    tip = solid("getnowblock", {})
    contracts = transaction.get("raw_data", {}).get("contract", [])
    if str(transaction.get("txID", "")).lower() != txid or len(contracts) != 1:
        raise VerificationError("Finalized TRON transfer was not found.")
    transfer = contracts[0]
    if transfer.get("type") != "TransferContract":
        raise VerificationError("Only native TRX transfers are supported.")
    transfer_data = transfer.get("parameter", {}).get("value", {})
    if str(transfer_data.get("to_address", "")).upper() != recipient:
        raise VerificationError("Incorrect TRX recipient.")
    if _to_int(transfer_data.get("amount")) != int(atomic_amount):
        raise VerificationError("Incorrect TRX amount.")
    if str(receipt.get("id", "")).lower() != txid:
        raise VerificationError("TRON finalized transaction receipt not found.")
    # ResourceReceipt.result describes smart-contract execution. Native TRX
    # transfers may have only a net_fee; never demand this optional field.
    # But if any execution status exists, it MUST affirm success.
    outcomes = [receipt.get("result"), (receipt.get("receipt") or {}).get("result")]
    outcomes.extend((item or {}).get("contractRet") for item in transaction.get("ret", []))
    if any(v not in (None, "SUCCESS") for v in outcomes):
        raise VerificationError("TRON transfer execution was unsuccessful.")
    block = _to_int(receipt.get("blockNumber"))
    if block <= 0:
        raise VerificationError("Invalid finalized TRON block.")
    tip_height = _to_int(tip.get("block_header", {}).get("raw_data", {}).get("number"))
    confirmations = tip_height - block + 1
    if confirmations < min_conf:
        raise VerificationError("Awaiting additional finalized TRX confirmations.")
    block_timestamp_ms = _to_int(receipt.get("blockTimeStamp"))
    if block_timestamp_ms < 1000000000000:
        raise VerificationError("Invalid TRON block timestamp.")
    return Proof(block, confirmations, block_timestamp_ms)
