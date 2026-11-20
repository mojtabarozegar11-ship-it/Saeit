"""Live, isolated Starter30 native-TRX checkout and settlement.

The route is English-only and uses only the dedicated mojprop database.
It accepts exactly 30 TRX, verifies a submitted transaction through two
independent SolidityNode providers, and grants a simulated account only inside
one database transaction after both proofs agree.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
import secrets
import string

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from config.mojprop_db_router import MOJPROP_DB_ALIAS
from prop_firm.models import (
    PropSimulationAccount,
    PropSimulationIdentity,
    PropSimulationInvoiceOwner,
    PropSimulationPayment,
)
from prop_firm.simulation_identity_adapter import normalize_email, _identity_keys
from prop_firm.simulation_policy import SIMULATION_POLICY
from services.mojprop_starter30_tron_settlement import (
    NATIVE_AMOUNT_SUN,
    PRODUCT,
    _hex_recipient,
)
from services.mpw_tron_independent_solidified_rpc import (
    RpcProvider,
    hex_to_tron_address,
    query_solidified_transfer,
    verify_distinct_provider_config,
)
from services.mpw_trx_walletless_core import PaymentHold
from services.mojtaba_tron_owner_receiver import approved_recipient

NETWORK = "tron-mainnet"
TERMS_REF = "starter30-simulation-v1"
_RELEASE_FLAGS = (
    "MPW_MOJPROP_PRODUCTION_RELEASE_APPROVED",
    "MPW_MOJPROP_TRX_RELEASE_ENABLED",
    "MPW_MOJPROP_TRX_RPC_ATTESTED",
)


class Starter30ReleaseClosed(RuntimeError):
    pass


class Starter30PaymentRejected(ValueError):
    pass


def release_is_open() -> bool:
    return (
        getattr(settings, "MPW_MOJPROP_DB_ALIAS_ENABLED", False) is True
        and getattr(settings, "MPW_MOJPROP_DEPLOYMENT_ENV", "") == "production"
        and all(getattr(settings, name, False) is True for name in _RELEASE_FLAGS)
    )


def require_release() -> None:
    if not release_is_open():
        raise Starter30ReleaseClosed("Starter30 payment release is not enabled")


def _provider_pair() -> tuple[RpcProvider, RpcProvider]:
    require_release()
    first = RpcProvider(
        source_id=getattr(settings, "MPW_MOJPROP_RPC_A_SOURCE_ID", ""),
        operator_id=getattr(settings, "MPW_MOJPROP_RPC_A_OPERATOR_ID", ""),
        endpoint=getattr(settings, "MPW_MOJPROP_RPC_A_ENDPOINT", ""),
        api_key=getattr(settings, "MPW_MOJPROP_RPC_A_API_KEY", ""),
    )
    second = RpcProvider(
        source_id=getattr(settings, "MPW_MOJPROP_RPC_B_SOURCE_ID", ""),
        operator_id=getattr(settings, "MPW_MOJPROP_RPC_B_OPERATOR_ID", ""),
        endpoint=getattr(settings, "MPW_MOJPROP_RPC_B_ENDPOINT", ""),
        api_key=getattr(settings, "MPW_MOJPROP_RPC_B_API_KEY", ""),
    )
    verify_distinct_provider_config(first, second)
    return first, second


def _token(prefix: str) -> str:
    alphabet = string.ascii_uppercase + string.digits
    return prefix + "".join(secrets.choice(alphabet) for _ in range(20))


def _payer_hex(raw: str) -> str:
    try:
        value = _hex_recipient(raw)
    except (ValueError, TypeError, OverflowError) as exc:
        raise Starter30PaymentRejected("valid TRON wallet address is required") from exc
    if value == _hex_recipient(approved_recipient()):
        raise Starter30PaymentRejected("payer wallet must differ from the receiving wallet")
    return value


@dataclass(frozen=True)
class IssuedStarter30Invoice:
    payment_ref: str
    invoice_ref: str
    recipient: str
    amount_sun: int
    expires_at: object


def verify_pre_invoice_configuration() -> None:
    """Reject invoice creation until two independent RPCs and receiver are configured.

    This is a local configuration preflight, NOT a live RPC connectivity or
    payout-settlement attestation. No database access or value transfer.
    """
    require_release()
    try:
        _provider_pair()
        _hex_recipient(approved_recipient())
    except (PaymentHold, ValueError, TypeError) as exc:
        raise Starter30PaymentRejected(
            "TRON verification configuration is unavailable; no invoice may be issued"
        ) from exc


def issue_invoice(*, email: str, payer_address: str, terms_accepted: bool) -> IssuedStarter30Invoice:
    require_release()
    if terms_accepted is not True:
        raise Starter30PaymentRejected("simulation disclosure must be accepted")
    verify_pre_invoice_configuration()
    normalized = normalize_email(email)
    payer_hex41 = _payer_hex(payer_address)
    subject_key, email_digest = _identity_keys(normalized)
    now = timezone.now()
    expires_at = now + timedelta(hours=24)
    with transaction.atomic(using=MOJPROP_DB_ALIAS):
        identity, _ = PropSimulationIdentity.objects.using(MOJPROP_DB_ALIAS).get_or_create(
            provider="email",
            subject_key=subject_key,
            defaults={
                "email_digest": email_digest,
                "status": PropSimulationIdentity.Status.PENDING,
            },
        )
        if identity.email_digest != email_digest or identity.status == PropSimulationIdentity.Status.BLOCKED:
            raise Starter30PaymentRejected("email identity is unavailable")
        invoice_ref = _token("MOJPROP30-")
        payment_ref = _token("PAY-")
        owner = PropSimulationInvoiceOwner.objects.using(MOJPROP_DB_ALIAS).create(
            identity=identity,
            invoice_ref=invoice_ref,
            buyer_email_digest=email_digest,
            settlement_verified=False,
            contract_version=TERMS_REF,
        )
        PropSimulationPayment.objects.using(MOJPROP_DB_ALIAS).create(
            invoice_owner=owner,
            payment_ref=payment_ref,
            product=PRODUCT,
            network=NETWORK,
            recipient=approved_recipient(),
            amount_sun=NATIVE_AMOUNT_SUN,
            payer_hex41=payer_hex41,
            issued_at=now,
            expires_at=expires_at,
            terms_acceptance_ref=TERMS_REF,
            status=PropSimulationPayment.Status.AWAITING,
        )
    return IssuedStarter30Invoice(payment_ref, invoice_ref, approved_recipient(), NATIVE_AMOUNT_SUN, expires_at)


def settle_invoice(*, invoice_ref: str, txid: str) -> dict:
    require_release()
    try:
        first, second = _provider_pair()
    except (PaymentHold, ValueError, TypeError) as exc:
        raise Starter30PaymentRejected(
            "Independent TRON verification configuration is unavailable"
        ) from exc
    try:
        transfer_a = query_solidified_transfer(first, txid)
        transfer_b = query_solidified_transfer(second, txid)
    except Exception as exc:
        raise Starter30PaymentRejected("transaction could not be solidified by both providers") from exc
    if (
        transfer_a.tx_hash != transfer_b.tx_hash
        or transfer_a.network != NETWORK
        or transfer_b.network != NETWORK
        or transfer_a.sender != transfer_b.sender
        or transfer_a.recipient != transfer_b.recipient
        or transfer_a.amount_sun != transfer_b.amount_sun
        or transfer_a.block_time != transfer_b.block_time
        or transfer_a.solidified is not True
        or transfer_b.solidified is not True
    ):
        raise Starter30PaymentRejected("two provider proofs disagree")
    if transfer_a.recipient != approved_recipient() or transfer_a.amount_sun != NATIVE_AMOUNT_SUN:
        raise Starter30PaymentRejected("exact 30 TRX transfer to the approved receiver is required")
    outcome = _settle_verified_invoice(invoice_ref=invoice_ref, transfer_a=transfer_a)
    if outcome is _EXPIRED_INVOICE:
        # The EXPIRED write has committed; do not raise inside transaction.atomic.
        raise Starter30PaymentRejected("invoice has expired")
    return outcome


_EXPIRED_INVOICE = object()


def _settle_verified_invoice(*, invoice_ref: str, transfer_a):
    """Persist EXPIRED without rolling it back; all account issuance remains atomic."""
    with transaction.atomic(using=MOJPROP_DB_ALIAS):
        payment = (
            PropSimulationPayment.objects.using(MOJPROP_DB_ALIAS)
            .select_for_update()
            .select_related("invoice_owner", "invoice_owner__identity")
            .get(invoice_owner__invoice_ref=invoice_ref)
        )
        # Check the expiry AFTER the row lock, not while waiting for it.
        now = timezone.now()
        if payment.status == PropSimulationPayment.Status.PAID:
            if payment.txid == transfer_a.tx_hash:
                return _paid_result(payment)
            raise Starter30PaymentRejected("invoice is already settled")
        if payment.status != PropSimulationPayment.Status.AWAITING:
            raise Starter30PaymentRejected("invoice is not awaiting payment")
        # The blockchain transfer timestamp governs whether payment was on time.
        # Delayed provider confirmation or late user reconciliation must not
        # erase an on-time transfer merely because the invoice has since expired.
        transfer_in_window = payment.issued_at <= transfer_a.block_time < payment.expires_at
        if now >= payment.expires_at and not transfer_in_window:
            payment.status = PropSimulationPayment.Status.EXPIRED
            payment.save(using=MOJPROP_DB_ALIAS, update_fields=["status", "updated_at"])
            return _EXPIRED_INVOICE
        if not transfer_in_window:
            raise Starter30PaymentRejected("payment is outside the invoice window")
        expected_sender = hex_to_tron_address(payment.payer_hex41)
        if transfer_a.sender != expected_sender:
            raise Starter30PaymentRejected("sender does not match the wallet bound to this invoice")
        if PropSimulationPayment.objects.using(MOJPROP_DB_ALIAS).filter(txid=transfer_a.tx_hash).exists():
            raise Starter30PaymentRejected("transaction is already assigned")
        owner = payment.invoice_owner
        identity = owner.identity
        owner.settlement_reference = transfer_a.tx_hash
        owner.settlement_verified = True
        owner.save(using=MOJPROP_DB_ALIAS, update_fields=["settlement_reference", "settlement_verified"])
        identity.status = PropSimulationIdentity.Status.ACTIVE
        identity.save(using=MOJPROP_DB_ALIAS, update_fields=["status", "updated_at"])
        account = PropSimulationAccount(
            identity=identity,
            invoice_owner=owner,
            account_ref=_token("MOJPROP30-ACC-"),
            kind=PropSimulationAccount.Kind.CHALLENGE,
            status=PropSimulationAccount.Status.ACTIVE,
            starting_capital_usd=SIMULATION_POLICY.starting_balance_usd,
            policy_version=SIMULATION_POLICY.contract_version,
            opened_at=now,
        )
        account.save(using=MOJPROP_DB_ALIAS)
        payment.status = PropSimulationPayment.Status.PAID
        payment.txid = transfer_a.tx_hash
        payment.sender_hex41 = payment.payer_hex41
        payment.settled_at = now
        payment.save(using=MOJPROP_DB_ALIAS)
        return {
            "status": "paid",
            "payment_ref": payment.payment_ref,
            "invoice_ref": owner.invoice_ref,
            "account_ref": account.account_ref,
            "simulation_balance_usd": str(account.starting_capital_usd),
            "txid": transfer_a.tx_hash,
        }


def _paid_result(payment) -> dict:
    account = PropSimulationAccount.objects.using(MOJPROP_DB_ALIAS).filter(
        invoice_owner_id=payment.invoice_owner_id
    ).order_by("-created_at").first()
    return {
        "status": "paid",
        "payment_ref": payment.payment_ref,
        "invoice_ref": payment.invoice_owner.invoice_ref,
        "account_ref": account.account_ref if account else None,
        "simulation_balance_usd": str(account.starting_capital_usd) if account else None,
        "txid": payment.txid,
    }


def invoice_status(invoice_ref: str) -> dict:
    require_release()
    payment = PropSimulationPayment.objects.using(MOJPROP_DB_ALIAS).select_related(
        "invoice_owner"
    ).get(invoice_owner__invoice_ref=invoice_ref)
    return {
        "status": payment.status,
        "payment_ref": payment.payment_ref,
        "invoice_ref": invoice_ref,
        "recipient": payment.recipient,
        "amount_sun": payment.amount_sun,
        "expires_at": payment.expires_at,
        "txid": payment.txid,
    }
