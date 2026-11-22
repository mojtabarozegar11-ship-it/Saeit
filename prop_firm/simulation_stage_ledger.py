"""Atomic promotion ledger for the isolated simulated-account domain.

This module never reaches the legacy real-brokerage PropAccount model. It
records one level at a time for PropSimulationAccount and has no broker,
wallet, checkout, email or treasury side effect.
"""

from decimal import Decimal

from django.db import transaction

from config.mojprop_db_router import MOJPROP_DB_ALIAS

from .models import (
    PropSimulationAccount,
    PropSimulationStageTransition,
)
from .rules import LEVELS


class SimulationStageTransitionRejected(ValueError):
    """Raised when an isolated simulated promotion cannot be committed."""


def _text(value, name, limit):
    if type(value) is not str or not value.strip() or len(value) > limit:
        raise SimulationStageTransitionRejected(f"{name} is invalid")
    return value.strip()


def _digest(value, name):
    value = _text(value, name, 64).lower()
    if len(value) != 64:
        raise SimulationStageTransitionRejected(f"{name} must be SHA-256")
    try:
        int(value, 16)
    except ValueError as exc:
        raise SimulationStageTransitionRejected(
            f"{name} must be hexadecimal"
        ) from exc
    return value


def _replay(account, transition, performance_digest, capacity_digest):
    if (
        transition.performance_evidence_digest != performance_digest
        or transition.capacity_evidence_digest != capacity_digest
        or transition.policy_version != account.policy_version
        or account.tier_index != transition.to_tier
        or account.starting_capital_usd != transition.to_capital_usd
        or account.status != PropSimulationAccount.Status.ACTIVE
    ):
        raise SimulationStageTransitionRejected(
            "transition key conflicts with current account evidence"
        )
    return {
        "status": "idempotent_replay",
        "transition_id": transition.pk,
        "account_ref": account.account_ref,
        "from_tier": transition.from_tier,
        "to_tier": transition.to_tier,
        "starting_capital_usd": str(account.starting_capital_usd),
    }


def commit_next_simulated_level(
    *,
    account_ref,
    transition_key,
    performance_evidence_digest,
    capacity_evidence_digest,
    verified_pass=False,
    capacity_verified=False,
):
    """Commit one and only one next level for a simulated funded account.

    The two boolean gates are trusted internal evaluator results, not customer
    HTTP input. A repeated identical call returns the original receipt.
    """

    account_ref = _text(account_ref, "account_ref", 96)
    transition_key = _text(transition_key, "transition_key", 96)
    performance_digest = _digest(
        performance_evidence_digest, "performance_evidence_digest"
    )
    capacity_digest = _digest(
        capacity_evidence_digest, "capacity_evidence_digest"
    )
    if verified_pass is not True:
        raise SimulationStageTransitionRejected(
            "independently verified simulated pass required"
        )
    if capacity_verified is not True:
        raise SimulationStageTransitionRejected(
            "independently verified next-tier capacity required"
        )

    with transaction.atomic(using=MOJPROP_DB_ALIAS):
        account = (
            PropSimulationAccount.objects.using(MOJPROP_DB_ALIAS)
            .select_for_update()
            .select_related("invoice_owner", "identity")
            .get(account_ref=account_ref)
        )
        existing = (
            PropSimulationStageTransition.objects.using(MOJPROP_DB_ALIAS)
            .select_for_update()
            .filter(account=account, transition_key=transition_key)
            .first()
        )
        if existing is not None:
            return _replay(
                account, existing, performance_digest, capacity_digest
            )

        if account.kind != PropSimulationAccount.Kind.FUNDED_SIMULATION:
            raise SimulationStageTransitionRejected(
                "only the isolated funded-simulation kind can promote"
            )
        if account.status != PropSimulationAccount.Status.PASSED:
            raise SimulationStageTransitionRejected(
                "simulation account must be PASSED before promotion"
            )
        if account.invoice_owner.settlement_verified is not True:
            raise SimulationStageTransitionRejected(
                "independently settled entry is required"
            )
        if account.tier_index >= len(LEVELS) - 1:
            raise SimulationStageTransitionRejected(
                "maximum simulated level already reached"
            )

        from_tier = account.tier_index
        to_tier = from_tier + 1
        from_capital = Decimal(LEVELS[from_tier])
        to_capital = Decimal(LEVELS[to_tier])
        if account.starting_capital_usd != from_capital:
            raise SimulationStageTransitionRejected(
                "account capital does not match its current tier"
            )

        account.tier_index = to_tier
        account.starting_capital_usd = to_capital
        account.status = PropSimulationAccount.Status.ACTIVE
        account.save(
            using=MOJPROP_DB_ALIAS,
            update_fields=[
                "tier_index",
                "starting_capital_usd",
                "status",
                "updated_at",
            ],
        )
        transition = PropSimulationStageTransition.objects.using(
            MOJPROP_DB_ALIAS
        ).create(
            account=account,
            transition_key=transition_key,
            from_tier=from_tier,
            to_tier=to_tier,
            from_capital_usd=from_capital,
            to_capital_usd=to_capital,
            policy_version=account.policy_version,
            performance_evidence_digest=performance_digest,
            capacity_evidence_digest=capacity_digest,
        )
        return {
            "status": "committed",
            "transition_id": transition.pk,
            "account_ref": account.account_ref,
            "from_tier": from_tier,
            "to_tier": to_tier,
            "starting_capital_usd": str(account.starting_capital_usd),
        }
