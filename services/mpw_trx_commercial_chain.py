"""Bounded independent mainnet TRX evidence for an owner-issued invoice.

Never infer settlement from merchant indexer data or browser callbacks.
This adapter only constructs verified finalized evidence for an existing
transaction; accounting is exclusively in the merchant database adapter.
"""
from __future__ import annotations
from datetime import datetime,timezone
from services.mpw_trx_walletless_core import PaymentHold, TX_ID
from services.mpw_tron_independent_solidified_rpc import parse_solidified_native_trx
from services.mpw_walletless_django_test_bridge import TrustedNodePair
from scripts.mpw_tron_public_dual_probe_readonly_20261023 import (
    NODES, get, head_height_and_age,
)

PINNED=(("publicnode-allnodes","https://tron-solidity-rpc.publicnode.com"),
        ("trongrid","https://api.trongrid.io"))

def read_only_independent_pair():
    """Require both network heads fresh; no transaction broadcasting."""
    if tuple(NODES)!=PINNED:
        raise PaymentHold("Unexpected mainnet verifier providers")
    now=datetime.now(timezone.utc)
    try:
        heights=[head_height_and_age(get(provider,"head"),now) for provider in PINNED]
    except (OSError,ValueError,TypeError,KeyError) as exc:
        raise PaymentHold("Mainnet solidified head proof unavailable") from exc
    if abs(heights[0]-heights[1])>100:
        raise PaymentHold("Independent finalized nodes disagree on head range")
    def read(index,tx):
        if not isinstance(tx,str) or TX_ID.fullmatch(tx) is None:
            raise PaymentHold("Untrusted transaction candidate")
        provider=PINNED[index]
        try:
            body=get(provider,"body",tx)
            receipt=get(provider,"receipt",tx)
            return parse_solidified_native_trx(tx,body,receipt,source_id=provider[0])
        except (OSError,ValueError,TypeError,KeyError) as exc:
            raise PaymentHold("Independent solidity transfer not available") from exc
    return TrustedNodePair(
        identifier_a=PINNED[0][0],
        identifier_b=PINNED[1][0],
        prove_a=lambda tx:read(0,tx),
        prove_b=lambda tx:read(1,tx),
        audited_as_independent=True,
    )
