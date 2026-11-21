"""Live, isolated Starter30 native-TRX checkout and settlement.

The route is English-only and uses only the dedicated mojprop database.
It accepts exactly 30 TRX, verifies a submitted transaction through two
independent SolidityNode providers, and grants a simulated account only inside
one database transaction after both proofs agree. A payer wallet may be supplied to bind an invoice, but it is optional; when omitted, the settled sender is recorded from the verified on-chain transfer.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
import secrets
import string

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from config.mojprop_db_router import MOJPROP_DB_ALIAS
from prop_firm.models import (
    PropSimulationAccount,
    PropSimulationIdentity,
    PropSimulationInvoiceOwner,
    PropSimulationPayment,
)
from prop_firm.simulation_identity_adapter import normalize_email, _identity_keys
from prop_firm.starter30_receiver_pool import (
    InvoiceAttributionUnavailable,
    attested_receivers,
    require_payment_binding,
    select_unused_receiver,
)
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
TERMS_REF = SIMULATION_POLICY.contract_version  # Immutable new invoice policy identifier.
_RELEASE_FLAGS = (
    "MPW_MOJPROP_PRODUCTION_RELEASE_APPROVED",
    "MPW_MOJPROP_TRX_RELEASE_ENABLED",
    "MPW_MOJPROP_TRX_RPC_ATTESTED",
    # Independent commercial evidence: generic switches and RPC setup alone
    # never authorize collection of a customer fee.
    "MPW_MOJPROP_SELLER_ELIGIBILITY_VERIFIED",
    "MPW_MOJPROP_INVOICE_CUSTODY_VERIFIED",
    "MPW_MOJPROP_REWARD_RESERVE_VERIFIED",
    "MPW_MOJPROP_REWARD_SETTLEMENT_RAIL_VERIFIED",
    "MPW_MOJPROP_DELIVERY_RECOVERY_VERIFIED",
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
    """Reject new invoices unless RPC, contract, reward and schema gates pass.

    This checks local configuration and performs read-only isolated payment
    table UNIQUE-index introspection. It is NOT live RPC connectivity, verified
    cash custody, a buyer transfer, full database backup or a payout receipt.
    """
    require_release()
    try:
        _provider_pair()
        _hex_recipient(approved_recipient())
        attested_receivers()
        # A non-verified anonymous mailbox must never consume a permanent
        # receiving address, even when all TRON RPC connections work.
        from prop_firm.starter30_checkout_email import require_email_verification_release
        require_email_verification_release()
    except (PaymentHold, ValueError, TypeError) as exc:
        raise Starter30PaymentRejected(
            "TRON verification configuration is unavailable; no invoice may be issued"
        ) from exc
    # A configured TRON receiver and working RPCs do not prove 100%-of-profit
    # payout capability. No NEW invoice is allowed until the actual evaluator,
    # immutable owner terms and externally verified cash reserve/rail all match.
    # Historical invoices are handled by separate reconciliation, not this gate.
    from prop_firm.starter30_paid_admission import (
        require_paid_admission_readiness,
        require_live_unique_invoice_recipient_schema,
    )
    require_paid_admission_readiness()
    require_live_unique_invoice_recipient_schema()


def issue_invoice(
    *, email: str, payer_address: str | None = None,
    terms_accepted: bool, email_proof: str = "",
) -> IssuedStarter30Invoice:
    """Allocate an exclusive receiving address only to a verified guest email.

    The email identity row is locked to make repeat issuance idempotent across
    sessions. The DB UNIQUE recipient constraint handles concurrent *different*
    emails competing for the same address; no exposed address is ever recycled.
    """
    require_release()
    if terms_accepted is not True:
        raise Starter30PaymentRejected("simulation disclosure must be accepted")
    verify_pre_invoice_configuration()
    from prop_firm.starter30_checkout_email import (
        CheckoutEmailUnavailable, verify_checkout_email_proof,
    )
    try:
        verified_identity_id = verify_checkout_email_proof(email, email_proof)
    except CheckoutEmailUnavailable as exc:
        raise Starter30PaymentRejected(str(exc)) from exc
    receivers = attested_receivers()
    normalized = normalize_email(email)
    payer_hex41 = _payer_hex(payer_address) if payer_address and payer_address.strip() else None
    subject_key, email_digest = _identity_keys(normalized)
    for _ in range(min(len(receivers) + 1, 8)):
        try:
            with transaction.atomic(using=MOJPROP_DB_ALIAS):
                # No get_or_create: issuing an invoice never implicitly creates
                # a buyer identity bypassing the email OTP verification.
                identity = (
                    PropSimulationIdentity.objects.using(MOJPROP_DB_ALIAS)
                    .select_for_update()
                    .get(pk=verified_identity_id, provider="email", subject_key=subject_key)
                )
                if (
                    identity.email_digest != email_digest
                    or identity.status == PropSimulationIdentity.Status.BLOCKED
                ):
                    raise Starter30PaymentRejected("email identity is unavailable")
                now = timezone.now()
                # A retried checkout for the same verified email reuses exactly
                # one non-expired pending invoice; no new address is burned.
                previous = (
                    PropSimulationPayment.objects.using(MOJPROP_DB_ALIAS)
                    .filter(
                        invoice_owner__identity_id=identity.pk,
                        status=PropSimulationPayment.Status.AWAITING,
                        expires_at__gt=now,
                    )
                    .select_related("invoice_owner")
                    .order_by("-issued_at")
                    .first()
                )
                if previous is not None:
                    # Never reuse a prior-policy invoice for a new v2 customer.
                    if (
                        previous.invoice_owner.contract_version != TERMS_REF
                        or previous.terms_acceptance_ref != TERMS_REF
                    ):
                        raise Starter30PaymentRejected(
                            "previous invoice has a different immutable contract; contact support"
                        )
                    if previous.recipient not in receivers:
                        raise Starter30PaymentRejected("previous invoice requires support")
                    if (previous.payer_hex41 or None) != payer_hex41:
                        raise Starter30PaymentRejected(
                            "existing invoice sending-wallet option differs; contact support"
                        )
                    return IssuedStarter30Invoice(
                        previous.payment_ref,
                        previous.invoice_owner.invoice_ref,
                        previous.recipient,
                        previous.amount_sun,
                        previous.expires_at,
                    )
                used = set(
                    PropSimulationPayment.objects.using(MOJPROP_DB_ALIAS)
                    .filter(recipient__in=receivers)
                    .values_list("recipient", flat=True)
                )
                recipient = select_unused_receiver(receivers, used)
                if payer_hex41 and payer_hex41 == _hex_recipient(recipient):
                    raise Starter30PaymentRejected("payer wallet cannot be invoice receiving wallet")
                invoice_ref = _token("MOJPROP30-")
                payment_ref = _token("PAY-")
                expires_at = now + timedelta(hours=24)
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
                    recipient=recipient,
                    amount_sun=NATIVE_AMOUNT_SUN,
                    payer_hex41=payer_hex41,
                    issued_at=now,
                    expires_at=expires_at,
                    terms_acceptance_ref=TERMS_REF,
                    status=PropSimulationPayment.Status.AWAITING,
                )
                return IssuedStarter30Invoice(
                    payment_ref, invoice_ref, recipient, NATIVE_AMOUNT_SUN, expires_at
                )
        except IntegrityError:
            # Roll back a concurrent unique-recipient conflict, then re-read
            # the remaining pool. Never silently double-credit one address.
            continue
        except ValidationError as exc:
            errors = getattr(exc, "error_dict", {})
            if set(errors) == {"recipient"} and all(
                getattr(error, "code", None) == "unique"
                for error in errors.get("recipient", ())
            ):
                # Model.full_clean checks the uniqueness constraint before the
                # DB insert. A losing allocator must retry, not return HTTP 500.
                continue
            raise Starter30PaymentRejected("invoice validation failed") from exc
        except InvoiceAttributionUnavailable as exc:
            raise Starter30PaymentRejected(str(exc)) from exc
    raise Starter30PaymentRejected(
        "invoice receiver could not be exclusively allocated; retry later"
    )


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
    if transfer_a.amount_sun != NATIVE_AMOUNT_SUN:
        raise Starter30PaymentRejected("exact 30 native TRX transfer is required")
    outcome = _settle_verified_invoice(invoice_ref=invoice_ref, transfer_a=transfer_a)
    if outcome is _EXPIRED_INVOICE:
        raise Starter30PaymentRejected("invoice has expired")
    return outcome


_EXPIRED_INVOICE = object()


def _settle_verified_invoice(*, invoice_ref: str, transfer_a):
    """Commit expiry before error; keep all other settlement work atomic."""
    with transaction.atomic(using=MOJPROP_DB_ALIAS):
        payment = (
            PropSimulationPayment.objects.using(MOJPROP_DB_ALIAS)
            .select_for_update()
            .select_related("invoice_owner", "invoice_owner__identity")
            .get(invoice_owner__invoice_ref=invoice_ref)
        )
        # An on-chain txid is public. Only the exclusive invoice recipient
        # identifies which buyer's invoice this transfer actually pays.
        try:
            require_payment_binding(
                recorded_recipient=payment.recipient,
                onchain_recipient=transfer_a.recipient,
            )
        except InvoiceAttributionUnavailable as exc:
            raise Starter30PaymentRejected(str(exc)) from exc
        now = timezone.now()  # sample clock only AFTER the locked row is acquired
        if payment.status == PropSimulationPayment.Status.PAID:
            if payment.txid == transfer_a.tx_hash:
                return _paid_result(payment)
            raise Starter30PaymentRejected("invoice is already settled")
        if payment.status not in (
            PropSimulationPayment.Status.AWAITING,
            PropSimulationPayment.Status.EXPIRED,
        ):
            raise Starter30PaymentRejected("invoice is not awaiting payment")
        # Existing v1 invoices require separately version-aware reconciliation.
        if (
            payment.invoice_owner.contract_version != TERMS_REF
            or payment.terms_acceptance_ref != TERMS_REF
        ):
            raise Starter30PaymentRejected(
                "invoice policy version requires manual support before settlement"
            )
        # A wrong/out-of-window txid can expire an invoice even though a genuine
        # in-window transfer may still be awaiting independent confirmation.
        # Accept only the original invoice-window proof, never a late transfer.
        # An early admin expiration is not automatically reversible.
        if payment.status == PropSimulationPayment.Status.EXPIRED and now < payment.expires_at:
            raise Starter30PaymentRejected("invoice is not awaiting payment")
        transfer_in_window = payment.issued_at <= transfer_a.block_time < payment.expires_at
        if now >= payment.expires_at and not transfer_in_window:
            if payment.status == PropSimulationPayment.Status.AWAITING:
                payment.status = PropSimulationPayment.Status.EXPIRED
                payment.save(using=MOJPROP_DB_ALIAS, update_fields=["status", "updated_at"])
            return _EXPIRED_INVOICE
        if not transfer_in_window:
            raise Starter30PaymentRejected("payment is outside the invoice window")
        if payment.payer_hex41:
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
        # Persist the verified on-chain sender in canonical 0x41-prefixed hex,
        # not its Base58Check display form, for consistent future reconciliation.
        payment.sender_hex41 = _hex_recipient(transfer_a.sender)
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
    """Report actual time-expired invoice status without a database mutation.

    The old settlement path still requires a separate transactional expiry
    persistence fix (issue #2799). This read-only customer display change
    never credits payment, extends an invoice or activates an account.
    """
    require_release()
    payment = PropSimulationPayment.objects.using(MOJPROP_DB_ALIAS).select_related(
        "invoice_owner"
    ).get(invoice_owner__invoice_ref=invoice_ref)
    effective_status = payment.status
    if (
        effective_status == PropSimulationPayment.Status.AWAITING
        and timezone.now() >= payment.expires_at
    ):
        effective_status = PropSimulationPayment.Status.EXPIRED
    return {
        "status": effective_status,
        "payment_ref": payment.payment_ref,
        "invoice_ref": invoice_ref,
        "recipient": payment.recipient,
        "amount_sun": payment.amount_sun,
        "expires_at": payment.expires_at,
        "txid": payment.txid,
    }
