"""Bounded, unattended reconciliation for configured sitewide ETH/TRX orders.

NO merchant approval or blockchain write is involved. Read-only indexers supply
transaction candidates; independent full mainnet verification MUST be successful
before an order can move to paid and enqueue fulfillment. Off by default.
"""
from datetime import timedelta
import math
from types import SimpleNamespace

from django.conf import settings
from django.utils import timezone

from scripts.mojplaywin_direct_wallet_discovery import (
    discover_eth, discover_trx, match_unpaid_invoices, IndexerUnavailable,
)
from scripts.mojplaywin_native_chain_verify import VerificationError
from scripts.mojplaywin_native_rpc_clients import NativeRpcUnavailable

from .models import CommerceInvoice
from .settlement import settle_order_invoice, SettlementRejected
from .trusted_chain import verify_with_trusted_rpc, ChainAdapterUnavailable

MAX_BATCH=100
MAX_LOOKBACK_SECONDS=86400


class ReconciliationUnavailable(ValueError):
    pass


def reconcile_pending_orders(
    *,
    asset_filter=None,
    eth_scanner=discover_eth,
    trx_scanner=discover_trx,
    verifier=verify_with_trusted_rpc,
    settler=settle_order_invoice,
    now=None,
):
    """Perform one trusted bounded scan; no network activity when idle or off."""
    if asset_filter is not None and asset_filter not in ("ETH","TRX"):
        raise ReconciliationUnavailable("Unsupported asset filter")
    if any(getattr(settings,name,False) is not True for name in (
        "MPW_COMMERCE_RELEASE_READY",
        "MPW_COMMERCE_AUTORECONCILE_ENABLED",
        "MPW_COMMERCE_SETTLEMENT_ENABLED",
        "MPW_COMMERCE_REAL_RPC_ENABLED",
    )):
        return {"state":"disabled","pending":0,"matched":0,"paid":0,"rejected":0}
    now=now or timezone.now()
    earliest=now-timedelta(seconds=MAX_LOOKBACK_SECONDS)
    qs=(CommerceInvoice.objects
        .filter(status=CommerceInvoice.Status.AWAITING,
                order__status="pending", issued_at__gte=earliest)
        .order_by("id"))
    if asset_filter is not None:
        qs=qs.filter(asset=asset_filter)
    invoices=list(qs[:MAX_BATCH])
    if not invoices:
        return {"state":"idle","pending":0,"matched":0,"paid":0,"rejected":0}
    older=min(i.issued_at for i in invoices)
    lookback=min(MAX_LOOKBACK_SECONDS,
                 max(600,math.ceil((now-older).total_seconds())+90))
    timestamp_ms=int(now.timestamp()*1000)
    try:
        discovered=[]
        if any(i.asset=="ETH" for i in invoices):
            discovered.extend(eth_scanner(now_ms=timestamp_ms,lookback_s=lookback))
        if any(i.asset=="TRX" for i in invoices):
            discovered.extend(trx_scanner(now_ms=timestamp_ms,lookback_s=lookback))
        # Adapt the new order-level invoice fields for the existing stateless
        # transaction matcher. This matcher never writes paid state.
        matches=match_unpaid_invoices([
            SimpleNamespace(
                pk=i.pk, network=i.network,
                merchant_address=i.recipient,
                verified_sender_address=i.expected_sender,
                amount_atomic=i.amount_atomic,
            ) for i in invoices
        ],discovered)
    except (IndexerUnavailable,ValueError,TypeError) as exc:
        raise ReconciliationUnavailable(
            "Read-only transaction discovery is incomplete"
        ) from exc
    paid=0
    rejected=0
    for invoice_id,tx_hash in matches[:MAX_BATCH]:
        try:
            status=settler(invoice_id,tx_hash,trusted_chain_verifier=verifier)
            if status=="paid":
                paid+=1
        except (VerificationError,NativeRpcUnavailable,ChainAdapterUnavailable,
                SettlementRejected,ValueError):
            rejected+=1
    return {
        "state":"scanned","pending":len(invoices),"matched":len(matches),
        "paid":paid,"rejected":rejected,
    }
