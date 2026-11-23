"""Conservative shared-receiver payer collision check for future Starter30 billing.

This pure DB read guard is deliberately NOT a wallet-ownership verifier and
is NOT currently wired into live settlement. Production integration must
preserve historical paid-invoice recovery and the protected source-bundle
release contract. Never treat absence of a collision as a buyer signature.
"""
from __future__ import annotations
from config.mojprop_db_router import MOJPROP_DB_ALIAS
from prop_firm.models import PropSimulationPayment


class AmbiguousPayerClaim(ValueError):
    """A public TXID cannot automatically be attributed to this invoice."""


def require_unambiguous_payer_claim(
    *, payment_pk, payer_hex41: str | None, recipient: str, block_time
) -> None:
    """Reject sender/receiver claims with overlapping original invoice windows.

    Even historical EXPIRED or REVIEW rows matter for their original window.
    Never mutate invoices, issue an entitlement, or infer wallet ownership.
    """
    if not payer_hex41:
        raise AmbiguousPayerClaim(
            "payer wallet ownership is unverified; contact support"
        )
    collision = (
        PropSimulationPayment.objects.using(MOJPROP_DB_ALIAS)
        .filter(
            payer_hex41=payer_hex41,
            recipient=recipient,
            issued_at__lte=block_time,
            expires_at__gt=block_time,
        )
        .exclude(pk=payment_pk)
        .exists()
    )
    if collision:
        raise AmbiguousPayerClaim(
            "ambiguous sending-wallet claim; contact support for manual review"
        )
