"""No real trading or publishing: verify evidence policy before any sale."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from unittest import TestCase

from services.mojtaba_signal_policy import (
    EducationalSignal, SignalRecordError, RISK_DISCLAIMER, review_signal,
)


class SingleBotSignalPolicyTests(TestCase):
    def setUp(self):
        self.now = datetime(2026, 11, 15, 10, 0, tzinfo=timezone.utc)
        self.s = EducationalSignal(
            record_id="brief_gold_001",
            asset="XAU/USD", timeframe="1h",
            scenario="Gold may consolidate if volatility eases; a breakout is only one conditional educational scenario.",
            invalidation="Invalidate the scenario if the defined level fails during the reviewed session.",
            evidence_url="https://example.org/market/source",
            observed_at=self.now - timedelta(minutes=30),
            reviewed_at=self.now - timedelta(minutes=10),
            as_of=self.now - timedelta(minutes=5),
            reviewer_id="market_review_01",
            risk_statement=RISK_DISCLAIMER,
        )

    def verify(self, **changes):
        return review_signal(replace(self.s, **changes), now=self.now)

    def test_valid_record_has_stable_fingerprint_without_false_delivery(self):
        result = self.verify()
        self.assertEqual(result["record"]["author_agent"], "mojtaba.bot.ai")
        self.assertTrue(result["content_policy_passed"])
        self.assertFalse(result["independent_source_verified"])
        self.assertFalse(result["publication_allowed"])
        self.assertFalse(result["delivery_confirmed"])
        self.assertFalse(result["payment_received"])
        self.assertEqual(len(result["evidence_fingerprint"]), 64)
        self.assertEqual(self.verify()["evidence_fingerprint"],
                         result["evidence_fingerprint"])

    def test_ordinary_url_is_not_independent_live_market_verification(self):
        result = self.verify(evidence_url="https://example.org/market/source")
        self.assertFalse(result["publication_allowed"])
        self.assertFalse(result["delivery_confirmed"])
        self.assertFalse(result["payment_received"])
        self.assertFalse(result["independent_source_verified"])
        self.assertEqual(result["record"]["reviewer_id"], "market_review_01")

    def test_only_one_bot_owns_signal_identity(self):
        for value in ("another.bot", "", None):
            with self.subTest(value=value), self.assertRaises(SignalRecordError):
                self.verify(author_agent=value)

    def test_source_must_be_independent_https_url(self):
        for value in ("http://example.org/x", "javascript:alert(1)", "https://a",
                      "https://u:p@example.org/x", "https://example.org/x#secret", ""):
            with self.subTest(url=value), self.assertRaises(SignalRecordError):
                self.verify(evidence_url=value)

    def test_market_observation_timestamps_reject_stale_future_and_naive(self):
        changes = (
            {"observed_at": self.now - timedelta(days=2)},
            {"observed_at": self.now + timedelta(minutes=1)},
            {"reviewed_at": self.now - timedelta(hours=1)},
            {"as_of": self.now + timedelta(minutes=2)},
            {"as_of": datetime(2026, 11, 15, 10, 0)},
        )
        for change in changes:
            with self.subTest(change=change), self.assertRaises(SignalRecordError):
                self.verify(**change)

    def test_risk_disclosure_and_invalidation_cannot_be_omitted(self):
        for change in (
            {"risk_statement": "An investment is always safe."},
            {"risk_statement": ""},
            {"invalidation": "none"},
            {"scenario": "buy"},
            {"scenario": "Guaranteed profit. Risk free return guaranteed for every subscriber."},
        ):
            with self.subTest(change=change), self.assertRaises(SignalRecordError):
                self.verify(**change)

    def test_reviewer_and_timeframe_cannot_be_invented(self):
        for change in (
            {"reviewer_id": ""}, {"reviewer_id": "x"},
            {"timeframe": "unlimited"}, {"timeframe": "0"},
            {"asset": ""}, {"asset": "XAU/USD|ETH"},
        ):
            with self.subTest(change=change), self.assertRaises(SignalRecordError):
                self.verify(**change)

    def test_changes_produce_distinct_fingerprint(self):
        before = self.verify()["evidence_fingerprint"]
        after = self.verify(
            scenario=self.s.scenario + " Additional range-bound risks apply."
        )["evidence_fingerprint"]
        self.assertNotEqual(before, after)

    def test_malformed_source_urls_fail_closed_without_uncaught_errors(self):
        invalid_urls = (
            "https://[2001:db8::1",
            "https://example.org:abc/path",
            "https://example.org:65536/path",
            "https://example.org:0/path",
            "https://example.org/path\nX-Injected: 1",
            "https://example.org/path\rX-Injected: 1",
            "https://example.org/path\t?q=1",
            " https://example.org/path",
            "https://example.org/path ",
            "https://example.org\\@attacker.org/path",
            "https://example.org/path" + chr(0xD800),
            "https://example.org/path" + chr(0x7F),
            "https://example.org/path" + chr(0x85),
        )
        for value in invalid_urls:
            with self.subTest(value=repr(value)), self.assertRaises(SignalRecordError):
                self.verify(evidence_url=value)

    def test_unpaired_unicode_surrogates_in_signal_text_fail_closed(self):
        for field in ("scenario", "invalidation", "risk_statement"):
            for char in (chr(0xD800), chr(0xDFFF)):
                with self.subTest(field=field, char=hex(ord(char))):
                    original = getattr(self.s, field)
                    with self.assertRaises(SignalRecordError):
                        self.verify(**{field: original + char})

    def test_valid_https_source_with_query_keeps_stable_provenance(self):
        result = self.verify(evidence_url="https://example.org/market/source?session=123")
        self.assertTrue(result["content_policy_passed"])
        self.assertFalse(result["publication_allowed"])
        self.assertEqual(result["record"]["evidence_url"],
                         "https://example.org/market/source?session=123")
