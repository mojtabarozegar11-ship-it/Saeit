"""Atomic Django persistence for reserve-backed MOJ PROP rewards.

This module is deliberately limited to settled invoices and database ledger rows.
It never calls a broker, RPC endpoint, wallet, or payout provider.
"""
from __future__ import annotations

from django.core.exceptions import ValidationError
from django.db import transaction

from .models import (
    PropPlan1Invoice,
    PropPlan1Receipt,
    PropRewardCommitment,
    PropRewardReserveAllocation,
)


BPS = 10_000
REWARD_RESERVE_BPS = 8_000
REFUND_RESERVE_BPS = 1_000
OPERATING_BUFFER_BPS = 1_000
SUPPORTED_FEES_SUN = frozenset({18_000_000, 30_000_000})


def _positive_sun(value, field):
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValidationError({field: "positive integer SUN amount required"})
    return value


def _allocation_values(fee_sun):
    reward = fee_sun * REWARD_RESERVE_BPS // BPS
    refund = fee_sun * REFUND_RESERVE_BPS // BPS
    operating = fee_sun - reward - refund
    return reward, refund, operating


@transaction.atomic
def allocate_reward_reserve_after_settlement(*, invoice_id):
    """Create one durable allocation only after an attested paid invoice."""
    invoice = (
        PropPlan1Invoice.objects.select_for_update()
        .get(pk=invoice_id)
    )
    if invoice.status != "paid":
        raise ValidationError("settled_paid_invoice_required")
    from .simulation_invoice_contract import PRODUCT_CODE, CONTRACT_VERSION
    from .plan1_invoice import CONTRACT_VERSION as LEGACY_VERSION
    allowed_contracts = {"MOJ-PROP-01": LEGACY_VERSION, PRODUCT_CODE: CONTRACT_VERSION}
    if invoice.product_code not in allowed_contracts:
        raise ValidationError("unsupported_prop_product")
    if invoice.contract_version != allowed_contracts[invoice.product_code]:
        raise ValidationError("unsupported_product_contract_version")
    if invoice.purchase_kind not in {"first", "retry"}:
        raise ValidationError("unsupported_purchase_kind")
    expected_fee = (
        30_000_000 if invoice.purchase_kind == "first" else 18_000_000
    )
    if invoice.amount_sun != expected_fee:
        raise ValidationError("invoice_purchase_kind_amount_mismatch")
    if invoice.amount_sun not in SUPPORTED_FEES_SUN:
        raise ValidationError("unsupported_settlement_amount")

    try:
        receipt = (
            PropPlan1Receipt.objects.select_for_update()
            .select_related("ledger")
            .get(invoice=invoice)
        )
    except PropPlan1Receipt.DoesNotExist as exc:
        raise ValidationError("settlement_receipt_required") from exc

    ledger = receipt.ledger
    if ledger.network != "tron-mainnet":
        raise ValidationError("tron_mainnet_required")
    if ledger.amount_sun != invoice.amount_sun:
        raise ValidationError("settlement_amount_mismatch")
    if ledger.trusted_reconciler_attestation is not True:
        raise ValidationError("trusted_settlement_attestation_required")

    if PropRewardReserveAllocation.objects.filter(invoice=invoice).exists():
        raise ValidationError("duplicate_reserve_allocation")

    reward, refund, operating = _allocation_values(invoice.amount_sun)
    return PropRewardReserveAllocation.objects.create(
        invoice=invoice,
        settlement=ledger,
        fee_sun=invoice.amount_sun,
        reward_reserve_sun=reward,
        refund_reserve_sun=refund,
        operating_buffer_sun=operating,
    )


@transaction.atomic
def commit_reward(*, allocation_id, commitment_ref, amount_sun):
    """Persist one bounded reward commitment with a global reserve lock."""
    if type(commitment_ref) is not str or not commitment_ref:
        raise ValidationError("commitment_ref_required")
    amount = _positive_sun(amount_sun, "amount_sun")

    allocations = list(
        PropRewardReserveAllocation.objects.select_for_update().order_by("id")
    )
    allocation = next(
        (row for row in allocations if row.pk == allocation_id), None
    )
    if allocation is None:
        raise ValidationError("unknown_reserve_allocation")
    if PropRewardCommitment.objects.filter(
        commitment_ref=commitment_ref
    ).exists():
        raise ValidationError("duplicate_reward_commitment")

    order_available = (
        allocation.reward_reserve_sun - allocation.committed_reward_sun
    )
    total_available = sum(
        row.reward_reserve_sun - row.committed_reward_sun
        for row in allocations
    )
    if amount > order_available:
        raise ValidationError("reward_exceeds_order_reserve")
    if amount > total_available:
        raise ValidationError("reward_reserve_shortfall")

    commitment = PropRewardCommitment.objects.create(
        allocation=allocation,
        commitment_ref=commitment_ref,
        amount_sun=amount,
    )
    allocation.committed_reward_sun += amount
    allocation.save(update_fields=["committed_reward_sun", "updated_at"])
    return commitment


def reward_reserve_snapshot():
    """Return durable obligations; no virtual principal is included."""
    allocations = PropRewardReserveAllocation.objects.all()
    total = sum(row.reward_reserve_sun for row in allocations)
    committed = sum(row.committed_reward_sun for row in allocations)
    return {
        "total_reward_reserve_sun": total,
        "committed_rewards_sun": committed,
        "available_reward_reserve_sun": total - committed,
        "virtual_principal_requirement_sun": 0,
    }
