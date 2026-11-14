"""Read-only TronGrid discovery; NEVER treat indexer rows as proof of payment.

Discover transaction *candidates*, then independently verify with two pinned
solidified mainnet RPC operators before touching an existing merchant ledger.
This module performs no broadcasts or wallet signing.
"""
from __future__ import annotations

import json
import re
import urllib.parse
import urllib.request
from django.conf import settings

from .tron_gateway_verify import MAINNET_RECEIVER, TX_PATTERN, PaymentNotFinal, address_hex

API = "https://api.trongrid.io"
MAX_BYTES = 2_000_000
MAX_PAGES = 5
MAX_RESULTS = 200


class _DenyRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def _get_page(params, *, api_key):
    """Only this exact account endpoint is permitted; redirects are prohibited."""
    query = urllib.parse.urlencode(params)
    url = f"{API}/v1/accounts/{MAINNET_RECEIVER}/transactions?{query}"
    request = urllib.request.Request(
        url, method="GET",
        headers={
            "Accept": "application/json",
            "User-Agent": "Zomorod-Tron-Readonly-Discovery/1",
            "TRON-PRO-API-KEY": api_key,
        },
    )
    try:
        opener = urllib.request.build_opener(_DenyRedirect())
        with opener.open(request, timeout=12) as response:
            if (response.status != 200 or
                    response.headers.get_content_type() != "application/json"):
                raise PaymentNotFinal("TRON indexer unavailable")
            raw = response.read(MAX_BYTES + 1)
            if len(raw) > MAX_BYTES:
                raise PaymentNotFinal("TRON indexer payload too large")
        doc = json.loads(raw)
    except (OSError, TypeError, ValueError) as exc:
        raise PaymentNotFinal("TRON indexer request failed") from exc
    if (type(doc) is not dict or doc.get("success") is not True or
            type(doc.get("data")) is not list or len(doc["data"]) > MAX_RESULTS or
            type(doc.get("meta", {})) is not dict):
        raise PaymentNotFinal("TRON indexer data invalid")
    return doc


def native_candidate(tx, *, recipient_hex):
    """Minimal indexer inspection: *candidate*, not final receipt."""
    if type(tx) is not dict:
        return None
    txid = tx.get("txID")
    raw = tx.get("raw_data")
    stamp = tx.get("block_timestamp")
    if (type(txid) is not str or not TX_PATTERN.fullmatch(txid)
            or type(stamp) is not int or type(raw) is not dict):
        return None
    contracts = raw.get("contract")
    if type(contracts) is not list or len(contracts) != 1 or type(contracts[0]) is not dict:
        return None
    c = contracts[0]
    parameter = c.get("parameter")
    if c.get("type") != "TransferContract" or type(parameter) is not dict:
        return None
    value = parameter.get("value")
    if (type(value) is not dict or type(value.get("to_address")) is not str
            or value["to_address"].lower() != recipient_hex
            or type(value.get("amount")) is not int or
            not 0 < value["amount"] < 10**18):
        return None
    return (txid.lower(), value["amount"], stamp)


def receiver_candidates(*, min_ms: int, max_ms: int,
                        pages: int = 3, fetch=_get_page):
    """Bounded, paginated, receiver-specific history, with no settlement writes.

    Returns (candidate tuples, was_truncated). Runs should overlap time windows
    and preserve a manual-txid fallback. Pagination is not completeness proof.
    """
    if (type(min_ms) is not int or type(max_ms) is not int or
            not 0 < min_ms < max_ms or
            type(pages) is not int or not 1 <= pages <= MAX_PAGES):
        raise PaymentNotFinal("Unsafe discovery bounds")
    api_key = getattr(settings, "TRON_UNIFIED_TRONGRID_API_KEY", "")
    if type(api_key) is not str or not re.fullmatch(r"[A-Za-z0-9_-]{16,256}", api_key):
        raise PaymentNotFinal("Read-only TronGrid API key not configured")
    params = {
        "only_confirmed": "true",
        "only_to": "true",
        "limit": str(MAX_RESULTS),
        "min_timestamp": str(min_ms),
        "max_timestamp": str(max_ms),
        "order_by": "block_timestamp,desc",
    }
    recipient_hex = address_hex(MAINNET_RECEIVER)
    visited = set()
    seen_tx = set()
    found = []
    truncated = False
    for index in range(pages):
        doc = fetch(params, api_key=api_key)
        for record in doc["data"]:
            candidate = native_candidate(record, recipient_hex=recipient_hex)
            if candidate is not None and candidate[0] not in seen_tx:
                seen_tx.add(candidate[0])
                found.append(candidate)
        fingerprint = doc.get("meta", {}).get("fingerprint")
        if not fingerprint:
            return found, False
        if (type(fingerprint) is not str or not 1 <= len(fingerprint) <= 1024 or
                not re.fullmatch(r"[A-Za-z0-9_+/=-]+", fingerprint) or
                fingerprint in visited):
            raise PaymentNotFinal("Unsafe indexer continuation")
        visited.add(fingerprint)
        params["fingerprint"] = fingerprint
        truncated = index + 1 == pages
    return found, truncated
