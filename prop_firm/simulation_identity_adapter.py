"""Private identity and one-time login adapter for the isolated MOJ PROP database.

This module is an internal boundary only. It does not create Django auth users,
send email, create invoices, verify settlement, or enable a public route.
Callers must configure a dedicated digest secret in the environment and must
pass the database alias explicitly through this adapter's fixed alias.
"""

from dataclasses import dataclass
from datetime import timedelta
import hashlib
import hmac
import re
import secrets

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from config.mojprop_db_router import MOJPROP_DB_ALIAS
from .models import (
    PropSimulationAccount,
    PropSimulationIdentity,
    PropSimulationLoginChallenge,
)


class IdentityAdapterClosed(RuntimeError):
    """Raised whenever identity/login work cannot pass the private gate."""


@dataclass(frozen=True)
class IssuedLoginChallenge:
    challenge_ref: str
    code: str
    expires_at: object


_EMAIL_RE = re.compile(r"[^@\s]{1,190}@[^@\s]{1,64}\Z")
_REF_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{7,127}\Z")
_ALLOWED_PURPOSES = frozenset(
    {
        PropSimulationLoginChallenge.Purpose.LOGIN,
        PropSimulationLoginChallenge.Purpose.RECOVERY,
    }
)


def _digest_secret() -> bytes:
    value = getattr(settings, "MPW_MOJPROP_IDENTITY_DIGEST_SECRET", "")
    if not isinstance(value, str) or len(value) < 32:
        raise IdentityAdapterClosed("dedicated identity digest secret is not configured")
    return value.encode("utf-8")


def normalize_email(raw_email: str) -> str:
    if not isinstance(raw_email, str):
        raise IdentityAdapterClosed("email must be text")
    value = raw_email.strip().casefold()
    if len(value) > 254 or _EMAIL_RE.fullmatch(value) is None:
        raise IdentityAdapterClosed("canonical email is required")
    return value


def _scoped_digest(secret: bytes, scope: str, value: str) -> str:
    payload = scope.encode("ascii") + b":" + value.encode("utf-8")
    return hmac.new(secret, payload, hashlib.sha256).hexdigest()


def _identity_keys(email: str) -> tuple[str, str]:
    secret = _digest_secret()
    return (
        _scoped_digest(secret, "subject", email),
        _scoped_digest(secret, "email", email),
    )


def _require_ref(value: str, label: str) -> str:
    if not isinstance(value, str) or _REF_RE.fullmatch(value) is None:
        raise IdentityAdapterClosed(f"bounded {label} is required")
    return value


def register_identity(raw_email: str) -> int:
    """Create or retrieve a pending identity without storing the email itself."""
    email = normalize_email(raw_email)
    subject_key, email_digest = _identity_keys(email)
    with transaction.atomic(using=MOJPROP_DB_ALIAS):
        identity, _created = (
            PropSimulationIdentity.objects.using(MOJPROP_DB_ALIAS).get_or_create(
                provider="email",
                subject_key=subject_key,
                defaults={
                    "email_digest": email_digest,
                    "status": PropSimulationIdentity.Status.PENDING,
                },
            )
        )
        if not hmac.compare_digest(identity.email_digest, email_digest):
            raise IdentityAdapterClosed("identity digest collision or tampering detected")
        if identity.status == PropSimulationIdentity.Status.BLOCKED:
            raise IdentityAdapterClosed("identity is blocked")
        return int(identity.pk)


def activate_identity(identity_id: int, *, verification_ref: str) -> None:
    """Activate an identity only from a private, externally verified boundary."""
    _require_ref(verification_ref, "verification reference")
    with transaction.atomic(using=MOJPROP_DB_ALIAS):
        identity = (
            PropSimulationIdentity.objects.using(MOJPROP_DB_ALIAS)
            .select_for_update()
            .get(pk=identity_id)
        )
        if identity.status == PropSimulationIdentity.Status.BLOCKED:
            raise IdentityAdapterClosed("identity is blocked")
        identity.status = PropSimulationIdentity.Status.ACTIVE
        identity.save(using=MOJPROP_DB_ALIAS, update_fields=["status", "updated_at"])


def issue_login_challenge(
    identity_id: int,
    *,
    purpose: str = PropSimulationLoginChallenge.Purpose.LOGIN,
    ttl_seconds: int | None = None,
    now=None,
    code: str | None = None,
) -> IssuedLoginChallenge:
    """Issue a one-time code; only its scoped digest is persisted."""
    if purpose not in _ALLOWED_PURPOSES:
        raise IdentityAdapterClosed("unsupported challenge purpose")
    if ttl_seconds is None:
        ttl_seconds = int(
            getattr(settings, "MPW_MOJPROP_LOGIN_CHALLENGE_TTL_SECONDS", 600)
        )
    if type(ttl_seconds) is not int or not 60 <= ttl_seconds <= 1800:
        raise IdentityAdapterClosed("challenge TTL is outside the private bounds")
    if code is None:
        code = secrets.token_hex(16)
    if not isinstance(code, str) or not 16 <= len(code) <= 128:
        raise IdentityAdapterClosed("challenge code is outside the private bounds")
    issued_at = now or timezone.now()
    challenge_ref = secrets.token_urlsafe(24)
    challenge_ref = re.sub(r"[^A-Za-z0-9._:-]", "", challenge_ref)
    challenge_ref = _require_ref(challenge_ref, "challenge reference")
    digest = _scoped_digest(
        _digest_secret(), "challenge", challenge_ref + ":" + code
    )
    expires_at = issued_at + timedelta(seconds=ttl_seconds)
    with transaction.atomic(using=MOJPROP_DB_ALIAS):
        identity = (
            PropSimulationIdentity.objects.using(MOJPROP_DB_ALIAS)
            .select_for_update()
            .get(pk=identity_id)
        )
        if identity.status != PropSimulationIdentity.Status.ACTIVE:
            raise IdentityAdapterClosed("active identity required")
        PropSimulationLoginChallenge.objects.using(MOJPROP_DB_ALIAS).create(
            identity_id=identity.pk,
            challenge_ref=challenge_ref,
            purpose=purpose,
            code_digest=digest,
            expires_at=expires_at,
        )
    return IssuedLoginChallenge(challenge_ref, code, expires_at)


def consume_login_challenge(
    challenge_ref: str,
    code: str,
    *,
    now=None,
    max_attempts: int | None = None,
) -> int:
    """Atomically consume a valid code and return only the isolated identity ID."""
    _require_ref(challenge_ref, "challenge reference")
    if not isinstance(code, str) or not code:
        raise IdentityAdapterClosed("challenge code is required")
    if max_attempts is None:
        max_attempts = int(getattr(settings, "MPW_MOJPROP_LOGIN_MAX_ATTEMPTS", 5))
    if type(max_attempts) is not int or not 1 <= max_attempts <= 10:
        raise IdentityAdapterClosed("maximum challenge attempts are outside the bounds")
    observed_at = now or timezone.now()
    with transaction.atomic(using=MOJPROP_DB_ALIAS):
        challenge = (
            PropSimulationLoginChallenge.objects.using(MOJPROP_DB_ALIAS)
            .select_for_update()
            .get(challenge_ref=challenge_ref)
        )
        if challenge.consumed_at is not None:
            raise IdentityAdapterClosed("challenge already consumed")
        if challenge.attempt_count >= max_attempts:
            raise IdentityAdapterClosed("challenge attempt limit reached")
        expected = _scoped_digest(
            _digest_secret(), "challenge", challenge_ref + ":" + code
        )
        if (
            observed_at >= challenge.expires_at
            or not hmac.compare_digest(challenge.code_digest, expected)
        ):
            # Commit the failed attempt before raising. Raising inside the
            # atomic block would roll back the increment and silently disable
            # the max-attempts lockout for this one-time challenge.
            challenge.attempt_count += 1
            challenge.save(
                using=MOJPROP_DB_ALIAS,
                update_fields=["attempt_count"],
            )
        else:
            challenge.consumed_at = observed_at
            challenge.save(using=MOJPROP_DB_ALIAS, update_fields=["consumed_at"])
            return int(challenge.identity_id)

    # The database lock and transaction have ended successfully. A wrong or
    # expired code must be rejected without undoing its persisted attempt.
    raise IdentityAdapterClosed("invalid or expired challenge")


def settled_accounts(identity_id: int) -> list[dict]:
    """Return simulation accounts only when the isolated invoice owner is settled."""
    rows = (
        PropSimulationAccount.objects.using(MOJPROP_DB_ALIAS)
        .filter(
            identity_id=identity_id,
            invoice_owner__identity_id=identity_id,
            invoice_owner__settlement_verified=True,
        )
        .values(
            "id",
            "account_ref",
            "kind",
            "status",
            "starting_capital_usd",
            "policy_version",
        )
    )
    return list(rows)
