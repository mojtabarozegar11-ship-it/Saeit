#!/usr/bin/env python3
"""Verify real, public Shasta native-TRX evidence without paying or crediting.

This is an intentionally isolated READ-ONLY canary, never a merchant checkout.
The historical public transfer is for chain parser verification only: it MUST
NOT become a new buyer's paid invoice, a production receipt, or a delivery.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

APP = Path(__file__).resolve().parents[1]
if str(APP) not in sys.path:
    sys.path.insert(0, str(APP))

from services.mpw_tron_independent_solidified_rpc import (
    PaymentHold, parse_solidified_native_trx,
)

# Pinned official public TEST network, not a deployment-configurable endpoint.
TESTNET = "tron-shasta"
BASE = "https://api.shasta.trongrid.io"
WALLET = "TWTBsKZPVuQgaGNbyJWJm9XR28g4wVBCNQ"
# Historical 2,000 TRX Shasta funding transfer; public, solidified and read-only.
CANARY_TXID = "5abbe2881663f47eb4989396e8b8b4910554917f5f8281ddd05dbf479878b284"
CANARY_SUN = 2_000_000_000
MAX_JSON = 150_000


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *_args, **_kwargs):
        raise PaymentHold("Shasta canary must not follow redirects")


def public_read(method: str, path: str, payload: dict | None = None) -> dict:
    allowed = {
        ("POST", "/wallet/getaccount"),
        ("GET", "/walletsolidity/getnowblock"),
        ("POST", "/walletsolidity/gettransactionbyid"),
        ("POST", "/walletsolidity/gettransactioninfobyid"),
    }
    if (method, path) not in allowed:
        raise PaymentHold("Unapproved testnet read")
    data = (json.dumps(payload, separators=(",", ":")).encode("utf8")
            if method == "POST" else None)
    request = urllib.request.Request(
        BASE + path, data=data, method=method,
        headers={"Accept": "application/json", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.build_opener(NoRedirect()).open(request, timeout=15) as resp:
            if resp.status != 200 or resp.headers.get_content_type() != "application/json":
                raise PaymentHold("Invalid Shasta response")
            raw = resp.read(MAX_JSON + 1)
    except (TimeoutError, urllib.error.URLError, OSError) as exc:
        raise PaymentHold("Official Shasta RPC unavailable") from exc
    if len(raw) > MAX_JSON:
        raise PaymentHold("Oversize Shasta response")
    try:
        result = json.loads(raw)
    except (ValueError, UnicodeDecodeError) as exc:
        raise PaymentHold("Unparseable Shasta response") from exc
    if not isinstance(result, dict) or result.get("Error"):
        raise PaymentHold("Shasta RPC application error")
    return result


def audit(*, read=public_read, now: datetime | None = None) -> dict:
    instant = now or datetime.now(timezone.utc)
    if instant.tzinfo is None or instant.utcoffset() is None:
        raise PaymentHold("Aware clock required")
    head = read("GET", "/walletsolidity/getnowblock")
    meta = head.get("block_header", {}).get("raw_data", {})
    height, head_ms = meta.get("number"), meta.get("timestamp")
    if type(height) is not int or height < 1 or type(head_ms) is not int or head_ms < 1:
        raise PaymentHold("Missing solidified Shasta head")
    age = (instant - datetime.fromtimestamp(head_ms / 1000, timezone.utc)).total_seconds()
    if not -60 <= age <= 600:
        raise PaymentHold("Shasta chain head is stale")

    account = read("POST", "/wallet/getaccount", {"address": WALLET, "visible": True})
    balance = account.get("balance")
    if account.get("address") != WALLET or type(balance) is not int or balance < 0:
        raise PaymentHold("Unknown Shasta test account")

    query = {"value": CANARY_TXID, "visible": False}
    body = read("POST", "/walletsolidity/gettransactionbyid", query)
    info = read("POST", "/walletsolidity/gettransactioninfobyid", query)
    transfer = parse_solidified_native_trx(
        CANARY_TXID, body, info, source_id="official-shasta-smoke",
        network=TESTNET,
    )
    block_number = info.get("blockNumber")
    if (transfer.network != TESTNET or transfer.recipient != WALLET
        or transfer.amount_sun != CANARY_SUN
        or type(block_number) is not int or block_number > height):
        raise PaymentHold("Shasta historical native transfer disagrees")

    return {
        "network": TESTNET,
        "status": "SHASTA_CHAIN_READONLY_PASSED",
        "official_solidity_height": height,
        "head_age_seconds": int(age),
        "test_account_active": True,
        "test_balance_trx": f"{balance / 1_000_000:.6f}",
        "historical_native_transfer_solidified": True,
        "historical_transfer_sun": transfer.amount_sun,
        "historical_transfer_block": block_number,
        "historical_txid": CANARY_TXID,
        "test_invoice_paid": False,
        "testnet_transfers_broadcast": 0,
        "production_writes": 0,
        "gateway_financial_settlement_verified": False,
    }


if __name__ == "__main__":
    try:
        print(json.dumps(audit(), sort_keys=True))
    except PaymentHold as exc:
        print(json.dumps({"status": "SHASTA_READONLY_BLOCKED", "reason": str(exc),
                          "production_writes": 0, "testnet_transfers_broadcast": 0}))
        raise SystemExit(2)
