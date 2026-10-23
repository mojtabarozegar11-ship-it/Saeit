#!/usr/bin/env python3
"""Read-only mainnet native-TRX canary across independently operated public gateways.

Never submit a transaction, inspect merchant orders, change a DB, or activate
checkout. Anonymous gateways are DIAGNOSTIC ONLY, not merchant settlement proofs.
No wallet, transfer amount, transaction ID, URL response, or auth detail is logged.
"""
from __future__ import annotations
from datetime import datetime, timezone
import json
import urllib.error
import urllib.request

from services.mpw_tron_independent_solidified_rpc import parse_solidified_native_trx

NODES = (
    ("publicnode-allnodes", "https://tron-solidity-rpc.publicnode.com"),
    ("trongrid", "https://api.trongrid.io"),
)
PATHS = {
    "head": "/walletsolidity/getnowblock",
    "body": "/walletsolidity/gettransactionbyid",
    "receipt": "/walletsolidity/gettransactioninfobyid",
}
MAX_HEAD_BYTES = 2_000_000
MAX_TX_BYTES = 150_000


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def get(provider: tuple[str, str], operation: str, txid: str = "") -> dict:
    """Only the three allowlisted read-only methods on pinned HTTPS origins."""
    if provider not in NODES or operation not in PATHS:
        raise ValueError("Unapproved read-only TRON source")
    if operation != "head" and (len(txid) != 64 or
                                any(c not in "0123456789abcdef" for c in txid)):
        raise ValueError("Malformed public canary hash")
    url = provider[1] + PATHS[operation]
    data = None if operation == "head" else json.dumps(
        {"value": txid, "visible": False}, separators=(",", ":")
    ).encode("utf8")
    request = urllib.request.Request(
        url, data=data,
        headers={"Accept": "application/json", "Content-Type": "application/json"},
        method="GET" if operation == "head" else "POST",
    )
    with urllib.request.build_opener(NoRedirect()).open(request, timeout=15) as response:
        if response.status != 200 or response.headers.get(
            "Content-Type", ""
        ).split(";")[0] != "application/json":
            raise ValueError("Invalid provider HTTP response")
        limit = MAX_HEAD_BYTES if operation == "head" else MAX_TX_BYTES
        raw = response.read(limit + 1)
    if len(raw) > limit:
        raise ValueError("Bounded provider payload overflow")
    answer = json.loads(raw)
    if type(answer) is not dict or answer.get("Error"):
        raise ValueError("Invalid provider result")
    return answer


def head_height_and_age(response: dict, observation: datetime) -> int:
    raw = response.get("block_header", {}).get("raw_data", {})
    number, millis = raw.get("number"), raw.get("timestamp")
    if type(number) is not int or number <= 0 or type(millis) is not int or millis <= 0:
        raise ValueError("Invalid solidified header")
    age = observation.timestamp() - millis / 1000
    if age < -60 or age > 600:
        raise ValueError("Stale solidified header")
    return number


def select_native_candidate(block: dict) -> str:
    txs = block.get("transactions", [])
    if not isinstance(txs, list):
        raise ValueError("Missing solidified transactions")
    for tx in txs:
        if not isinstance(tx, dict):
            continue
        contracts = tx.get("raw_data", {}).get("contract", [])
        results = tx.get("ret", [])
        if (isinstance(contracts, list) and len(contracts) == 1
            and isinstance(contracts[0], dict)
            and contracts[0].get("type") == "TransferContract"
            and isinstance(results, list) and len(results) == 1
            and isinstance(results[0], dict)
            and results[0].get("contractRet") == "SUCCESS"):
            txid = tx.get("txID", "")
            if (type(txid) is str and len(txid) == 64
                and all(c in "0123456789abcdef" for c in txid)):
                return txid
    raise ValueError("No recent native transfer in public sample")


def audit():
    result = {
        "scope": "public-anonymous-tron-mainnet-readonly-diagnostic",
        "status": "BLOCKED",
        "two_fresh_solidified_heads": False,
        "native_transfer_body_and_receipt_match": False,
        "approved_for_merchant_financial_settlement": False,
        "merchant_canary_verified": False,
        "financial_writes": 0,
        "public_checkout_activated": False,
    }
    try:
        now = datetime.now(timezone.utc)
        heads = (get(NODES[0], "head"), get(NODES[1], "head"))
        heights = [head_height_and_age(block, now) for block in heads]
        if abs(heights[0] - heights[1]) > 100:
            raise ValueError("Different solidified head ranges")
        result["two_fresh_solidified_heads"] = True
        txid = select_native_candidate(heads[0])
        proofs = []
        for provider in NODES:
            body = get(provider, "body", txid)
            receipt = get(provider, "receipt", txid)
            proofs.append(parse_solidified_native_trx(
                txid, body, receipt, source_id=provider[0]
            ))
        left, right = proofs
        if (left.tx_hash != right.tx_hash
            or left.sender != right.sender
            or left.recipient != right.recipient
            or left.amount_sun != right.amount_sun
            or left.block_time != right.block_time
            or not (left.solidified and right.solidified)
            or not (left.execution_success and right.execution_success)):
            raise ValueError("Public canary proof disagreement")
        result["native_transfer_body_and_receipt_match"] = True
        result["status"] = "PUBLIC_NETWORK_PROOF_READY_ONLY"
        result["reason"] = "merchant_purchase_and_independent_operator_review_required"
    except Exception as exc:
        # Only fixed, non-transactional exception type: no response or secret data.
        result["reason"] = "public_network_proof_unavailable"
        result["error_class"] = type(exc).__name__
    return result


if __name__ == "__main__":
    print("MPW_TRON_PUBLIC_DUAL_READONLY=" + json.dumps(audit(), sort_keys=True))
