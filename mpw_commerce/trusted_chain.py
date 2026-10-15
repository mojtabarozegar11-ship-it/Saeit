"""Production-intended read-only Ethereum/TRON finality adapter.

This module is disconnected from all public URLs and worker schedulers.
Unlike an indexer's transaction listing, only the independent mainnet RPC
receipt verifier can produce a settlement proof. There are NO merchant
signatures, wallet spending capabilities or customer-provided RPC endpoints.
"""
from datetime import datetime, timezone as utc_timezone
from django.conf import settings

from scripts.mojplaywin_native_chain_verify import (
    LockedQuote, verify_eth_transfer, verify_trx_transfer, VerificationError,
)
from scripts.mojplaywin_native_rpc_clients import (
    ethereum_rpc, tron_solidity_rpc,
)
from .models import CommerceInvoice


class ChainAdapterUnavailable(ValueError):
    pass


def verify_with_trusted_rpc(
    invoice, tx_hash, *, eth_rpc=ethereum_rpc, trx_rpc=tron_solidity_rpc,
):
    if getattr(settings,"MPW_COMMERCE_REAL_RPC_ENABLED",False) is not True:
        raise ChainAdapterUnavailable("Real blockchain verification disabled")
    if not isinstance(invoice,CommerceInvoice):
        raise ChainAdapterUnavailable("Internal commerce invoice required")
    quote=LockedQuote(
        order_id=invoice.order_id,
        network=invoice.network,
        smallest_units=int(invoice.amount_atomic),
        expected_sender=invoice.expected_sender,
        created_at_ms=int(invoice.issued_at.timestamp()*1000),
        expires_at_ms=int(invoice.expires_at.timestamp()*1000),
        quote_currency="USD",
        quote_amount=format(invoice.total_usd,".2f"),
    )
    if invoice.asset=="ETH":
        proof=verify_eth_transfer(tx_hash,quote,eth_rpc)
        backend="ethereum-mainnet-verified"
    elif invoice.asset=="TRX":
        proof=verify_trx_transfer(tx_hash,quote,trx_rpc)
        backend="tron-mainnet-verified"
    else:
        raise ChainAdapterUnavailable("Unsupported chain")
    stamp=proof.get("mined_timestamp_ms")
    if type(stamp) is not int or stamp<=0:
        raise ChainAdapterUnavailable("Block timestamp was not verified")
    return {
        "finalized":True,
        "order_id":proof["order_id"],
        "network":proof["network"],
        "tx_hash":proof["transaction_hash"],
        "sender":proof["sender"],
        "recipient":proof["recipient"],
        "amount_atomic":proof["amount_smallest_units"],
        "backend":backend,
        "block_timestamp":datetime.fromtimestamp(stamp/1000,utc_timezone.utc),
    }
