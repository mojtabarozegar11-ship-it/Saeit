"""Fail-closed boundary for licensed, authenticated simulation quotes.

The boundary does not fetch market data. A separately approved adapter must
supply a quote plus an independently verified attestation. Until then, no
quote is accepted as authoritative.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from typing import Optional

from .simulation_engine import MarketQuote


@dataclass(frozen=True)
class FeedAttestation:
    provider_id: str
    license_reference: str
    symbols: tuple[str, ...]
    issued_at: str
    expires_at: str
    payload_digest: str
    signature_verified: bool = False
    license_verified: bool = False

    def __post_init__(self):
        if not self.provider_id or not self.license_reference:
            raise ValueError("provider and license reference are required")
        if not self.symbols:
            raise ValueError("at least one licensed symbol is required")
        if not self.issued_at or not self.expires_at or not self.payload_digest:
            raise ValueError("attestation timestamps and digest are required")


@dataclass(frozen=True)
class QuoteEnvelope:
    quote: MarketQuote
    attestation: FeedAttestation
    previous_envelope_digest: Optional[str] = None

    def canonical_payload(self) -> bytes:
        payload = {
            "quote": {
                "symbol": self.quote.symbol,
                "bid": str(self.quote.bid),
                "ask": str(self.quote.ask),
                "timestamp": self.quote.timestamp,
                "sequence": self.quote.sequence,
            },
            "attestation": {
                "provider_id": self.attestation.provider_id,
                "license_reference": self.attestation.license_reference,
                "symbols": list(self.attestation.symbols),
                "issued_at": self.attestation.issued_at,
                "expires_at": self.attestation.expires_at,
                # The signed digest is carried outside the canonical payload
                # to avoid a self-referential hash.
            },
            "previous_envelope_digest": self.previous_envelope_digest,
        }
        return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()

    @property
    def envelope_digest(self) -> str:
        return hashlib.sha256(self.canonical_payload()).hexdigest()


class FeedBoundary:
    """Accept only fresh, licensed and independently verified quote envelopes."""

    def __init__(self):
        self.last_sequence = -1
        self.last_envelope_digest: Optional[str] = None

    @staticmethod
    def _parse(value: str) -> datetime:
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError("timestamps must be ISO-8601") from exc
        if parsed.tzinfo is None:
            raise ValueError("timestamps must include timezone")
        return parsed.astimezone(timezone.utc)

    def accept(self, envelope: QuoteEnvelope, *, now: str) -> str:
        if not isinstance(envelope, QuoteEnvelope):
            raise TypeError("QuoteEnvelope required")
        current = self._parse(now)
        issued = self._parse(envelope.attestation.issued_at)
        expires = self._parse(envelope.attestation.expires_at)
        quoted = self._parse(envelope.quote.timestamp)
        if not envelope.attestation.signature_verified:
            raise ValueError("feed_signature_not_verified")
        if not envelope.attestation.license_verified:
            raise ValueError("market_data_license_not_verified")
        if envelope.quote.symbol not in envelope.attestation.symbols:
            raise ValueError("symbol_outside_license_scope")
        if issued > current or expires <= current or quoted > current:
            raise ValueError("feed_attestation_time_invalid")
        if envelope.quote.sequence <= self.last_sequence:
            raise ValueError("feed_sequence_not_monotonic")
        if self.last_envelope_digest != envelope.previous_envelope_digest:
            raise ValueError("feed_chain_break")
        actual = envelope.envelope_digest
        if envelope.attestation.payload_digest != actual:
            raise ValueError("feed_payload_digest_mismatch")
        self.last_sequence = envelope.quote.sequence
        self.last_envelope_digest = actual
        return actual

    def reset(self):
        self.last_sequence = -1
        self.last_envelope_digest = None


def commercial_feed_configured():
    """A server-owned verifier and reviewed provider/license identity are mandatory."""
    from django.conf import settings
    provider = getattr(settings, "MPW_SIMULATION_LICENSED_PROVIDER_ID", "")
    license_ref = getattr(settings, "MPW_SIMULATION_LICENSE_REFERENCE", "")
    age = getattr(settings, "MPW_SIMULATION_QUOTE_MAX_AGE_SECONDS", 15)
    return (getattr(settings, "MPW_SIMULATION_SIMULATION_DATA_RIGHTS_VERIFIED", False) is True
            and callable(getattr(settings, "MPW_SIMULATION_QUOTE_ATTESTATION_VERIFIER", None))
            and isinstance(provider, str) and bool(provider.strip())
            and isinstance(license_ref, str) and bool(license_ref.strip())
            and type(age) is int and 1 <= age <= 60)


def verified_commercial_quote(envelope, *, symbol, now):
    """Validate an attested live quote without modifying historical replay."""
    from django.conf import settings
    from django.core.exceptions import ValidationError
    if not commercial_feed_configured() or not isinstance(envelope, QuoteEnvelope):
        raise ValidationError("Licensed quote envelope required")
    att = envelope.attestation
    try:
        if (att.provider_id != settings.MPW_SIMULATION_LICENSED_PROVIDER_ID
                or att.license_reference != settings.MPW_SIMULATION_LICENSE_REFERENCE
                or envelope.quote.symbol != symbol
                or symbol not in getattr(settings, "MPW_SIMULATION_ALLOWED_SYMBOLS", ())
                or att.signature_verified is not True or att.license_verified is not True):
            raise ValueError("Wrong quote provenance")
        current = FeedBoundary._parse(now.isoformat())
        quoted = FeedBoundary._parse(envelope.quote.timestamp)
        issued = FeedBoundary._parse(att.issued_at)
        expires = FeedBoundary._parse(att.expires_at)
        age = (current - quoted).total_seconds()
        if (not 0 <= age <= getattr(settings, "MPW_SIMULATION_QUOTE_MAX_AGE_SECONDS", 15)
                or not quoted <= issued <= current < expires
                or symbol not in att.symbols
                or att.payload_digest != envelope.envelope_digest
                or settings.MPW_SIMULATION_QUOTE_ATTESTATION_VERIFIER(envelope) is not True):
            raise ValueError("Unverified or stale quote")
    except Exception as exc:
        raise ValidationError("Licensed quote verification failed") from exc
    return envelope.quote, {"provider_id": att.provider_id, "license_reference": att.license_reference,
                           "envelope_digest": envelope.envelope_digest}
