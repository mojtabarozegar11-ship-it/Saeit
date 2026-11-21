"""Pre-invoice email verification for guest Starter30 buyers, not a paid user login.

Public receiving addresses are NEVER permanently reserved merely by entering
an unverified email. One owner-approved transactional code must be delivered,
consumed exactly once and bound to a short-lived signed session capability.

Only the isolated mojprop DB is used; no external paid provider, broker, funds,
or wallet private key. SMTP is disabled unless separately owner-approved.
"""
from __future__ import annotations

from datetime import timedelta
import hmac

from django.conf import settings
from django.core import signing
from django.core.mail import send_mail
from django.db import transaction
from django.utils import timezone

from config.mojprop_db_router import MOJPROP_DB_ALIAS
from prop_firm.models import PropSimulationIdentity, PropSimulationLoginChallenge
from prop_firm.simulation_identity_adapter import (
    IdentityAdapterClosed,
    _identity_keys,
    consume_login_challenge,
    issue_login_challenge,
    normalize_email,
    register_identity,
)

_PURPOSE = PropSimulationLoginChallenge.Purpose.CHECKOUT
_SALT = "mojprop-starter30-verified-email-invoice-v1"
_MAX_PROOF_AGE_SECONDS = 900


class CheckoutEmailUnavailable(ValueError):
    """Independent email / abuse controls are not safe or available."""


def require_email_verification_release() -> None:
    """Hard hold: no SMTP or allocation before owner-verifiable controls."""
    from prop_firm.starter30_live import require_release

    require_release()
    if (
        getattr(settings, "MPW_MOJPROP_PREINVOICE_TRANSACTIONAL_EMAIL_APPROVED", False) is not True
        or getattr(settings, "MPW_MOJPROP_BUYER_SHARED_RATE_LIMIT_VERIFIED", False) is not True
        or getattr(settings, "SESSION_COOKIE_SECURE", False) is not True
        or getattr(settings, "CSRF_COOKIE_SECURE", False) is not True
    ):
        raise CheckoutEmailUnavailable(
            "email verification and shared anti-abuse are not yet approved"
        )


def request_checkout_email_code(email: str) -> str:
    """One identity-bound OTP per 60s; <=3 per 15m, across browser workers.

    Requires a verified global WAF/shared anti-abuse prerequisite before any
    public rollout. No receiving-address allocation occurs in this operation.
    """
    require_email_verification_release()
    normalized = normalize_email(email)
    identity_id = register_identity(normalized)
    now = timezone.now()
    with transaction.atomic(using=MOJPROP_DB_ALIAS):
        identity = (
            PropSimulationIdentity.objects.using(MOJPROP_DB_ALIAS)
            .select_for_update().get(pk=identity_id)
        )
        if identity.status == PropSimulationIdentity.Status.BLOCKED:
            raise CheckoutEmailUnavailable("email identity is unavailable")
        since = now - timedelta(minutes=15)
        scoped = (
            PropSimulationLoginChallenge.objects.using(MOJPROP_DB_ALIAS)
            .filter(
                identity_id=identity.pk,
                purpose=_PURPOSE,
                created_at__gte=since,
            )
        )
        count = scoped.count()
        last = scoped.order_by("-created_at").values_list("created_at", flat=True).first()
        if count >= 3 or (last is not None and last > now - timedelta(seconds=60)):
            raise CheckoutEmailUnavailable("please try requesting a code later")
        issued = issue_login_challenge(identity.pk, purpose=_PURPOSE)
    # Only after the durable anti-abuse decision and a separate owner-approved
    # transactional email flag may this requested email be sent.
    try:
        sent = send_mail(
            "Your requested Moj Prop Starter30 email verification",
            "Your one-time Starter30 checkout verification code is: "
            + issued.code
            + "\nIt expires shortly. If you did not request this, ignore this message. "
            "Never share your wallet seed or send funds to an unverified address.",
            None,
            [normalized],
            fail_silently=False,
        )
    except Exception as exc:
        raise CheckoutEmailUnavailable("verification email could not be delivered") from exc
    if sent != 1:
        raise CheckoutEmailUnavailable("verification email could not be delivered")
    return issued.challenge_ref


def consume_checkout_email_code(challenge_ref: str, code: str) -> str:
    """Exchange verified mailbox possession for a signed 15-minute capability."""
    require_email_verification_release()
    try:
        identity_id = consume_login_challenge(
            challenge_ref, code, expected_purpose=_PURPOSE
        )
    except IdentityAdapterClosed as exc:
        raise CheckoutEmailUnavailable("invalid or expired email code") from exc
    identity = (
        PropSimulationIdentity.objects.using(MOJPROP_DB_ALIAS)
        .get(pk=identity_id)
    )
    if identity.status == PropSimulationIdentity.Status.BLOCKED:
        raise CheckoutEmailUnavailable("email identity is unavailable")
    payload = {
        "v": 1,
        "id": identity.pk,
        "email_digest": identity.email_digest,
        "scope": "starter30-single-invoice",
    }
    return signing.dumps(payload, salt=_SALT, compress=False)


def verify_checkout_email_proof(email: str, proof: str) -> int:
    """Fail closed on an unsigned/expired/cross-email bearer proof."""
    require_email_verification_release()
    if type(proof) is not str or not proof or len(proof) > 2048:
        raise CheckoutEmailUnavailable("verify your email before creating an invoice")
    try:
        payload = signing.loads(
            proof, salt=_SALT, max_age=_MAX_PROOF_AGE_SECONDS
        )
    except (signing.BadSignature, signing.SignatureExpired, ValueError) as exc:
        raise CheckoutEmailUnavailable("email verification has expired") from exc
    normalized = normalize_email(email)
    _subject_key, expected_email_digest = _identity_keys(normalized)
    if (
        type(payload) is not dict
        or payload.get("v") != 1
        or payload.get("scope") != "starter30-single-invoice"
        or type(payload.get("id")) is not int
        or payload["id"] <= 0
        or type(payload.get("email_digest")) is not str
        or not hmac.compare_digest(payload["email_digest"], expected_email_digest)
    ):
        raise CheckoutEmailUnavailable("verified email does not match this invoice")
    return payload["id"]
