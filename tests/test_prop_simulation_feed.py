import unittest
from decimal import Decimal as D

from prop_firm.simulation_engine import MarketQuote
from prop_firm.simulation_feed import FeedAttestation, FeedBoundary, QuoteEnvelope


def quote(seq=1, timestamp="2026-11-19T00:00:00Z"):
    return MarketQuote("EURUSD", D("100"), D("101"), timestamp, seq)


def envelope(seq=1, *, previous=None, signature=True, license=True,
             timestamp="2026-11-19T00:00:00Z"):
    # Digest is filled after constructing the envelope in the helper.
    att = FeedAttestation(
        provider_id="licensed-provider",
        license_reference="lic-2026",
        symbols=("EURUSD",),
        issued_at="2026-11-18T00:00:00Z",
        expires_at="2026-11-20T00:00:00Z",
        payload_digest="placeholder",
        signature_verified=signature,
        license_verified=license,
    )
    initial = QuoteEnvelope(quote(seq, timestamp), att, previous)
    att = FeedAttestation(
        provider_id=att.provider_id,
        license_reference=att.license_reference,
        symbols=att.symbols,
        issued_at=att.issued_at,
        expires_at=att.expires_at,
        payload_digest=initial.envelope_digest,
        signature_verified=signature,
        license_verified=license,
    )
    return QuoteEnvelope(initial.quote, att, previous)


class FeedBoundaryTests(unittest.TestCase):
    def test_valid_chain_accepts(self):
        boundary = FeedBoundary()
        first = envelope()
        digest = boundary.accept(first, now="2026-11-19T01:00:00Z")
        self.assertEqual(digest, first.envelope_digest)
        second = envelope(2, previous=digest)
        self.assertEqual(boundary.accept(second, now="2026-11-19T01:01:00Z"),
                         second.envelope_digest)

    def test_signature_is_required(self):
        with self.assertRaisesRegex(ValueError, "signature"):
            FeedBoundary().accept(envelope(signature=False),
                                   now="2026-11-19T01:00:00Z")

    def test_license_is_required(self):
        with self.assertRaisesRegex(ValueError, "license"):
            FeedBoundary().accept(envelope(license=False),
                                   now="2026-11-19T01:00:00Z")

    def test_sequence_must_increase(self):
        boundary = FeedBoundary()
        first = envelope()
        digest = boundary.accept(first, now="2026-11-19T01:00:00Z")
        with self.assertRaisesRegex(ValueError, "monotonic"):
            boundary.accept(envelope(1, previous=digest),
                            now="2026-11-19T01:01:00Z")

    def test_chain_break_rejected(self):
        boundary = FeedBoundary()
        first = envelope()
        boundary.accept(first, now="2026-11-19T01:00:00Z")
        with self.assertRaisesRegex(ValueError, "chain"):
            boundary.accept(envelope(2, previous="wrong"),
                            now="2026-11-19T01:01:00Z")

    def test_expired_attestation_rejected(self):
        att = FeedAttestation(
            provider_id="p", license_reference="l", symbols=("EURUSD",),
            issued_at="2026-11-18T00:00:00Z",
            expires_at="2026-11-19T00:00:00Z",
            payload_digest="x", signature_verified=True, license_verified=True,
        )
        env = QuoteEnvelope(quote(), att)
        with self.assertRaisesRegex(ValueError, "time"):
            FeedBoundary().accept(env, now="2026-11-19T01:00:00Z")

    def test_symbol_scope_rejected(self):
        boundary = FeedBoundary()
        att = FeedAttestation(
            provider_id="p", license_reference="l", symbols=("XAUUSD",),
            issued_at="2026-11-18T00:00:00Z",
            expires_at="2026-11-20T00:00:00Z",
            payload_digest="x", signature_verified=True, license_verified=True,
        )
        env = QuoteEnvelope(quote(), att)
        with self.assertRaisesRegex(ValueError, "scope"):
            boundary.accept(env, now="2026-11-19T01:00:00Z")

    def test_payload_tampering_rejected(self):
        boundary = FeedBoundary()
        valid = envelope()
        tampered = QuoteEnvelope(
            MarketQuote("EURUSD", D("100"), D("102"),
                        valid.quote.timestamp, valid.quote.sequence),
            valid.attestation,
            valid.previous_envelope_digest,
        )
        with self.assertRaisesRegex(ValueError, "digest"):
            boundary.accept(tampered, now="2026-11-19T01:00:00Z")

    def test_missing_chain_anchor_rejected_after_first(self):
        boundary = FeedBoundary()
        first = envelope()
        boundary.accept(first, now="2026-11-19T01:00:00Z")
        with self.assertRaisesRegex(ValueError, "chain"):
            boundary.accept(envelope(2), now="2026-11-19T01:01:00Z")


if __name__ == "__main__":
    unittest.main()
