"""Commercial contract/version and quote boundary regression tests."""
from dataclasses import replace
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from django.core.exceptions import ValidationError
from django.test import SimpleTestCase, override_settings
from prop_firm.simulation_invoice_contract import (
    SimulationInvoiceContract, CONTRACT_VERSION, COMMERCIAL_CONTRACT_VERSION,
)
from prop_firm.simulation_feed import (
    FeedAttestation, QuoteEnvelope, verified_commercial_quote, commercial_feed_configured,
)
from prop_firm.simulation_engine import MarketQuote

def verified(envelope):
    return True  # Isolated test verifier only; not configured in production.

@override_settings(
    MPW_SIMULATION_SIMULATION_DATA_RIGHTS_VERIFIED=True,
    MPW_SIMULATION_LICENSED_PROVIDER_ID="reviewed-provider",
    MPW_SIMULATION_LICENSE_REFERENCE="reviewed-license",
    MPW_SIMULATION_QUOTE_ATTESTATION_VERIFIER=verified,
    MPW_SIMULATION_ALLOWED_SYMBOLS=("EURUSD",),
    MPW_SIMULATION_QUOTE_MAX_AGE_SECONDS=15,
)
class CommercialSimulationBoundaryTests(SimpleTestCase):
    now = datetime(2026, 11, 19, 12, tzinfo=timezone.utc)

    def offer(self, version):
        return SimulationInvoiceContract(
            "T9yD14Nj9j7xAB4dbGeiX9h8unkKHxuWwb", "a"*64, version=version)

    def envelope(self, age=1, provider="reviewed-provider"):
        quote = MarketQuote("EURUSD", Decimal("100"), Decimal("101"),
                            (self.now-timedelta(seconds=age)).isoformat(), 1)
        att = FeedAttestation(provider, "reviewed-license", ("EURUSD",),
                             self.now.isoformat(), (self.now+timedelta(seconds=15)).isoformat(),
                             "placeholder", True, True)
        initial = QuoteEnvelope(quote, att)
        return replace(initial, attestation=replace(att, payload_digest=initial.envelope_digest))

    def test_contract_versions_keep_distinct_data_modes_and_digests(self):
        legacy = self.offer(CONTRACT_VERSION)
        commercial = self.offer(COMMERCIAL_CONTRACT_VERSION)
        self.assertEqual(legacy.snapshot()["data_mode"], "synthetic_replay")
        self.assertEqual(commercial.snapshot()["data_mode"], "licensed_market_data")
        self.assertNotEqual(legacy.digest(), commercial.digest())
        self.assertEqual(legacy.snapshot()["amount_sun"], commercial.snapshot()["amount_sun"])

    def test_fresh_attested_quote(self):
        envelope = self.envelope()
        quote, evidence = verified_commercial_quote(envelope, symbol="EURUSD", now=self.now)
        self.assertEqual(quote, envelope.quote)
        self.assertEqual(evidence["envelope_digest"], envelope.envelope_digest)

    def test_stale_quote(self):
        with self.assertRaises(ValidationError):
            verified_commercial_quote(self.envelope(age=16), symbol="EURUSD", now=self.now)

    def test_future_quote(self):
        with self.assertRaises(ValidationError):
            verified_commercial_quote(self.envelope(age=-1), symbol="EURUSD", now=self.now)

    def test_unapproved_provider(self):
        with self.assertRaises(ValidationError):
            verified_commercial_quote(self.envelope(provider="unknown"), symbol="EURUSD", now=self.now)

    def test_plain_quote_not_proof(self):
        with self.assertRaises(ValidationError):
            verified_commercial_quote(self.envelope().quote, symbol="EURUSD", now=self.now)

    @override_settings(MPW_SIMULATION_QUOTE_ATTESTATION_VERIFIER=None)
    def test_missing_verifier_blocks_readiness(self):
        self.assertFalse(commercial_feed_configured())
        with self.assertRaises(ValidationError):
            verified_commercial_quote(self.envelope(), symbol="EURUSD", now=self.now)

    @override_settings(MPW_SIMULATION_QUOTE_ATTESTATION_VERIFIER=lambda envelope: False)
    def test_failed_external_verification_blocks_execution(self):
        with self.assertRaises(ValidationError):
            verified_commercial_quote(self.envelope(), symbol="EURUSD", now=self.now)
