"""Private payment reconciliation bridge for isolated MOJ PROP ownership.

The source database contains the independently attested payment receipt. This
adapter reads that receipt through an explicitly configured source alias and
writes only opaque identity/payment ownership data to the isolated mojprop
alias. It never trusts browser data, creates a public invoice, sends mail,
moves funds, or creates a simulation account.
"""

from dataclasses import dataclass
import re

from django.conf import settings
from django.db import transaction

from config.mojprop_db_router import MOJPROP_DB_ALIAS
from .models import (
    PropPlan1Receipt,
    PropSimulationIdentity,
    PropSimulationInvoiceOwner,
)
from .plan1_invoice import AMOUNT_SUN, CONTRACT_VERSION, NETWORK
from .simulation_identity_adapter import (
    IdentityAdapterClosed,
    _identity_keys,
    normalize_email,
)


class PaymentReconciliationClosed(RuntimeError):
    """Raised when the independent settlement boundary cannot be proven."""


@dataclass(frozen=True)
class SettlementAttestation:
    invoice_ref: str
    tx_hash: str
    evidence_digest: str
    network: str
    amount_sun: int
    trusted_reconciler_attestation: bool


@dataclass(frozen=True)
class InvoiceOwnershipResult:
    invoice_ref: str
    identity_id: int
    owner_id: int
    created: bool
    settlement_verified: bool = True


_INVOICE_REF_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,95}\Z")
_TX_HASH_RE = re.compile(r"[A-Za-z0-9]{20,128}\Z")
_HEX_DIGEST_RE = re.compile(r"[0-9a-f]{64}\Z")
_SUPPORTED_AMOUNTS = frozenset({18_000_000, AMOUNT_SUN})


def _source_alias(source_alias: str) -> str:
    configured = getattr(
        settings, "MPW_MOJPROP_RECONCILIATION_SOURCE_ALIAS", ""
    )
    if (
        not isinstance(source_alias, str)
        or not source_alias
        or source_alias == MOJPROP_DB_ALIAS
        or not isinstance(configured, str)
        or configured != source_alias
    ):
        raise PaymentReconciliationClosed(
            "explicit configured source database alias is required"
        )
    return source_alias


def _validate_attestation(attestation: SettlementAttestation) -> None:
    if type(attestation) is not SettlementAttestation:
        raise TypeError("exact settlement attestation required")
    if (
        not isinstance(attestation.invoice_ref, str)
        or _INVOICE_REF_RE.fullmatch(attestation.invoice_ref) is None
    ):
        raise PaymentReconciliationClosed("bounded invoice reference required")
    if (
        not isinstance(attestation.tx_hash, str)
        or _TX_HASH_RE.fullmatch(attestation.tx_hash) is None
    ):
        raise PaymentReconciliationClosed("bounded transaction hash required")
    if (
        not isinstance(attestation.evidence_digest, str)
        or _HEX_DIGEST_RE.fullmatch(attestation.evidence_digest) is None
    ):
        raise PaymentReconciliationClosed("lowercase evidence digest required")
    if attestation.network != NETWORK:
        raise PaymentReconciliationClosed("settlement network mismatch")
    if attestation.amount_sun not in _SUPPORTED_AMOUNTS:
        raise PaymentReconciliationClosed("unsupported settlement amount")
    if attestation.trusted_reconciler_attestation is not True:
        raise PaymentReconciliationClosed(
            "trusted reconciler attestation is required"
        )


def _read_verified_receipt(
    *, source_alias: str, attestation: SettlementAttestation
):
    try:
        receipt = (
            PropPlan1Receipt.objects.using(source_alias)
            .select_related("invoice", "ledger")
            .get(invoice__order_ref=attestation.invoice_ref)
        )
    except PropPlan1Receipt.DoesNotExist as exc:
        raise PaymentReconciliationClosed(
            "independently settled invoice receipt not found"
        ) from exc

    invoice = receipt.invoice
    ledger = receipt.ledger
    if (
        invoice.status != "paid"
        or invoice.contract_version != CONTRACT_VERSION
        or invoice.network != NETWORK
        or invoice.amount_sun not in _SUPPORTED_AMOUNTS
        or invoice.amount_sun != attestation.amount_sun
        or invoice.buyer_terms_acceptance is not True
    ):
        raise PaymentReconciliationClosed("source invoice contract is not settled")
    if (
        ledger.network != NETWORK
        or ledger.amount_sun != invoice.amount_sun
        or ledger.tx_hash != attestation.tx_hash
        or ledger.evidence_digest != attestation.evidence_digest
        or ledger.trusted_reconciler_attestation is not True
    ):
        raise PaymentReconciliationClosed("source settlement evidence mismatch")
    return invoice, ledger


def reconcile_settled_invoice(
    *,
    source_alias: str,
    attestation: SettlementAttestation,
) -> InvoiceOwnershipResult:
    """Bind one source-settled invoice to opaque isolated ownership."""
    source_alias = _source_alias(source_alias)
    _validate_attestation(attestation)
    invoice, ledger = _read_verified_receipt(
        source_alias=source_alias, attestation=attestation
    )
    try:
        email = normalize_email(invoice.buyer_email)
        subject_key, email_digest = _identity_keys(email)
    except IdentityAdapterClosed as exc:
        raise PaymentReconciliationClosed(
            "buyer identity cannot be derived from source receipt"
        ) from exc

    with transaction.atomic(using=MOJPROP_DB_ALIAS):
        identity, _identity_created = (
            PropSimulationIdentity.objects.using(MOJPROP_DB_ALIAS)
            .select_for_update()
            .get_or_create(
                provider="email",
                subject_key=subject_key,
                defaults={
                    "email_digest": email_digest,
                    "status": PropSimulationIdentity.Status.PENDING,
                },
            )
        )
        if identity.email_digest != email_digest:
            raise PaymentReconciliationClosed("identity digest mismatch")
        if identity.status == PropSimulationIdentity.Status.BLOCKED:
            raise PaymentReconciliationClosed("identity is blocked")

        owner, created = (
            PropSimulationInvoiceOwner.objects.using(MOJPROP_DB_ALIAS)
            .select_for_update()
            .get_or_create(
                invoice_ref=invoice.order_ref,
                defaults={
                    "identity_id": identity.pk,
                    "buyer_email_digest": email_digest,
                    "settlement_reference": ledger.tx_hash,
                    "settlement_verified": True,
                    "contract_version": invoice.contract_version,
                },
            )
        )
        if (
            owner.identity_id != identity.pk
            or owner.buyer_email_digest != email_digest
            or owner.settlement_reference != ledger.tx_hash
            or owner.settlement_verified is not True
            or owner.contract_version != invoice.contract_version
        ):
            raise PaymentReconciliationClosed(
                "existing isolated invoice ownership is immutable and mismatched"
            )
        return InvoiceOwnershipResult(
            invoice_ref=invoice.order_ref,
            identity_id=int(identity.pk),
            owner_id=int(owner.pk),
            created=created,
        )
