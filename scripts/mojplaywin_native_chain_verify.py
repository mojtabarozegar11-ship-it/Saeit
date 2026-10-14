"""Verify native ETH/TRX transfers against trusted server-side blockchain RPC.

This library only checks evidence. It NEVER marks an order paid, sends money,
confirms wallet ownership, issues quotes or releases a digital product.

A trusted checkout service must first persist a quote bound to an authenticated
user and a cryptographically proven sender address. It must enforce unique
(network, tx_hash) claims transactionally in its own database.
"""
import hashlib
import hmac
import re
from dataclasses import dataclass
from typing import Callable, Mapping, Any

ETH_RECEIVER = "0x89149b01f59115B86553561F12438D2ADF517E75"
TRX_RECEIVER = "THFNU1iEXHd71WjEgjqUksd2UnMg2pUi73"
BASE58 = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"


class VerificationError(ValueError):
    pass


@dataclass(frozen=True)
class LockedQuote:
    order_id: int
    network: str
    smallest_units: int
    expected_sender: str
    created_at_ms: int
    expires_at_ms: int
    # USD value and rate-provider evidence are validated and stored by the
    # checkout service BEFORE a LockedQuote is created.
    quote_currency: str = "USD"
    quote_amount: str = "7.50"


def _fail(reason):
    raise VerificationError(reason)


def _uint(v, name):
    if isinstance(v, bool) or not isinstance(v, int) or v < 0:
        _fail("Invalid unsigned integer " + name)
    return v


def _hex_uint(v, name):
    if not isinstance(v, str) or not re.fullmatch(r"0x[0-9a-fA-F]+", v):
        _fail("Invalid hexadecimal " + name)
    return int(v, 16)


def _eth_address(v):
    if not isinstance(v, str) or not re.fullmatch(r"0x[0-9a-fA-F]{40}", v):
        _fail("Invalid ETH address")
    return v.lower()


def tron_address_to_hex(address):
    if not isinstance(address, str) or not 30 <= len(address) <= 36:
        _fail("Invalid TRON address length")
    value = 0
    for ch in address:
        if ch not in BASE58:
            _fail("Invalid TRON base58 character")
        value = value * 58 + BASE58.index(ch)
    try:
        decoded = value.to_bytes(25, "big")
    except OverflowError:
        _fail("Invalid TRON address size")
    if len(decoded) != 25 or decoded[0] != 0x41:
        _fail("Invalid TRON address prefix")
    checksum = hashlib.sha256(hashlib.sha256(decoded[:21]).digest()).digest()[:4]
    if not hmac.compare_digest(checksum, decoded[21:]):
        _fail("Invalid TRON address checksum")
    return decoded[:21].hex().upper()


def _tron_address_hex(value):
    if not isinstance(value, str):
        _fail("Invalid TRON hex address")
    if not re.fullmatch(r"41[0-9a-fA-F]{40}", value):
        _fail("Invalid TRON native address encoding")
    return value.upper()


def _validate_quote(q: LockedQuote, chain: str):
    if q.network != chain or not isinstance(q.order_id, int) or q.order_id <= 0:
        _fail("Quote order or network mismatch")
    _uint(q.smallest_units, "quote amount")
    _uint(q.created_at_ms, "quote start")
    _uint(q.expires_at_ms, "quote expiry")
    if q.smallest_units <= 0 or q.created_at_ms >= q.expires_at_ms:
        _fail("Invalid quoted amount or time window")
    if q.quote_currency != "USD" or q.quote_amount != "7.50":
        _fail("Wrong item or fiat quote")


def verify_eth_transfer(
    tx_hash: str, q: LockedQuote, rpc: Callable[[str, list], Any],
    minimum_confirmations: int = 12,
) -> Mapping[str, Any]:
    """rpc(method, params) MUST call a trusted backend-configured ETH mainnet RPC."""
    _validate_quote(q, "ethereum-mainnet")
    if not isinstance(tx_hash, str) or not re.fullmatch(r"0x[0-9a-fA-F]{64}", tx_hash):
        _fail("Invalid Ethereum transaction hash")
    _uint(minimum_confirmations, "confirmations")
    if minimum_confirmations < 12:
        _fail("Unsafe ETH confirmation threshold")

    if _hex_uint(rpc("eth_chainId", []), "chainId") != 1:
        _fail("Ethereum mainnet chainId mismatch")
    tx = rpc("eth_getTransactionByHash", [tx_hash])
    receipt = rpc("eth_getTransactionReceipt", [tx_hash])
    if not isinstance(tx, dict) or not isinstance(receipt, dict):
        _fail("Unmined ETH transaction")
    if tx.get("hash", "").lower() != tx_hash.lower():
        _fail("ETH hash mismatch")
    if receipt.get("transactionHash", "").lower() != tx_hash.lower():
        _fail("ETH receipt hash mismatch")
    if _eth_address(tx.get("to")) != _eth_address(ETH_RECEIVER):
        _fail("Wrong ETH recipient")
    if _eth_address(tx.get("from")) != _eth_address(q.expected_sender):
        _fail("Wrong ETH sender")
    if _hex_uint(tx.get("value"), "ETH amount") != q.smallest_units:
        _fail("ETH amount is not the exact locked quote")
    if _hex_uint(receipt.get("status"), "receipt status") != 1:
        _fail("ETH transaction reverted")
    block = _hex_uint(receipt.get("blockNumber"), "mined block")
    if block != _hex_uint(tx.get("blockNumber"), "tx block"):
        _fail("ETH transaction and receipt blocks differ")
    if receipt.get("blockHash", "").lower() != tx.get("blockHash", "").lower():
        _fail("Ethereum block hash mismatch")
    head = _hex_uint(rpc("eth_blockNumber", []), "ETH chain head")
    if head < block or head - block + 1 < minimum_confirmations:
        _fail("Insufficient Ethereum confirmations")
    header = rpc("eth_getBlockByNumber", [hex(block), False])
    if not isinstance(header, dict) or header.get("hash", "").lower() != tx.get("blockHash", "").lower():
        _fail("Ethereum block no longer canonical")
    timestamp_ms = _hex_uint(header.get("timestamp"), "block timestamp") * 1000
    if timestamp_ms < q.created_at_ms or timestamp_ms > q.expires_at_ms:
        _fail("ETH payment is outside the quote window")
    return {
        "network": q.network,
        "order_id": q.order_id,
        "transaction_hash": tx_hash.lower(),
        "amount_smallest_units": q.smallest_units,
        "confirmed_blocks": head - block + 1,
        "sender": q.expected_sender.lower(),
        "recipient": ETH_RECEIVER.lower(),
    }


def verify_trx_transfer(
    tx_hash: str, q: LockedQuote, solidity_rpc: Callable[[str, dict], Any]
) -> Mapping[str, Any]:
    """solidity_rpc(path,payload) MUST call a trusted TRON *solidity* API.

    walletsolidity data implies solidity (irreversible) finality. Do NOT
    substitute pending /wallet/gettransactionbyid results for finality.
    """
    _validate_quote(q, "tron-mainnet")
    if not isinstance(tx_hash, str) or not re.fullmatch(r"[0-9a-fA-F]{64}", tx_hash):
        _fail("Invalid TRON transaction hash")
    expected_sender = tron_address_to_hex(q.expected_sender)
    recipient = tron_address_to_hex(TRX_RECEIVER)
    tx = solidity_rpc("/walletsolidity/gettransactionbyid", {"value": tx_hash})
    info = solidity_rpc("/walletsolidity/gettransactioninfobyid", {"value": tx_hash})
    if not isinstance(tx, dict) or not isinstance(info, dict):
        _fail("TRON transaction is not solidified")
    if tx.get("txID", "").lower() != tx_hash.lower() or info.get("id", "").lower() != tx_hash.lower():
        _fail("TRON transaction ID mismatch")
    if info.get("receipt", {}).get("result", "SUCCESS") != "SUCCESS":
        _fail("TRON receipt failed")
    results = tx.get("ret")
    if not isinstance(results, list) or not results or any(r.get("contractRet") != "SUCCESS" for r in results):
        _fail("TRON transaction failed")
    contracts = tx.get("raw_data", {}).get("contract")
    if not isinstance(contracts, list) or len(contracts) != 1:
        _fail("TRON requires a single native transfer")
    contract = contracts[0]
    if contract.get("type") != "TransferContract":
        _fail("TRX native coin only; TRC20 is not supported by this path")
    transfer = contract.get("parameter", {}).get("value", {})
    if _tron_address_hex(transfer.get("owner_address")) != expected_sender:
        _fail("Wrong TRX sender")
    if _tron_address_hex(transfer.get("to_address")) != recipient:
        _fail("Wrong TRX recipient")
    amount = transfer.get("amount")
    if _uint(amount, "TRX amount") != q.smallest_units:
        _fail("TRX amount is not the exact locked quote")
    if not isinstance(info.get("blockNumber"), int) or info["blockNumber"] <= 0:
        _fail("TRON transaction is not confirmed")
    timestamp_ms = _uint(info.get("blockTimeStamp"), "TRON timestamp")
    if timestamp_ms < q.created_at_ms or timestamp_ms > q.expires_at_ms:
        _fail("TRX payment is outside the quote window")
    return {
        "network": q.network,
        "order_id": q.order_id,
        "transaction_hash": tx_hash.lower(),
        "amount_smallest_units": q.smallest_units,
        "finality": "tron-solidity",
        "sender": q.expected_sender,
        "recipient": TRX_RECEIVER,
    }
