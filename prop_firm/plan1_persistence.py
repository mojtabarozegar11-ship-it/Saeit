"""Atomic persistence boundary for a future MOJ-PROP-01 settlement adapter.

No public endpoint may call record_verified_settlement. A private adapter must
provide an independently verified reconciliation attestation.
"""
import re

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from .models import (
    PropPlan1Invoice,
    PropPlan1Receipt,
    TronSettlementLedger,
)
from .plan1_invoice import AMOUNT_SUN, CONTRACT_VERSION, NETWORK


_EMAIL = re.compile(r"^[^@\\s]+@[^@\\s]+\\.[^@\\s]+$")


def persist_plan1_invoice(
    *,
    order_ref,
    buyer_email,
    buyer_terms_acceptance,
    recipient,
    contract_digest,
):
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
        "contract_version": CONTRACT_VERSION,
        "network": NETWORK,
        "amount_sun": AMOUNT_SUN,
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
            immutable = (
                invoice.buyer_email == buyer_email
                and invoice.product_code == defaults["product_code"]
                and invoice.contract_version == defaults["contract_version"]
                and invoice.network == defaults["network"]
                and invoice.amount_sun == defaults["amount_sun"]
                and invoice.recipient == defaults["recipient"]
                and invoice.buyer_terms_acceptance is True
                and invoice.contract_digest == defaults["contract_digest"]
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
    if not isinstance(tx_hash, str) or not re.fullmatch(r"[A-Za-z0-9]{20,128}", tx_hash):
        raise ValidationError("Bounded transaction hash required")
    if not isinstance(evidence_digest, str) or len(evidence_digest) != 64:
        raise ValidationError("Evidence digest required")

    with transaction.atomic():
        invoice = PropPlan1Invoice.objects.select_for_update().get(pk=invoice_id)
        if invoice.amount_sun != AMOUNT_SUN or invoice.network != NETWORK:
            raise ValidationError("Invoice contract drift")
        if invoice.status != "pending":
            raise ValidationError("Invoice is not pending")
        try:
            ledger = TronSettlementLedger.objects.create(
                network=NETWORK,
                tx_hash=tx_hash,
                amount_sun=AMOUNT_SUN,
                evidence_digest=evidence_digest,
                trusted_reconciler_attestation=True,
            )
        except IntegrityError as exc:
            raise ValidationError("Transaction hash already settled") from exc
        invoice.status = "paid"
        invoice.save(update_fields=["status"])
        return PropPlan1Receipt.objects.create(invoice=invoice, ledger=ledger)
