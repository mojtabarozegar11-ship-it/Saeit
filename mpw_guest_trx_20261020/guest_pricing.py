"""TRX-only guest quote with timestamp freshness; staging feature, not live-routed.

An ETH update cannot invalidate a fresh TRX quote. Never issue a payable
invoice if TRX has no independently fresh, trusted USD observation.
"""
from decimal import Decimal

from scripts.s01_trx_rate_isolation_candidate import (
    TrustedRateUnavailable,
    fetch_trx_only,
)


def receive_wallet():
    # Runtime-only imports: price validation itself must be testable without
    # loading the external production commerce ledger or chain verifier.
    from mpw_commerce.invoicing import RECEIVERS
    from scripts.mojplaywin_native_chain_verify import tron_address_to_hex

    chain, address, decimals = RECEIVERS.get("TRX", (None, None, None))
    if chain != "tron-mainnet" or decimals != 6 or not address:
        raise RuntimeError("TRX receiving wallet unavailable")
    tron_address_to_hex(address)
    return address


def price_usd():
    """Price of one TRX in USD; fail closed on stale/invalid/untrusted quotes."""
    observation = fetch_trx_only()
    value = observation.usd_per_trx
    if not Decimal("0.001") <= value <= Decimal("100"):
        raise TrustedRateUnavailable("TRX quote outside commerce safety range")
    return value
