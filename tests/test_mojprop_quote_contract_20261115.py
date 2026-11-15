"""Regression tests for the distinction between a quote and revenue."""
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace
import unittest

from core.mojprop_quote_contract import QuoteContractError, make_quote_snapshot

class QuoteSnapshotTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 11, 15, 12, 0, tzinfo=timezone.utc)
        self.lead = SimpleNamespace(request_id="MOJPROP-20261115-AB12")
        self.base = dict(
            lead=self.lead,
            version=1,
            title="Educational gold-market brief",
            scope="A dated, source-backed educational report with scenarios, invalidation and explicit limitations.",
            exclusions="No live trading, funded account, guaranteed return or automatic advice.",
            amount=Decimal("99.00"),
            currency="USD",
            delivery_days=7,
            status="issued",
            reviewed_at=self.now - timedelta(hours=2),
            issued_at=self.now - timedelta(hours=1),
            expires_at=self.now + timedelta(days=2),
            accepted_at=None,
            acceptance_reference="",
        )

    def make(self, **changes):
        return SimpleNamespace(**{**self.base, **changes})

    def test_issued_snapshot_is_not_a_payment_or_delivery(self):
        result = make_quote_snapshot(self.make(), now=self.now)
        self.assertEqual(result["reference"], "MOJPROP-20261115-AB12")
        self.assertEqual(result["amount"], "99.00")
        self.assertFalse(result["payable"])
        self.assertEqual(result["payment_status"], "not_collected")
        self.assertEqual(result["delivery_status"], "not_delivered")
        self.assertEqual(result["revenue_status"], "not_received")

    def test_acceptance_requires_evidence_inside_active_window(self):
        result = make_quote_snapshot(
            self.make(
                status="accepted",
                accepted_at=self.now - timedelta(minutes=10),
                acceptance_reference="buyer-consent:portal-001",
            ),
            now=self.now,
        )
        self.assertEqual(result["status"], "accepted")

    def test_draft_and_cancelled_offers_cannot_be_called_quotes(self):
        for status in ("draft", "approved", "cancelled", "expired"):
            with self.subTest(status=status), self.assertRaises(QuoteContractError):
                make_quote_snapshot(self.make(status=status), now=self.now)

    def test_expired_quote_is_rejected(self):
        with self.assertRaises(QuoteContractError):
            make_quote_snapshot(
                self.make(expires_at=self.now - timedelta(minutes=1)),
                now=self.now,
            )

    def test_float_and_zero_amounts_are_rejected(self):
        for amount in (99.0, Decimal("0.00"), Decimal("NaN"), Decimal("99.001")):
            with self.subTest(amount=repr(amount)), self.assertRaises(QuoteContractError):
                make_quote_snapshot(self.make(amount=amount), now=self.now)

    def test_future_issuance_and_oversized_window_are_rejected(self):
        with self.assertRaises(QuoteContractError):
            make_quote_snapshot(
                self.make(issued_at=self.now + timedelta(minutes=1)),
                now=self.now,
            )
        with self.assertRaises(QuoteContractError):
            make_quote_snapshot(
                self.make(expires_at=self.now + timedelta(days=91)),
                now=self.now,
            )

    def test_acceptance_before_issue_or_without_reference_is_rejected(self):
        for changes in (
            {"status": "accepted", "accepted_at": self.now - timedelta(days=1),
             "acceptance_reference": "buyer-consent:old"},
            {"status": "accepted", "accepted_at": self.now - timedelta(minutes=10),
             "acceptance_reference": ""},
        ):
            with self.subTest(changes=changes), self.assertRaises(QuoteContractError):
                make_quote_snapshot(self.make(**changes), now=self.now)

    def test_quote_contract_never_invents_a_payment_route(self):
        result = make_quote_snapshot(self.make(), now=self.now)
        self.assertNotIn("tx_id", result)
        self.assertNotIn("wallet", result)
        self.assertNotIn("payment_url", result)


    def test_quote_version_must_be_canonical_and_bounded(self):
        for version in (0, -1, 1000, "1", True, None, 1.0):
            with self.subTest(version=repr(version)), self.assertRaises(QuoteContractError):
                make_quote_snapshot(self.make(version=version), now=self.now)

    def test_unpaired_unicode_surrogate_in_quote_cannot_reach_buyer(self):
        for field in ("title", "scope", "exclusions"):
            for surrogate in (chr(0xD800), chr(0xDFFF)):
                with self.subTest(field=field, surrogate=repr(surrogate)):
                    value = self.base[field] + surrogate
                    with self.assertRaises(QuoteContractError):
                        make_quote_snapshot(self.make(**{field: value}), now=self.now)

    def test_wrong_clock_type_is_rejected_as_domain_error(self):
        for bad in (0, "", [], {}, datetime(2026, 11, 15, 12, 0)):
            with self.subTest(clock=repr(bad)), self.assertRaises(QuoteContractError):
                make_quote_snapshot(self.make(), now=bad)

if __name__ == "__main__":
    unittest.main()
