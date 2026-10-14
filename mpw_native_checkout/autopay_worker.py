"""Unattended inbound ETH/TRX reconciliation (staged, DISABLED by default).

Call only after approved release gates, trusted sender/order validation,
RPC/indexer readiness and end-to-end paid ebook fulfilment tests.
The receiving merchant does not manually approve any customer purchase.

No polling loop or cron is created here. Failure of either required indexer
blocks the entire batch; unverified candidate hashes never settle orders.
"""
from datetime import timedelta
import math

from django.conf import settings
from django.db import IntegrityError
from django.utils import timezone

from scripts.mojplaywin_direct_wallet_discovery import (
    discover_eth, discover_trx, match_unpaid_invoices, IndexerUnavailable,
)
from scripts.mojplaywin_native_rpc_clients import (
    ethereum_rpc, tron_solidity_rpc, NativeRpcUnavailable,
)
from scripts.mojplaywin_native_chain_verify import VerificationError
from .models import NativeInvoice
from .settlement import settle_native_invoice, SettlementRejected

MAX_BATCH = 100
MAX_LOOKBACK_SECONDS = 86400


class AutoPayUnavailable(ValueError):
    pass


def reconcile_once(
    *,
    eth_scanner=discover_eth,
    trx_scanner=discover_trx,
    eth_chain_rpc=ethereum_rpc,
    trx_chain_rpc=tron_solidity_rpc,
    now=None,
    asset_filter=None,
):
    """One bounded scan-and-settle cycle. Must be called by a trusted scheduler."""
    if asset_filter is not None and asset_filter not in ("ETH","TRX"):
        raise AutoPayUnavailable("Unexpected asset-specific reconciliation request")
    if getattr(settings, "MPW_NATIVE_AUTOPAY_ENABLED", False) is not True:
        return {"state":"disabled","scanned":0,"matched":0,"paid":0,"rejected":0}
    if now is None:
        now=timezone.now()
    earliest=now-timedelta(seconds=MAX_LOOKBACK_SECONDS)
    qs=(NativeInvoice.objects.select_related("order","product")
        .filter(status=NativeInvoice.Status.AWAITING,
                order__status="pending",product_id=72,
                sender_signature_verified_at__isnull=False,
                issued_at__gte=earliest)
        .order_by("id"))
    if asset_filter:
        qs=qs.filter(asset=asset_filter)
    if qs.count()>MAX_BATCH:
        raise AutoPayUnavailable("Batch capacity exceeded; do not skip open invoices")
    invoices=list(qs)
    if not invoices:
        return {"state":"no_pending","scanned":0,"matched":0,"paid":0,"rejected":0}

    older=min(i.issued_at for i in invoices)
    # Search only the required invoice age plus a small timestamp margin;
    # never re-query an arbitrary hour of history for a brand-new order.
    lookback_s=min(MAX_LOOKBACK_SECONDS,
                   max(600, math.ceil((now-older).total_seconds())+90))
    coins={i.asset for i in invoices}
    now_ms=int(now.timestamp()*1000)
    try:
        discovered=[]
        if "ETH" in coins:
            discovered.extend(eth_scanner(now_ms=now_ms,lookback_s=lookback_s))
        if "TRX" in coins:
            discovered.extend(trx_scanner(now_ms=now_ms,lookback_s=lookback_s))
        matches=match_unpaid_invoices(invoices,discovered)
    except (IndexerUnavailable,ValueError,TypeError) as exc:
        raise AutoPayUnavailable("Cannot prove coverage of inbound transactions") from exc

    if len(matches)>MAX_BATCH:
        raise AutoPayUnavailable("Unbounded matched transfer set")

    paid=0
    rejected=0
    for invoice_id,tx_hash in matches:
        try:
            result=settle_native_invoice(
                invoice_id,tx_hash,
                ethereum_rpc=eth_chain_rpc,
                tron_solidity_rpc=trx_chain_rpc,
            )
            if result=="paid": paid+=1
        except (VerificationError,NativeRpcUnavailable,SettlementRejected,
                IntegrityError,ValueError):
            # No failed candidate can set an Order to paid.
            # Operators must inspect a sanitized error log separately.
            rejected+=1
    return {
        "state":"scanned",
        "scanned":len(discovered),
        "matched":len(matches),
        "paid":paid,
        "rejected":rejected,
    }
