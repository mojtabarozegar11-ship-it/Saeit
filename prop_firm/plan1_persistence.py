"""Atomic persistence for Plan 1 settlement and reward-reserve creation.

The settlement adapter must supply an independent reconciliation attestation.
This module never calls a broker, wallet or payout provider.
"""
import re

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from .models import (
    PropPlan1Invoice,
    PropPlan1Receipt,
    TronSettlementLedger,
)
from .plan1_invoice import CONTRACT_VERSION, NETWORK
from .reward_reserve_persistence import (
    SUPPORTED_FEES_SUN,
    allocate_reward_reserve_after_settlement,
)


_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
PURCHASE_KIND_FEES_SUN = {
    "first": 30_000_000,
    "retry": 18_000_000,
}


def _fee_for_purchase_kind(purchase_kind):
    if purchase_kind not in PURCHASE_KIND_FEES_SUN:
        raise ValidationError("unsupported_purchase_kind")
    return PURCHASE_KIND_FEES_SUN[purchase_kind]


def persist_plan1_invoice(
    *,
    order_ref,
    buyer_email,
    buyer_terms_acceptance,
    recipient,
    contract_digest,
    purchase_kind="first",
    retry_eligibility_verified=False,
):
    fee_sun = _fee_for_purchase_kind(purchase_kind)
    if purchase_kind == "retry" and retry_eligibility_verified is not True:
        raise ValidationError("server_retry_eligibility_required")
    if not isinstance(order_ref, str) or not re.fullmatch(
        r"[A-Za-z0-9][A-Za-z0-9._:-]{0,95}", order_ref
    ):
        raise ValidationError("Bounded canonical order reference required")
    if not isinstance(buyer_email, str) or not _EMAIL.fullmatch(buyer_email):
        raise ValidationError("A valid buyer email is required")
    if buyer_terms_acceptance is not True:
        raise ValidationError("Terms acceptance is required")
    if not isinstance(recipient, str) or not recipient:
        raise ValidationError("Recipient is required")
    if not isinstance(contract_digest, str) or len(contract_digest) != 64:
        raise ValidationError("Trusted contract digest is required")

    defaults = {
        "buyer_email": buyer_email,
        "product_code": "MOJ-PROP-01",
        "purchase_kind": purchase_kind,
        "contract_version": CONTRACT_VERSION,
        "network": NETWORK,
        "amount_sun": fee_sun,
        "recipient": recipient,
        "buyer_terms_acceptance": True,
        "contract_digest": contract_digest,
        "status": "pending",
    }
    with transaction.atomic():
        invoice, created = PropPlan1Invoice.objects.select_for_update().get_or_create(
            order_ref=order_ref, defaults=defaults
        )
        if not created:
            immutable = all(
                (
                    invoice.buyer_email == buyer_email,
                    invoice.product_code == defaults["product_code"],
                    invoice.purchase_kind == purchase_kind,
                    invoice.contract_version == defaults["contract_version"],
                    invoice.network == defaults["network"],
                    invoice.amount_sun == fee_sun,
                    invoice.recipient == defaults["recipient"],
                    invoice.buyer_terms_acceptance is True,
                    invoice.contract_digest == defaults["contract_digest"],
                )
            )
            if not immutable:
                raise ValidationError("Invoice identity or contract snapshot is immutable")
        return invoice


def record_verified_settlement(
    *,
    invoice_id,
    tx_hash,
    evidence_digest,
    trusted_reconciler_attestation,
):
    if trusted_reconciler_attestation is not True:
        raise ValidationError("Independent settlement attestation is required")
    if not isinstance(tx_hash, str) or not re.fullmatch(
        r"[A-Za-z0-9]{20,128}", tx_hash
    ):
        raise ValidationError("Bounded transaction hash required")
    if not isinstance(evidence_digest, str) or len(evidence_digest) != 64:
        raise ValidationError("Evidence digest required")

    with transaction.atomic():
        invoice = PropPlan1Invoice.objects.select_for_update().get(pk=invoice_id)
        expected_fee = _fee_for_purchase_kind(invoice.purchase_kind)
        if (
            invoice.amount_sun != expected_fee
            or invoice.amount_sun not in SUPPORTED_FEES_SUN
            or invoice.network != NETWORK
        ):
            raise ValidationError("Invoice contract drift")
        if invoice.status != "pending":
            raise ValidationError("Invoice is not pending")
        try:
            ledger = TronSettlementLedger.objects.create(
                network=NETWORK,
                tx_hash=tx_hash,
                amount_sun=invoice.amount_sun,
                evidence_digest=evidence_digest,
                trusted_reconciler_attestation=True,
            )
        except IntegrityError as exc:
            raise ValidationError("Transaction hash already settled") from exc
        invoice.status = "paid"
        invoice.save(update_fields=["status"])
        receipt = PropPlan1Receipt.objects.create(invoice=invoice, ledger=ledger)
        allocate_reward_reserve_after_settlement(invoice_id=invoice.pk)
        return receipt
