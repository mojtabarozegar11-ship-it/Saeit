"""Independent finalized mainnet TRX evidence; no transaction broadcasting."""
from datetime import datetime, timezone
from services.mpw_trx_walletless_core import PaymentHold
from services.mpw_tron_independent_solidified_rpc import (
    RpcProvider, solidified_head_height, verified_live_pair,
)

PINNED = (
    ("publicnode-allnodes", "https://tron-solidity-rpc.publicnode.com"),
    ("trongrid", "https://api.trongrid.io"),
)


def read_only_independent_pair():
    from django.conf import settings

    # Existing owner-controlled attestation; source code alone is not evidence.
    if getattr(settings, "MPW_TRX_SOLIDITY_RELEASE_VERIFIED", False) is not True:
        raise PaymentHold("Independent provider release is not verified")
    first = RpcProvider(PINNED[0][0], "allnodes", PINNED[0][1])
    second = RpcProvider(PINNED[1][0], "trongrid", PINNED[1][1])
    now = datetime.now(timezone.utc)
    heights = [solidified_head_height(provider, now) for provider in (first, second)]
    if abs(heights[0] - heights[1]) > 100:
        raise PaymentHold("Independent finalized nodes disagree on head range")
    return verified_live_pair(first, second, trusted_operator_attestation=True)
