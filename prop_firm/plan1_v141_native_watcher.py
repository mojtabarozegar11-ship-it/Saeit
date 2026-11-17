"""Server-side, zero-custody automatic MOJ-PROP-01 incoming TRX watcher.

Discovery via a paginated account index is UNTRUSTED; every candidate is
independently verified with two solidified TRON nodes by the authoritative
checkout and committed to a globally unique network/txid register.
No broadcasts, customer wallet access, private keys, or customer-origin writes.
"""
from __future__ import annotations

from datetime import timezone as utc
import json
import re
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from .plan1_v141_native_payment_models import PropV141NativeOrder
from .plan1_v141_native_checkout import (
    AMOUNT_SUN, RECEIVER, NETWORK, CheckoutRejected,
    _addr_hex, _release_enabled, confirm_native_trx_and_deliver,
)

_TXID = re.compile(r"[a-f0-9]{64}\Z")
_FINGERPRINT = re.compile(r"[A-Za-z0-9_=-]{8,500}\Z")
MAX_PAGES = 25
PAGE_LIMIT = 200
_BASE = "https://api.trongrid.io"


def _indexer_configuration():
    """Only an explicitly configured, audited mainnet indexer is accepted."""
    base = getattr(settings, "MOJPROP_V141_TRON_HISTORY_INDEXER", None)
    if type(base) is not str or base.rstrip("/") != _BASE:
        raise CheckoutRejected("Trusted mainnet transaction indexer not configured")
    key = getattr(settings, "MOJPROP_V141_TRONGRID_API_KEY", "")
    if type(key) is not str or len(key) > 256 or any(
            ord(ch) < 33 or ord(ch) > 126 for ch in key):
        raise CheckoutRejected("Invalid private TronGrid key configuration")
    return base.rstrip("/"), key


def _get_page(base, api_key, *, from_ms, fingerprint=None):
    params = {
        "only_confirmed": "true",
        "only_to": "true",
        "order_by": "block_timestamp,asc",
        "min_timestamp": str(from_ms),
        "limit": str(PAGE_LIMIT),
    }
    if fingerprint is not None:
        if type(fingerprint) is not str or not _FINGERPRINT.fullmatch(fingerprint):
            raise CheckoutRejected("Untrusted indexer page cursor")
        params["fingerprint"] = fingerprint
    target = base + "/v1/accounts/" + RECEIVER + "/transactions?" + urlencode(params)
    headers = {"Accept": "application/json"}
    if api_key:
        headers["TRON-PRO-API-KEY"] = api_key
    request = Request(target, headers=headers, method="GET")
    with urlopen(request, timeout=12) as response:
        if response.status != 200 or response.geturl() != target:
            raise CheckoutRejected("Indexer HTTP redirect or failure")
        raw = response.read(1_000_001)
    if len(raw) > 1_000_000:
        raise CheckoutRejected("Indexer response too large")
    try:
        payload = json.loads(raw)
    except (ValueError, UnicodeError) as exc:
        raise CheckoutRejected("Indexer returned malformed JSON") from exc
    if type(payload) is not dict or payload.get("success") is not True:
        raise CheckoutRejected("Indexer data retrieval failed")
    data, meta = payload.get("data"), payload.get("meta")
    if type(data) is not list or type(meta) is not dict or len(data) > PAGE_LIMIT:
        raise CheckoutRejected("Indexer pagination response invalid")
    return data, meta


def _candidates(open_orders):
    """Yield txids only when all independent invoice mappings are unambiguous."""
    if not open_orders:
        return []
    base, key = _indexer_configuration()
    oldest = min(i.issued_at for i in open_orders)
    from_ms = max(0, int(oldest.astimezone(utc.utc).timestamp() * 1000) - 1000)
    last_cursor = None
    seen_cursors = set()
    # No reader-selected customer invoice: match every pending order together.
    candidates = []
    seen_txids = set()
    for _page_number in range(MAX_PAGES):
        records, meta = _get_page(
            base, key, from_ms=from_ms, fingerprint=last_cursor)
        for tx in records:
            if type(tx) is not dict:
                continue
            txid = tx.get("txID")
            if (type(txid) is not str or not _TXID.fullmatch(txid)
                    or txid in seen_txids):
                continue
            seen_txids.add(txid)
            contract_list = (tx.get("raw_data") or {}).get("contract")
            if type(contract_list) is not list or len(contract_list) != 1:
                continue
            c = contract_list[0]
            if type(c) is not dict or c.get("type") != "TransferContract":
                continue
            param = c.get("parameter")
            v = param.get("value") if type(param) is dict else None
            if type(v) is not dict:
                continue
            sender, recipient, amount = (
                v.get("owner_address"), v.get("to_address"), v.get("amount"))
            if (type(sender) is not str or type(recipient) is not str or
                    type(amount) is not int or amount != AMOUNT_SUN or
                    recipient.lower() != _addr_hex(RECEIVER)):
                continue
            # Discovery timestamp is just a hint; finality verifier checks
            # the actual solidified block and exact invoice date/window.
            try:
                block_ms = int(tx["block_timestamp"])
            except (KeyError, ValueError, TypeError):
                continue
            candidates.append((txid, sender.lower(), block_ms))
        # For a FULL page without cursor we cannot prove coverage. Fail closed.
        next_cursor = meta.get("fingerprint")
        if next_cursor is None:
            if len(records) >= PAGE_LIMIT:
                raise CheckoutRejected("Indexer omitted full-page continuation")
            return candidates
        if (type(next_cursor) is not str
                or not _FINGERPRINT.fullmatch(next_cursor)
                or next_cursor in seen_cursors):
            raise CheckoutRejected("Indexer pagination loop or invalid cursor")
        seen_cursors.add(next_cursor)
        last_cursor = next_cursor
    raise CheckoutRejected("Index coverage exceeds bounded scan; cannot auto-credit")


def reconcile_pending_invoices(*, dry_run=False):
    """Explicitly invoked server job; never called from a visitor page.

    The caller must schedule this via an audited server-side job with
    overlap prevented and alerts on failures. All orders are read under a
    shared snapshot. A TX may auto-match only if exactly ONE pending invoice
    has the bound payer and the block falls within that invoice's window.
    """
    if not _release_enabled():
        raise CheckoutRejected("Payment release/reconciliation is not authorized")
    if type(dry_run) is not bool:
        raise ValueError("dry_run must be a bool")
    orders = list(PropV141NativeOrder.objects.filter(
        status="issued", product_code="MOJ-PROP-01").order_by("issued_at", "pk")
        .only("id", "reference", "payer_hex41", "issued_at", "expires_at",
              "status", "product_code"))
    report = {"checked_invoices": len(orders), "candidate_txids": 0,
              "settled": 0, "unmatched": 0, "ambiguous": 0,
              "pending": len(orders), "dry_run": dry_run}
    if not orders:
        return report
    # Covers late-indexed transfers for invoices that have already expired;
    # the verifier still requires their actual block time to be in-window.
    candidates = _candidates(orders)
    report["candidate_txids"] = len(candidates)
    for txid, payer, block_ms in candidates:
        matches = [
            order for order in orders
            if order.payer_hex41.lower() == payer
            and (int(order.issued_at.timestamp() * 1000) <= block_ms
                 < int(order.expires_at.timestamp() * 1000))
        ]
        if len(matches) != 1:
            report["ambiguous" if len(matches) > 1 else "unmatched"] += 1
            continue
        if dry_run:
            continue
        try:
            confirm_native_trx_and_deliver(reference=matches[0].reference,
                                            txid=txid)
        except CheckoutRejected:
            # Invalid/incomplete/fraudulent candidate: retain invoice and
            # permit a later finalized proof; never treat indexer as finality.
            continue
        report["settled"] += 1
    report["pending"] = PropV141NativeOrder.objects.filter(
        status="issued", product_code="MOJ-PROP-01").count()
    return report
