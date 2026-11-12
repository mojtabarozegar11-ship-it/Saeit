"""Unit tests for strict financial receipt classification."""
import unittest
from apps.management.settlement_reconciliation import Settlement, reconcile


class SettlementReconciliationTests(unittest.TestCase):
    def test_only_verified_production_settlements_count(self):
        rows = [
            Settlement("a", "USD", "30.00", "r1", "settled", True, "5.00"),
            Settlement("b", "USD", "100", "r2", "pending", True),
            Settlement("c", "USD", "999", "r3", "settled", True, environment="test"),
            Settlement("d", "USD", "50", "r4", "settled", False),
        ]
        self.assertEqual(reconcile(rows, "USD"), {
            "currency": "USD", "confirmed_receipts": 1,
            "excluded_records": 3, "gross_settled": "30.00",
            "refunded": "5.00", "net_received": "25.00"})

    def test_duplicate_receipt_rejected(self):
        row = Settlement("a", "USD", "5", "same", "settled", True)
        with self.assertRaises(ValueError):
            reconcile([row, row], "USD")

    def test_over_refund_rejected(self):
        with self.assertRaises(ValueError):
            reconcile([Settlement("a", "USD", "1", "r1", "settled", True, "2")], "USD")

    def test_negative_and_nan_rejected(self):
        for amount in ("-1", "NaN", "Infinity"):
            with self.subTest(amount=amount), self.assertRaises(ValueError):
                reconcile([Settlement("a", "USD", amount, "r1", "settled", True)], "USD")

    def test_currency_not_mixed(self):
        rows = [Settlement("a", "EUR", "50", "r1", "settled", True)]
        self.assertEqual(reconcile(rows, "USD")["confirmed_receipts"], 0)


if __name__ == "__main__":
    unittest.main()
