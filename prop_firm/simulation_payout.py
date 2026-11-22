"""Fail-closed commitment ledger for the Starter30 100% profit promise.

This module records a payable liability only after an internal, independently
verified pass. It never sends TRX, touches a broker, or exposes treasury keys.
"""


from decimal import Decimal, InvalidOperation

from django.core.exceptions import ValidationError
from django.db import transaction

from config.mojprop_db_router import MOJPROP_DB_ALIAS
from .models import PropSimulationAccount, PropSimulationPayoutCommitment


PAYOUT_PERCENT = 100


class PayoutCommitmentRejected(ValueError):
    """Raised when a full-profit commitment cannot pass its internal gates."""


def _money(value, field):
    try:
        amount = Decimal(str(value)).quantize(Decimal("0.01"))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise PayoutCommitmentRejected(f"{field} must be a finite USD amount") from exc
    if not amount.is_finite() or amount <= 0:
        raise PayoutCommitmentRejected(f"{field} must be positive")
    return amount


def _digest(value):
    if type(value) is not str or len(value) != 64:
        raise PayoutCommitmentRejected("beneficiary digest must be a 64-character digest")
    try:
        int(value, 16)
    except ValueError as exc:
        raise PayoutCommitmentRejected("beneficiary digest must be hexadecimal") from exc
    return value.lower()


def commit_full_profit_payout(
    *,
    account_ref,
    realized_profit_usd,
    verification_ref,
    beneficiary_digest,
):
    """Create or return one idempotent 100% payout commitment.

    The account must already be marked PASSED by a trusted internal evaluator.
    A beneficiary digest is stored instead of a payout address. Treasury
    settlement remains a separate owner-controlled operation.
    """
    if type(account_ref) is not str or not account_ref.strip():
        raise PayoutCommitmentRejected("account reference is required")
    if type(verification_ref) is not str or not verification_ref.strip():
        raise PayoutCommitmentRejected("independent verification reference is required")
    if len(verification_ref) > 128:
        raise PayoutCommitmentRejected("verification reference is too long")
    profit = _money(realized_profit_usd, "realized_profit_usd")
    beneficiary = _digest(beneficiary_digest)

    with transaction.atomic(using=MOJPROP_DB_ALIAS):
        account = (
            PropSimulationAccount.objects.using(MOJPROP_DB_ALIAS)
            .select_for_update()
            .get(account_ref=account_ref.strip())
        )
        if account.kind != PropSimulationAccount.Kind.FUNDED_SIMULATION:
            raise PayoutCommitmentRejected(
                "only an isolated funded-simulation account can create a payout commitment"
            )
        if account.status != PropSimulationAccount.Status.PASSED:
            raise PayoutCommitmentRejected(
                "only a trusted PASSED simulation account can create a payout commitment"
            )
        existing = (
            PropSimulationPayoutCommitment.objects.using(MOJPROP_DB_ALIAS)
            .select_for_update()
            .filter(account=account)
            .first()
        )
        if existing:
            if (
                existing.realized_profit_usd != profit
                or existing.trader_payout_usd != profit
                or existing.verification_ref != verification_ref
                or existing.beneficiary_digest != beneficiary
            ):
                raise PayoutCommitmentRejected(
                    "existing payout commitment does not match the requested evidence"
                )
            return _result(existing)

        commitment = PropSimulationPayoutCommitment(
            account=account,
            realized_profit_usd=profit,
            trader_payout_usd=profit,
            payout_percent=PAYOUT_PERCENT,
            verification_ref=verification_ref.strip(),
            beneficiary_digest=beneficiary,
            status=PropSimulationPayoutCommitment.Status.PENDING_SETTLEMENT,
        )
        commitment.save(using=MOJPROP_DB_ALIAS)
        return _result(commitment)


def _result(commitment):
    return {
        "status": commitment.status,
        "account_ref": commitment.account.account_ref,
        "realized_profit_usd": str(commitment.realized_profit_usd),
        "trader_payout_usd": str(commitment.trader_payout_usd),
        "payout_percent": commitment.payout_percent,
        "verification_ref": commitment.verification_ref,
        "settlement_reference": commitment.settlement_reference or None,
    }
