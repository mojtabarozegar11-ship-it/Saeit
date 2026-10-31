"""Strict offline verifier for short-lived PHP→Django office SSO assertions.

This is only the token contract. Production must keep SSO disabled until a
database-backed one-time nonce consumer, reviewed user/unit mapping and OTP
step-up are integrated. Never place the token in a URL.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import re
import time
from collections.abc import Callable

ISSUER = "zomorod-business-php"
AUDIENCE = "zomorod-company-office"
ALLOWED_ROLES = frozenset({"admin", "accountant", "manager"})
_FIELDS = frozenset({"iss", "aud", "iat", "exp", "nonce", "uid", "role"})
_B64 = re.compile(r"^[A-Za-z0-9_-]+$")


class SSOTicketError(ValueError):
    """Untrusted SSO assertion failed validation (never include its contents)."""


def _base64url_decode(value: str, limit: int) -> bytes:
    if not isinstance(value, str) or not 1 <= len(value) <= limit or not _B64.fullmatch(value):
        raise SSOTicketError("malformed assertion encoding")
    try:
        raw = base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
    except (ValueError, base64.binascii.Error) as exc:
        raise SSOTicketError("malformed assertion encoding") from exc
    if base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii") != value:
        raise SSOTicketError("non-canonical assertion encoding")
    return raw


def _unique_pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result = {}
    for key, value in pairs:
        if key in result:
            raise SSOTicketError("duplicate assertion key")
        result[key] = value
    return result


def verify_ticket(
    ticket: str,
    secret: bytes,
    *,
    consume_nonce: Callable[[str, int], bool],
    now: int | None = None,
) -> dict[str, object]:
    """Verify and atomically consume the assertion.

    consume_nonce MUST insert SHA256(nonce) into a persistent database
    table with a unique constraint and return False on uniqueness collision.
    In-memory sets/caches are not sufficient across Passenger workers.
    """
    if not isinstance(secret, bytes) or len(secret) < 32:
        raise SSOTicketError("server key unavailable")
    if not callable(consume_nonce):
        raise SSOTicketError("persistent nonce consumer required")
    if not isinstance(ticket, str) or len(ticket) > 1024:
        raise SSOTicketError("malformed assertion")
    parts = ticket.split(".")
    if len(parts) != 3 or parts[0] != "v1":
        raise SSOTicketError("unsupported assertion version")
    payload_b64, sig_b64 = parts[1:]
    raw = _base64url_decode(payload_b64, 768)
    signature = _base64url_decode(sig_b64, 64)
    if len(signature) != 32:
        raise SSOTicketError("invalid signature length")
    expected = hmac.new(secret, ("v1." + payload_b64).encode("ascii"), hashlib.sha256).digest()
    if not hmac.compare_digest(expected, signature):
        raise SSOTicketError("invalid signature")
    try:
        claims = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_pairs)
    except (ValueError, UnicodeError) as exc:
        raise SSOTicketError("invalid assertion body") from exc
    if not isinstance(claims, dict) or frozenset(claims) != _FIELDS:
        raise SSOTicketError("invalid assertion claims")
    if claims["iss"] != ISSUER or claims["aud"] != AUDIENCE:
        raise SSOTicketError("wrong issuer or audience")
    if claims["role"] not in ALLOWED_ROLES or type(claims["uid"]) is not int or claims["uid"] < 1:
        raise SSOTicketError("invalid identity or role")
    issued, expiry = claims["iat"], claims["exp"]
    if type(issued) is not int or type(expiry) is not int:
        raise SSOTicketError("invalid assertion timestamps")
    timestamp = int(time.time()) if now is None else now
    if type(timestamp) is not int or issued > timestamp + 5 or expiry <= timestamp or not 0 < expiry - issued <= 30:
        raise SSOTicketError("expired or future assertion")
    nonce = claims["nonce"]
    nonce_raw = _base64url_decode(nonce, 24)
    if len(nonce_raw) != 16:
        raise SSOTicketError("invalid assertion nonce")
    nonce_digest = hashlib.sha256(nonce_raw).hexdigest()
    if not consume_nonce(nonce_digest, expiry):
        raise SSOTicketError("assertion already used")
    return {"uid": claims["uid"], "role": claims["role"], "iat": issued, "exp": expiry}
