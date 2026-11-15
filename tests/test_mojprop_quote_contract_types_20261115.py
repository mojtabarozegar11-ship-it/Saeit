"""Type and evidence regressions for the Moj Prop quote contract."""
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace
import unittest

from core.mojprop_quote_contract import QuoteContractError, make_quote_snapshot

class QuoteContractTypeTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 11, 15, 13, 0, tzinfo=timezone.utc)
        self.base = dict(
            lead=SimpleNamespace(request_id="MOJPROP-20261115-TYPE"),
            version=1,
            title="Typed quote",
            scope="A source-backed manual report with explicit scope, limits and delivery conditions.",
            exclusions="No trading, no guarantees and no automatic advice.",
            amount=Decimal("25.00"),
            currency="USD",
            delivery_days=3,
            status="issued",
            reviewed_at=self.now - timedelta(hours=1),
            issued_at=self.now - timedelta(minutes=30),
            expires_at=self.now + timedelta(days=1),
            accepted_at=None,
            acceptance_reference="",
        )

    def make(self, **changes):
        return SimpleNamespace(**{**self.base, **changes})

    def test_version_must_be_a_bounded_integer(self):
        for version in (0, 1000, 1.0, "1", True, None):
            with self.subTest(version=repr(version)), self.assertRaises(QuoteContractError):
                make_quote_snapshot(self.make(version=version), now=self.now)

    def test_acceptance_reference_rejects_non_text_and_control_data(self):
        for reference in (123456, b"receipt:2026", "", "x" * 181, "valid\nreference"):
            with self.subTest(reference=repr(reference)), self.assertRaises(QuoteContractError):
                make_quote_snapshot(
                    self.make(
                        status="accepted",
                        accepted_at=self.now - timedelta(minutes=5),
                        acceptance_reference=reference,
                    ),
                    now=self.now,
                )

    def test_valid_acceptance_is_preserved(self):
        result = make_quote_snapshot(
            self.make(
                status="accepted",
                accepted_at=self.now - timedelta(minutes=5),
                acceptance_reference="buyer-consent:2026-001",
            ),
            now=self.now,
        )
        self.assertEqual(result["version"], 1)
        self.assertEqual(result["status"], "accepted")

if __name__ == "__main__":
    unittest.main()
