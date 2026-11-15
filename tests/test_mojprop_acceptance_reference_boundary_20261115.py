"""Strict acceptance evidence must be safe before a quote becomes public."""
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest import TestCase

from core.mojprop_quote_contract import (
    QuoteContractError, make_quote_snapshot, validate_acceptance_reference,
)


class MojPropAcceptanceReferenceTests(TestCase):
    def setUp(self):
        self.issued = datetime(2026, 11, 15, 10, tzinfo=timezone.utc)
        self.offer = SimpleNamespace(
            status="accepted",
            lead=SimpleNamespace(request_id="MOJPROP-20261115-001"),
            title="Farm management advisory",
            scope="A sufficiently detailed advisory scope for a buyer quote.",
            exclusions="Travel and third-party fees are excluded.",
            amount=Decimal("125.00"), currency="USD", delivery_days=7, version=1,
            issued_at=self.issued,
            expires_at=self.issued + timedelta(days=7),
            reviewed_at=self.issued,
            accepted_at=self.issued + timedelta(hours=1),
            acceptance_reference="buyer-approval-2026",
        )

    def test_valid_reference_is_normalized(self):
        self.assertEqual(validate_acceptance_reference("  buyer-approval-2026  "),
                         "buyer-approval-2026")
        self.assertEqual(make_quote_snapshot(self.offer, now=self.issued + timedelta(hours=2))[
            "status"], "accepted")

    def test_non_text_overlong_and_control_references_fail(self):
        for value in (True, 123, "short", "x" * 181,
                      "buyer" + chr(10) + "approval", "buyer" + chr(9) + "approval", "buyer" + chr(0)):
            with self.subTest(value=repr(value)), self.assertRaises(QuoteContractError):
                validate_acceptance_reference(value)

    def test_snapshot_cannot_bypass_reference_boundary(self):
        for value in ("buyer" + chr(10) + "approval", "x" * 181, None):
            payload = dict(vars(self.offer))
            payload["acceptance_reference"] = value
            bad = SimpleNamespace(**payload)
            with self.subTest(value=repr(value)), self.assertRaises(QuoteContractError):
                make_quote_snapshot(bad, now=self.issued + timedelta(hours=2))


if __name__ == "__main__":
    import unittest
    unittest.main()
