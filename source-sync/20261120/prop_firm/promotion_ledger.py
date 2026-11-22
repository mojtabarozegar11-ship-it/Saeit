"""Atomic, idempotent 14-level promotion transition ledger.

This module is source-only until the complete Moj Prop production bundle,
database migration compatibility, worker lifecycle and treasury gates are
independently verified. It does not call a broker, transfer funds, create a
customer, or open checkout.

The existing PropDecisionLog unique(account, decision_key) is used as the
immutable transition receipt. The account row and its receipt are written in
one transaction under the account row lock, so a retry cannot promote twice.
"""

from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction

from .models import PropAccount, PropDecisionLog
from .rules import LEVELS


class PromotionTransitionRejected(ValueError):
    """Raised when a verified one-tier transition cannot be committed."""


def _text(value, name, limit):
    if type(value) is not str or not value.strip() or len(value) > limit:
        raise PromotionTransitionRejected(f"{name} is invalid")
    return value.strip()


def _digest(value, name):
    value = _text(value, name, 64).lower()
    if len(value) != 64:
        raise PromotionTransitionRejected(f"{name} must be a SHA-256 digest")
    try:
        int(value, 16)
    except ValueError as exc:
        raise PromotionTransitionRejected(f"{name} must be hexadecimal") from exc
    return value


def _payload(*, account, from_index, target_index, evidence_digest,
             funding_evidence_digest):
    return [
        "atomic_stage_transition_v1",
        f"from_tier={from_index}",
        f"to_tier={target_index}",
        f"from_capital_usd={account.starting_capital_usd}",
        f"to_capital_usd={LEVELS[target_index]}",
        f"policy_version={account.policy_version}",
        f"performance_evidence={evidence_digest}",
        f"funding_evidence={funding_evidence_digest}",
    ]


def _replay_result(account, existing, payload):
    """Validate and return an already-committed transition receipt."""
    if (
        existing.category != "promotion"
        or existing.qualifies is not True
        or existing.policy_version != account.policy_version
        or existing.reasons != payload
    ):
        raise PromotionTransitionRejected(
            "decision key already binds to different transition evidence"
        )
    try:
        from_index = int(payload[1].split("=", 1)[1])
        target_index = int(payload[2].split("=", 1)[1])
    except (IndexError, ValueError) as exc:
        raise PromotionTransitionRejected(
            "stored transition receipt is malformed"
        ) from exc
    if (
        not 0 <= from_index < target_index < len(LEVELS)
        or account.tier_index != target_index
        or account.starting_capital_usd != Decimal(LEVELS[target_index])
        or account.status != PropAccount.Status.ACTIVE
    ):
        raise PromotionTransitionRejected(
            "account state does not match the committed transition receipt"
        )
    return {
        "status": "idempotent_replay",
        "decision_id": existing.pk,
        "account_id": str(account.pk),
        "from_tier": from_index,
        "to_tier": target_index,
        "starting_capital_usd": str(account.starting_capital_usd),
    }


def commit_next_level_transition(
    *,
    account_id,
    decision_key,
    evidence_digest,
    funding_evidence_digest,
    verified_pass=False,
    funding_verified=False,
):
    """Commit exactly one verified next-tier transition.

    Preconditions intentionally require a PASSED funded compartment, trusted
    performance evidence and independently verified next-tier capacity.
    The function never infers either approval from a browser request, a
    boolean stored on an old decision, or a payment receipt.

    A repeated call with the same decision key and identical evidence returns
    the original transition receipt without changing the account again.
    """

    if type(account_id) is not str or not account_id.strip():
        raise PromotionTransitionRejected("account_id is required")
    decision_key = _text(decision_key, "decision_key", 96)
    evidence_digest = _digest(evidence_digest, "evidence_digest")
    funding_evidence_digest = _digest(
        funding_evidence_digest, "funding_evidence_digest"
    )
    if verified_pass is not True:
        raise PromotionTransitionRejected("independently verified pass required")
    if funding_verified is not True:
        raise PromotionTransitionRejected("next-tier capacity verification required")

    with transaction.atomic():
        account = (
            PropAccount.objects.select_for_update()
            .select_related("trader", "challenge_enrollment")
            .get(pk=account_id)
        )

        if account.kind != PropAccount.Kind.FUNDED:
            raise PromotionTransitionRejected(
                "only a funded simulation compartment can transition levels"
            )

        existing = (
            PropDecisionLog.objects.select_for_update()
            .filter(account=account, decision_key=decision_key)
            .first()
        )
        if existing is not None:
            expected = _payload(
                account=account,
                from_index=int(existing.reasons[1].split("=", 1)[1])
                if isinstance(existing.reasons, list) and len(existing.reasons) > 2
                and str(existing.reasons[1]).startswith("from_tier=")
                else -1,
                target_index=int(existing.reasons[2].split("=", 1)[1])
                if isinstance(existing.reasons, list) and len(existing.reasons) > 2
                and str(existing.reasons[2]).startswith("to_tier=")
                else -1,
                evidence_digest=evidence_digest,
                funding_evidence_digest=funding_evidence_digest,
            )
            return _replay_result(account, existing, expected)

        if account.status != PropAccount.Status.PASSED:
            raise PromotionTransitionRejected("account must be PASSED before promotion")
        if account.tier_index >= len(LEVELS) - 1:
            raise PromotionTransitionRejected("maximum level already reached")

        from_index = account.tier_index
        target_index = from_index + 1
        payload = _payload(
            account=account,
            from_index=from_index,
            target_index=target_index,
            evidence_digest=evidence_digest,
            funding_evidence_digest=funding_evidence_digest,
        )

        # Account.clean() still enforces the immutable purchased contract,
        # KYC/eligibility, and funded-tier capital constraints.
        account.tier_index = target_index
        account.starting_capital_usd = Decimal(LEVELS[target_index])
        account.status = PropAccount.Status.ACTIVE
        try:
            account.full_clean()
        except ValidationError as exc:
            raise PromotionTransitionRejected(
                "account contract or eligibility validation failed"
            ) from exc

        decision = PropDecisionLog.objects.create(
            account=account,
            decision_key=decision_key,
            category="promotion",
            policy_version=account.policy_version,
            qualifies=True,
            reasons=payload,
            evidence_digest=evidence_digest,
        )
        account.save(
            update_fields=["tier_index", "starting_capital_usd", "status", "updated_at"]
        )
        return {
            "status": "committed",
            "decision_id": decision.pk,
            "account_id": str(account.pk),
            "from_tier": from_index,
            "to_tier": target_index,
            "starting_capital_usd": str(account.starting_capital_usd),
        }
