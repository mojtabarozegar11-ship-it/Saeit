import unittest
from datetime import datetime, timezone
from decimal import Decimal

from financial_core.revenue_evidence import (
    CustomerRevenueEvidence,
    RevenueEvidenceError,
    verify_customer_revenue,
)


class RevenueEvidenceTests(unittest.TestCase):
    def evidence(self, **changes):
        values = {
            "order_id": "order-123",
            "payment_reference": "payment-abc",
            "settlement_reference": "settlement-xyz",
            "provider": "verified-provider",
            "currency": "USD",
            "amount": Decimal("25.00"),
            "settled_at": datetime(2026, 11, 6, 14, 0, tzinfo=timezone.utc),
            "independently_reconciled": True,
            "source_record": "provider-receipt-1",
        }
        values.update(changes)
        return CustomerRevenueEvidence(**values)

    def test_verified_customer_revenue_is_not_trading_pnl(self):
        fact = verify_customer_revenue(self.evidence())
        self.assertTrue(fact.verified)
        self.assertEqual(fact.ledger, "customer_revenue")
        self.assertFalse(fact.trading_pnl_included)
        self.assertEqual(fact.amount, Decimal("25.00"))

    def test_requires_independent_reconciliation(self):
        with self.assertRaisesRegex(RevenueEvidenceError, "independent_reconciliation_required"):
            verify_customer_revenue(self.evidence(independently_reconciled=False))

    def test_rejects_missing_or_invalid_settlement_evidence(self):
        for changes, reasons in (
            ({"settlement_reference": ""}, ("required_settlement_evidence_missing",)),
            ({"amount": Decimal("0")}, ("settled_amount_must_be_finite_positive",)),
            ({"amount": Decimal("NaN")}, ("settled_amount_must_be_finite_positive",)),
            ({"amount": Decimal("Infinity")}, ("settled_amount_must_be_finite_positive",)),
            ({"amount": 25}, ("settled_amount_must_be_decimal",)),
            ({"currency": "usd"}, ("currency_must_be_canonical_uppercase",)),
            ({"settled_at": datetime(2026, 11, 6, 14, 0)}, ("settled_at_must_be_timezone_aware",)),
        ):
            with self.subTest(changes=changes):
                with self.assertRaisesRegex(RevenueEvidenceError, reasons[0]):
                    verify_customer_revenue(self.evidence(**changes))


if __name__ == "__main__":
    unittest.main()
