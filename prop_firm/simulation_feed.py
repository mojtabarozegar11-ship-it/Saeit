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
from typing import Iterable, Optional

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
                "payload_digest": self.attestation.payload_digest,
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
