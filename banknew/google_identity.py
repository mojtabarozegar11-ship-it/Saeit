"""MOJ Pay server-side Google identity verification; NO banking authorization.

Call only after framework CSRF defenses, with a nonce previously generated and
stored in the trusted server session, then consume that nonce exactly once.
Identity must be linked by Google's stable sub; never auto-link by email.
This module does not create a session, perform KYC, or authorize fund movement.
"""
from __future__ import annotations

import hmac
import re
import secrets
import time
from dataclasses import dataclass


_CLIENT_ID = re.compile(r"[A-Za-z0-9-]{6,256}\.apps\.googleusercontent\.com\Z")
_NONCE = re.compile(r"[A-Za-z0-9_-]{16,128}\Z")
_SUBJECT = re.compile(r"[A-Za-z0-9_-]{4,255}\Z")
_JWT = re.compile(r"[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\Z")
_ALLOWED_ISSUERS = frozenset({"accounts.google.com", "https://accounts.google.com"})


class GoogleIdentityError(ValueError):
    """Google sign-in refused; do not expose internal verifier or token details."""


class GoogleIdentityUnavailable(GoogleIdentityError):
    """The server is not configured for Google identity verification."""


@dataclass(frozen=True)
class GooglePrincipal:
    subject: str
    email: str
    hosted_domain: str | None
    issued_at: int
    expires_at: int

    @property
    def financial_kyc_verified(self) -> bool:
        """Google sign-in is never proof of regulatory customer identity."""
        return False


def generate_server_nonce() -> str:
    """Create a high-entropy nonce; caller must bind it to a one-use session."""
    return secrets.token_urlsafe(32)


def _google_verify(credential: str, client_id: str) -> dict:
    """Official Google-auth library validates signature, audience and expiry."""
    from google.auth.transport import requests as google_requests
    from google.oauth2 import id_token as google_id_token

    return google_id_token.verify_oauth2_token(
        credential, google_requests.Request(), client_id
    )


def verify_google_credential(
    credential: str,
    *,
    client_id: str,
    expected_nonce: str,
) -> GooglePrincipal:
    """Fail-closed OIDC verification for an externally CSRF-checked HTTPS POST.

    Do not pass a nonce received only from the same untrusted POST; it must
    originate from a server-side session and be consumed after a successful
    login. The returned principal grants no financial or custody privileges.
    """
    if not isinstance(client_id, str) or not _CLIENT_ID.fullmatch(client_id):
        raise GoogleIdentityUnavailable("Google OAuth client is not configured.")
    if not isinstance(expected_nonce, str) or not _NONCE.fullmatch(expected_nonce):
        raise GoogleIdentityError("Server login state is unavailable.")
    if (not isinstance(credential, str) or len(credential) > 16384 or
            not _JWT.fullmatch(credential)):
        raise GoogleIdentityError("Invalid Google credential.")
    try:
        payload = _google_verify(credential, client_id)
    except ImportError as exc:
        raise GoogleIdentityUnavailable("Google verification dependency missing.") from exc
    except Exception as exc:
        raise GoogleIdentityError("Google credential verification failed.") from exc
    if not isinstance(payload, dict):
        raise GoogleIdentityError("Invalid identity claims.")
    subject = payload.get("sub")
    issuer = payload.get("iss")
    audience = payload.get("aud")
    email = payload.get("email")
    is_verified = payload.get("email_verified")
    nonce = payload.get("nonce")
    issued_at = payload.get("iat")
    expires_at = payload.get("exp")
    hosted_domain = payload.get("hd")
    authorized_party = payload.get("azp")
    now = int(time.time())

    if (not isinstance(subject, str) or
            not _SUBJECT.fullmatch(subject)):
        raise GoogleIdentityError("Invalid identity subject.")
    if issuer not in _ALLOWED_ISSUERS or audience != client_id:
        raise GoogleIdentityError("Identity issuer or audience mismatch.")
    if authorized_party is not None and authorized_party != client_id:
        raise GoogleIdentityError("Unauthorized identity client.")
    if not isinstance(nonce, str) or not hmac.compare_digest(
        nonce, expected_nonce
    ):
        raise GoogleIdentityError("Identity replay protection failed.")
    if (isinstance(issued_at, bool) or not isinstance(issued_at, int) or
            isinstance(expires_at, bool) or not isinstance(expires_at, int) or
            issued_at > now + 120 or expires_at <= now or
            expires_at <= issued_at):
        raise GoogleIdentityError("Expired or invalid identity time window.")
    if (not isinstance(email, str) or not (3 <= len(email) <= 320) or
            email != email.strip() or email.count("@") != 1 or
            any(ord(ch) < 33 or ord(ch) == 127 for ch in email)):
        raise GoogleIdentityError("Invalid identity email.")
    if is_verified is not True:
        raise GoogleIdentityError("Google email is not verified.")
    if hosted_domain is not None and (
        not isinstance(hosted_domain, str) or not (1 <= len(hosted_domain) <= 253)
        or any(ord(ch) < 33 or ord(ch) >= 127 for ch in hosted_domain)
    ):
        raise GoogleIdentityError("Invalid hosted-domain claim.")
    return GooglePrincipal(
        subject=subject,
        email=email,
        hosted_domain=hosted_domain,
        issued_at=issued_at,
        expires_at=expires_at,
    )
