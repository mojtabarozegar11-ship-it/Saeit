"""Fail-closed USDT receipt verification for SAMAN/MojPlayWin staging.

Read-only; not wired to checkout, settlement, product grants, or live Django.
Only official Tether ERC-20 Ethereum and TRC-20 TRON contracts are accepted.
RPC inputs MUST be server-pinned; buyer-supplied data never implies payment.
"""
from dataclasses import dataclass
import re
from scripts.mojplaywin_native_chain_verify import tron_address_to_hex

USDT_ETH = "0xdac17f958d2ee523a2206206994597c13d831ec7"
USDT_TRON = "TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t"
ETH_RECEIVER = "0x89149b01f59115b86553561f12438d2adf517e75"
TRON_RECEIVER = "THFNU1iEXHd71WjEgjqUksd2UnMg2pUi73"
TRANSFER_EVENT = "ddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
TRANSFER_SELECTOR = "a9059cbb"
USDT_DECIMALS = 6
ONE_USDT = 1_000_000


class USDTVerificationError(ValueError):
    pass


@dataclass(frozen=True)
class USDTQuote:
    order_id: int
    network: str
    amount_micro: int
    expected_sender: str
    issued_at_ms: int
    expires_at_ms: int


def reject(message):
    raise USDTVerificationError(message)


def _hex(v, length=None):
    if type(v) is not str:
        reject("Invalid hexadecimal field")
    s = v.lower().removeprefix("0x")
    if not s or not re.fullmatch("[0-9a-f]+", s) or (length is not None and len(s) != length):
        reject("Invalid hexadecimal field")
    return s


def _number(v):
    return int(_hex(v), 16)


def _uint(v):
    if type(v) is not int or v < 0:
        reject("Invalid unsigned integer")
    return v


def _quote(q, network):
    if not isinstance(q, USDTQuote) or q.network != network:
        reject("Wrong invoice network")
    if type(q.order_id) is not int or q.order_id <= 0:
        reject("Invalid order")
    if _uint(q.amount_micro) == 0:
        reject("Invalid token amount")
    if _uint(q.issued_at_ms) >= _uint(q.expires_at_ms):
        reject("Invalid payment window")
    if q.expires_at_ms - q.issued_at_ms > 15 * 60 * 1000:
        reject("Excessive payment window")


def _transfer_calldata(data, recipient20, amount):
    raw = _hex(data)
    if len(raw) != 136 or raw[:8] != TRANSFER_SELECTOR:
        reject("Not an exact token transfer")
    if raw[8:32] != "0" * 24 or raw[32:72] != recipient20:
        reject("Token call receiver mismatch")
    if int(raw[72:136], 16) != amount:
        reject("Token call amount mismatch")


def _event_topics(topics, sender20, recipient20):
    if not isinstance(topics, list) or len(topics) != 3:
        return False
    try:
        return (
            _hex(topics[0], 64) == TRANSFER_EVENT
            and _hex(topics[1], 64) == "0" * 24 + sender20
            and _hex(topics[2], 64) == "0" * 24 + recipient20
        )
    except USDTVerificationError:
        return False


def _eth_receipt_event(logs, sender20, recipient20, amount):
    if not isinstance(logs, list):
        reject("Missing Ethereum events")
    matched = []
    for event in logs:
        if not isinstance(event, dict):
            reject("Malformed Ethereum event")
        if _hex(event.get("address"), 40) != USDT_ETH[2:]:
            continue
        topics = event.get("topics")
        if isinstance(topics, list) and topics:
            if _hex(topics[0], 64) == TRANSFER_EVENT:
                matched.append(event)
    if len(matched) != 1:
        reject("Ambiguous USDT Transfer events")
    if not _event_topics(matched[0].get("topics"), sender20, recipient20):
        reject("Incorrect USDT Transfer parties")
    if _number(matched[0].get("data")) != amount:
        reject("Incorrect USDT Transfer amount")


def verify_ethereum_usdt(tx_hash, quote, rpc, minimum_confirmations=12):
    """Consume only server-authorized Ethereum mainnet JSON-RPC."""
    _quote(quote, "ethereum-mainnet")
    txid = "0x" + _hex(tx_hash, 64)
    sender = "0x" + _hex(quote.expected_sender, 40)
    if type(minimum_confirmations) is not int or minimum_confirmations < 12:
        reject("Unsafe confirmation threshold")
    if _number(rpc("eth_chainId", [])) != 1:
        reject("Ethereum mainnet mismatch")
    tx = rpc("eth_getTransactionByHash", [txid])
    receipt = rpc("eth_getTransactionReceipt", [txid])
    if not isinstance(tx, dict) or not isinstance(receipt, dict):
        reject("Unmined transaction")
    if "0x" + _hex(tx.get("hash"), 64) != txid or "0x" + _hex(receipt.get("transactionHash"), 64) != txid:
        reject("Transaction/receipt mismatch")
    if "0x" + _hex(tx.get("to"), 40) != USDT_ETH:
        reject("Wrong token contract")
    if "0x" + _hex(tx.get("from"), 40) != sender:
        reject("Unverified sender")
    _transfer_calldata(tx.get("input"), ETH_RECEIVER[2:], quote.amount_micro)
    if _number(tx.get("value")) != 0 or _number(receipt.get("status")) != 1:
        reject("Failed or non-token transaction")
    block = _number(receipt.get("blockNumber"))
    if block != _number(tx.get("blockNumber")):
        reject("Wrong mined block")
    block_hash = _hex(receipt.get("blockHash"), 64)
    if block_hash != _hex(tx.get("blockHash"), 64):
        reject("Block mismatch")
    head = _number(rpc("eth_blockNumber", []))
    if head < block or head - block + 1 < minimum_confirmations:
        reject("Insufficient confirmations")
    header = rpc("eth_getBlockByNumber", [hex(block), False])
    if not isinstance(header, dict) or _hex(header.get("hash"), 64) != block_hash:
        reject("Block not canonical")
    timestamp = _number(header.get("timestamp")) * 1000
    if not quote.issued_at_ms <= timestamp <= quote.expires_at_ms:
        reject("Payment outside invoice window")
    _eth_receipt_event(receipt.get("logs"), sender[2:], ETH_RECEIVER[2:], quote.amount_micro)
    return {
        "order_id": quote.order_id, "network": "ethereum-mainnet",
        "asset": "USDT", "contract": USDT_ETH, "tx_hash": txid,
        "sender": sender, "recipient": ETH_RECEIVER,
        "amount_atomic": quote.amount_micro, "finalized": True,
        "block_timestamp_ms": timestamp, "confirmed_blocks": head - block + 1,
    }


def verify_tron_usdt(tx_hash, quote, solidity_rpc):
    """Require solidified TRON transaction AND authentic USDT TRC-20 Transfer log."""
    _quote(quote, "tron-mainnet")
    txid = _hex(tx_hash, 64)
    try:
        sender = tron_address_to_hex(quote.expected_sender).lower()
        recipient = tron_address_to_hex(TRON_RECEIVER).lower()
        contract = tron_address_to_hex(USDT_TRON).lower()
    except ValueError as e:
        raise USDTVerificationError("Invalid TRON account") from e
    tx = solidity_rpc("/walletsolidity/gettransactionbyid", {"value": txid})
    info = solidity_rpc("/walletsolidity/gettransactioninfobyid", {"value": txid})
    if not isinstance(tx, dict) or not isinstance(info, dict):
        reject("Unconfirmed TRON transaction")
    if _hex(tx.get("txID"), 64) != txid or _hex(info.get("id"), 64) != txid:
        reject("TRON hash mismatch")
    if info.get("receipt", {}).get("result") != "SUCCESS":
        reject("TRON execution failed")
    ret = tx.get("ret")
    if not isinstance(ret, list) or not ret or any(
        not isinstance(row, dict) or row.get("contractRet") != "SUCCESS" for row in ret
    ):
        reject("TRON contract not successful")
    operations = tx.get("raw_data", {}).get("contract")
    if not isinstance(operations, list) or len(operations) != 1:
        reject("Ambiguous TRON operations")
    operation = operations[0]
    if not isinstance(operation, dict) or operation.get("type") != "TriggerSmartContract":
        reject("TRC-20 smart contract required")
    p = operation.get("parameter", {}).get("value", {})
    if _hex(p.get("owner_address"), 42) != sender or _hex(p.get("contract_address"), 42) != contract:
        reject("Wrong TRC-20 contract or sender")
    _transfer_calldata(p.get("data"), recipient[2:], quote.amount_micro)
    if _uint(info.get("blockNumber")) == 0:
        reject("TRON not solidified")
    timestamp = _uint(info.get("blockTimeStamp"))
    if not quote.issued_at_ms <= timestamp <= quote.expires_at_ms:
        reject("TRON payment outside invoice window")
    events = info.get("log")
    if not isinstance(events, list):
        reject("Missing TRC-20 events")
    matched = []
    for event in events:
        if not isinstance(event, dict):
            reject("Malformed TRON event")
        if _hex(event.get("address"), 40) != contract[2:]:
            continue
        topics = event.get("topics")
        if isinstance(topics, list) and topics and _hex(topics[0], 64) == TRANSFER_EVENT:
            matched.append(event)
    if len(matched) != 1:
        reject("Ambiguous TRC-20 Transfer events")
    if not _event_topics(matched[0].get("topics"), sender[2:], recipient[2:]):
        reject("TRC-20 Transfer parties mismatch")
    if _number(matched[0].get("data")) != quote.amount_micro:
        reject("TRC-20 Transfer amount mismatch")
    return {
        "order_id": quote.order_id, "network": "tron-mainnet", "asset": "USDT",
        "contract": USDT_TRON, "tx_hash": txid, "sender": quote.expected_sender,
        "recipient": TRON_RECEIVER, "amount_atomic": quote.amount_micro,
        "finalized": True, "block_timestamp_ms": timestamp,
        "finality": "tron-solidity",
    }
