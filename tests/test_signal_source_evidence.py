"""Signal provenance: an untrusted 'verified' boolean cannot impersonate a broker."""
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import hmac

from django.test import SimpleTestCase

from core.signal_source_evidence import (
    authenticate_signal_source, canonical_signal_bytes,
)

SECRET = b"independent-config-only-source-hmac-32-bytes-minimum-example"
NOW = datetime(2026, 11, 14, 12, 0, tzinfo=timezone.utc)


class SignedSignalSourceRegressionTests(SimpleTestCase):
    def setUp(self):
        self.record = {
            "event_id": "broker:20261114:123",
            "symbol": "XAUUSD", "side": "buy",
            "created_at": NOW - timedelta(minutes=5),
            "entry": "4000", "stop_loss": "3980",
            "take_profit": "4040", "verified_source": True,
        }
        self.trusted = {("saman", "broker_a"): SECRET}

    def sign(self, *, record=None, brand="saman", source_id="broker_a", secret=SECRET):
        payload = canonical_signal_bytes(
            record=self.record if record is None else record,
            brand=brand, source_id=source_id,
        )
        return hmac.new(secret, payload, sha256).hexdigest()

    def assess(self, **changes):
        kw = {
            "record": self.record, "brand": "saman",
            "source_id": "broker_a", "signature": self.sign(),
            "trusted_source_keys": self.trusted, "seen_event_ids": set(),
            "now": NOW,
        }
        kw.update(changes)
        return authenticate_signal_source(**kw)

    def test_authenticated_source_is_still_not_performance_or_payment(self):
        r = self.assess()
        self.assertTrue(r.source_authenticated)
        self.assertFalse(r.performance_independently_audited)
        self.assertFalse(r.subscription_enabled)
        self.assertFalse(r.signal_delivered)

    def test_verified_source_produces_stable_hash_not_verified_profit(self):
        one, two = self.assess(), self.assess()
        self.assertTrue(one.source_authenticated)
        self.assertEqual(one.audit_digest_sha256, two.audit_digest_sha256)
        self.assertEqual(len(one.audit_digest_sha256), 64)
        self.assertFalse(one.performance_independently_audited)
        self.assertFalse(one.signal_delivered)

    def test_denied_provider_has_no_audit_credential(self):
        decision = self.assess(signature="0" * 64)
        self.assertFalse(decision.source_authenticated)
        self.assertIsNone(decision.audit_digest_sha256)

    def test_unsigned_user_verified_boolean_is_not_evidence(self):
        self.assertFalse(self.assess(signature="0" * 64).source_authenticated)

    def test_changed_entry_blocked(self):
        self.assertFalse(self.assess(record={**self.record, "entry": "4010"}).source_authenticated)

    def test_changed_stop_loss_blocked(self):
        self.assertFalse(self.assess(record={**self.record, "stop_loss": "3990"}).source_authenticated)

    def test_changed_take_profit_blocked(self):
        self.assertFalse(self.assess(record={**self.record, "take_profit": "4060"}).source_authenticated)

    def test_changed_event_id_blocked(self):
        self.assertFalse(self.assess(record={**self.record, "event_id": "broker:20261114:124"}).source_authenticated)

    def test_changed_symbol_blocked(self):
        self.assertFalse(self.assess(record={**self.record, "symbol": "EURUSD"}).source_authenticated)

    def test_changed_created_at_blocked(self):
        self.assertFalse(self.assess(record={
            **self.record, "created_at": NOW - timedelta(minutes=6),
        }).source_authenticated)

    def test_cross_brand_signature_cannot_reuse(self):
        trusted = {**self.trusted, ("zahra", "broker_a"): SECRET}
        r = self.assess(brand="zahra", trusted_source_keys=trusted)
        self.assertFalse(r.source_authenticated)

    def test_source_id_is_signed_and_restricted(self):
        trusted = {**self.trusted, ("saman", "broker_b"): SECRET}
        self.assertFalse(self.assess(source_id="broker_b", trusted_source_keys=trusted).source_authenticated)
        self.assertFalse(self.assess(source_id="../bad").source_authenticated)

    def test_explicitly_missing_trust_registry_blocked(self):
        self.assertFalse(self.assess(trusted_source_keys=None).source_authenticated)
        self.assertFalse(self.assess(trusted_source_keys={}).source_authenticated)

    def test_secret_rotations_invalidate_old_signatures(self):
        registry = {("saman", "broker_a"): b"rotated-secret-material-at-least-thirty-two-bytes"}
        self.assertFalse(self.assess(trusted_source_keys=registry).source_authenticated)

    def test_short_or_text_secret_not_accepted(self):
        self.assertFalse(self.assess(trusted_source_keys={("saman","broker_a"): b"tiny"}).source_authenticated)
        self.assertFalse(self.assess(trusted_source_keys={("saman","broker_a"): "str-secret-" * 4}).source_authenticated)

    def test_expired_signal_not_usable_as_fresh_signal(self):
        late = NOW + timedelta(days=2)
        self.assertEqual(self.assess(now=late).reason, "signal_expired")

    def test_future_dated_signal_not_accepted(self):
        early = NOW - timedelta(hours=1)
        self.assertEqual(self.assess(now=early).reason, "signal_from_future")

    def test_exact_replay_event_id_denied(self):
        self.assertEqual(self.assess(seen_event_ids={self.record["event_id"]}).reason, "signal_event_replayed")

    def test_missing_durable_replay_ledger_denied(self):
        self.assertFalse(self.assess(seen_event_ids=None).source_authenticated)
        self.assertFalse(self.assess(seen_event_ids="").source_authenticated)

    def test_naive_or_non_utc_clock_denied(self):
        self.assertFalse(self.assess(now=datetime(2026,11,14,12)).source_authenticated)
        self.assertFalse(self.assess(now=NOW.astimezone(timezone(timedelta(hours=3)))).source_authenticated)

    def test_invalid_age_config_denied(self):
        for v in (-1, 0, 604801, True, "3600"):
            with self.subTest(value=v):
                self.assertFalse(self.assess(max_age_seconds=v).source_authenticated)

    def test_invalid_signature_formats_denied(self):
        for v in (None, "", "a"*63, "A"*64, "0"*65):
            with self.subTest(value=v):
                self.assertFalse(self.assess(signature=v).source_authenticated)

    def test_false_source_verified_flag_denied(self):
        self.assertFalse(self.assess(record={**self.record, "verified_source": False}).source_authenticated)

    def test_unbounded_or_exponential_signal_prices_fail_before_authentication(self):
        for value in ("1e1000000", "0." + "1"*50000, "۹۹۹", "1"*19):
            with self.subTest(length=len(value)):
                with self.assertRaises(ValueError):
                    self.sign(record={**self.record, "entry": value})
                outcome = self.assess(record={**self.record, "entry": value})
                self.assertFalse(outcome.source_authenticated)

    def test_valid_eight_decimal_price_precision_still_authenticates(self):
        prices = {**self.record, "entry": "0.00000120",
                  "stop_loss": "0.00000119", "take_profit": "0.00000121"}
        result = self.assess(record=prices, signature=self.sign(record=prices))
        self.assertTrue(result.source_authenticated)

    def test_invalid_record_shape_denied(self):
        self.assertFalse(self.assess(record={}).source_authenticated)
        self.assertFalse(self.assess(record={**self.record, "profit_guaranteed": True}).source_authenticated)
