"""Offline authenticated signal provenance; never paid trading results."""
from datetime import datetime, timedelta, timezone
import unittest

from core.signal_history_evidence import (
    MAX_HISTORY_DAYS, SignalHistoryRejected, audit_history, source_digest,
    subscription_preflight, verify_source_integrity,
)

KEY = b"trusted-internal-feed-adapter-fixture-signing-key-2026"
NOW = datetime(2026, 11, 14, 18, 0, tzinfo=timezone.utc)


def signal(i=1, **changes):
    event = {
        "event_id": f"broker.20261114.{i}",
        "symbol": "XAUUSD",
        "side": "buy", "created_at": NOW - timedelta(minutes=60-i),
        "entry": "4000", "stop_loss": "3980", "take_profit": "4040",
        "verified_source": True,
    }
    event.update(changes)
    return event


def signed(record, source_id="source_main", brand="saman"):
    return {"record": record, "source_digest": source_digest(
        record, source_id=source_id, brand=brand, signing_key=KEY,
    )}


class SignalEvidenceTests(unittest.TestCase):
    def history(self, values=None, **changes):
        records = [signed(signal(i)) for i in (1, 2, 3)] if values is None else values
        return audit_history(records, source_id="source_main", brand="saman",
                             signing_key=KEY, now_utc=NOW, **changes)

    def test_three_ordered_source_signed_records_have_deterministic_digest(self):
        first = self.history()
        second = self.history()
        self.assertEqual(first.history_digest_sha256, second.history_digest_sha256)
        self.assertEqual(first.event_count, 3)
        self.assertTrue(first.integrity_verified_for_supplied_history)
        self.assertFalse(first.independent_execution_verified)
        self.assertFalse(first.customer_delivery_verified)
        self.assertFalse(first.subscription_authorized)
        self.assertFalse(first.checkout_enabled)

    def test_record_mutation_breaks_authenticated_source_integrity(self):
        record = signal()
        digest = source_digest(record, source_id="source_main", brand="saman", signing_key=KEY)
        for field, value in (
            ("entry", "4100"), ("stop_loss", "3995"),
            ("take_profit", "4200"), ("event_id", "broker.changed"),
        ):
            with self.subTest(field=field):
                tampered = {**record, field: value}
                self.assertFalse(verify_source_integrity(
                    tampered, source_id="source_main", brand="saman",
                    signing_key=KEY, digest=digest,
                ))

    def test_cross_brand_replay_cannot_be_authenticated_or_sold(self):
        item = signed(signal(), source_id="source_main", brand="saman")
        self.assertFalse(verify_source_integrity(
            item["record"], source_id="source_main", brand="maryam",
            signing_key=KEY, digest=item["source_digest"],
        ))
        with self.assertRaisesRegex(SignalHistoryRejected, "source_signature_mismatch"):
            audit_history([item], source_id="source_main", brand="maryam",
                          signing_key=KEY, now_utc=NOW)

    def test_unknown_brand_cannot_sign_historical_signal(self):
        with self.assertRaisesRegex(SignalHistoryRejected, "brand_not_registered"):
            signed(signal(), brand="unregistered_financial_brand")

    def test_wrong_signing_key_and_source_id_cannot_verify(self):
        item = signed(signal())
        self.assertFalse(verify_source_integrity(
            item["record"], source_id="another_source", brand="saman",
            signing_key=KEY, digest=item["source_digest"],
        ))
        self.assertFalse(verify_source_integrity(
            item["record"], source_id="source_main", brand="saman",
            signing_key=b"another-privileged-key-long-enough-to-pass-checks",
            digest=item["source_digest"],
        ))

    def test_blank_short_keys_cannot_authenticate(self):
        for key in (b"", b"short", "not-bytes", 123, None):
            with self.subTest(key=key), self.assertRaises(SignalHistoryRejected):
                source_digest(signal(), source_id="source_main", brand="saman", signing_key=key)

    def test_duplicate_ids_in_history_are_refused_even_if_each_signed(self):
        event = signal(1)
        with self.assertRaisesRegex(SignalHistoryRejected, "replayed_event_id"):
            self.history([signed(event), signed(event)])

    def test_duplicate_timestamp_and_out_of_order_records_are_rejected(self):
        first, second = signal(1), signal(2)
        equal = signal(2, created_at=first["created_at"])
        with self.assertRaisesRegex(SignalHistoryRejected, "nonmonotonic"):
            self.history([signed(first), signed(equal)])
        with self.assertRaisesRegex(SignalHistoryRejected, "nonmonotonic"):
            self.history([signed(second), signed(first)])

    def test_future_dated_signal_cannot_be_shown_as_historic_success(self):
        future = signal(1, created_at=NOW + timedelta(minutes=1))
        with self.assertRaisesRegex(SignalHistoryRejected, "future_dated_signal"):
            self.history([signed(future)])

    def test_stale_history_rejected_without_fake_current_performance(self):
        old = signal(1, created_at=NOW - timedelta(days=MAX_HISTORY_DAYS+1))
        with self.assertRaisesRegex(SignalHistoryRejected, "history_too_old"):
            self.history([signed(old)])

    def test_utc_source_date_required(self):
        naive = signal(1, created_at=datetime(2026, 11, 14, 17))
        with self.assertRaises(SignalHistoryRejected):
            signed(naive)

    def test_cannot_hide_unknown_fields_in_authenticated_feed(self):
        record = {**signal(), "profit_guaranteed": True}
        with self.assertRaises(SignalHistoryRejected):
            signed(record)

    def test_batch_limits_are_strict(self):
        for entries in ([], "not-list", [{}]*10001):
            with self.subTest(size=len(entries)), self.assertRaises(SignalHistoryRejected):
                self.history(entries)

    def test_unaudited_signal_history_does_not_enable_checkout(self):
        audit = self.history()
        result = subscription_preflight(
            history=audit, verified_order_source=True,
            timestamped_independent_execution_audit=False,
            risk_and_fee_disclosures_approved=True,
            jurisdiction_approved=True, subscriber_delivery_proven=True,
            refund_terms_approved=True, legal_merchant_ready=True,
        )
        self.assertFalse(result["eligible_for_owner_release_review"])
        self.assertIn("independent_execution_audit", result["missing"])
        self.assertFalse(result["checkout_enabled"])

    def test_truthy_approval_words_are_not_valid_release_evidence(self):
        audit = self.history()
        result = subscription_preflight(
            history=audit, verified_order_source="yes",
            timestamped_independent_execution_audit=True,
            risk_and_fee_disclosures_approved=1,
            jurisdiction_approved=True, subscriber_delivery_proven=True,
            refund_terms_approved=True, legal_merchant_ready=True,
        )
        self.assertFalse(result["eligible_for_owner_release_review"])
        self.assertEqual(
            result["missing"], ["signed_order_source", "risk_and_fee_disclosures"],
        )

    def test_all_eight_prep_checks_still_do_not_issue_money_or_access(self):
        audit = self.history()
        result = subscription_preflight(
            history=audit, verified_order_source=True,
            timestamped_independent_execution_audit=True,
            risk_and_fee_disclosures_approved=True,
            jurisdiction_approved=True, subscriber_delivery_proven=True,
            refund_terms_approved=True, legal_merchant_ready=True,
        )
        self.assertTrue(result["eligible_for_owner_release_review"])
        self.assertFalse(result["checkout_enabled"])
        self.assertFalse(result["account_or_subscriber_created"])
        self.assertFalse(result["realized_performance_verified"])
        self.assertIsNone(result["money_received"])


if __name__ == "__main__":
    unittest.main()
