"""Business reserve safety must never claim full coverage without evidence."""
import unittest
from decimal import Decimal

from financial_core.reconciliation import Reconciler, ReserveSnapshot


class ReserveReconciliationTests(unittest.TestCase):
    def setUp(self):
        self.verify = Reconciler().verify

    def test_fully_reserved_assets_are_independently_verified(self):
        ok, failed = self.verify([
            ReserveSnapshot("USD", Decimal("125.00"), Decimal("135.00")),
            ReserveSnapshot("TRX", Decimal("700"), Decimal("700")),
        ])
        self.assertTrue(ok)
        self.assertEqual(failed, ())

    def test_insufficient_asset_cannot_be_hidden_by_another_asset_surplus(self):
        shortfall = ReserveSnapshot("TRX", Decimal("100"), Decimal("90"))
        ok, failed = self.verify([
            ReserveSnapshot("USD", Decimal("1"), Decimal("100000")),
            shortfall,
        ])
        self.assertFalse(ok)
        self.assertEqual(failed, (shortfall,))

    def test_empty_reserve_report_is_not_proof_of_full_cover(self):
        self.assertEqual(self.verify([]), (False, ()))

    def test_negative_liabilities_and_assets_are_invalid_evidence(self):
        for debt, assets in [
            (Decimal("-20"), Decimal("0")),
            (Decimal("0"), Decimal("-1")),
            (Decimal("-100"), Decimal("-50")),
        ]:
            snapshot = ReserveSnapshot("TRX", debt, assets)
            with self.subTest(liability=debt, holdings=assets):
                self.assertFalse(snapshot.fully_reserved)
                with self.assertRaises(ValueError):
                    _ = snapshot.surplus

    def test_nonfinite_untyped_and_unidentified_values_are_rejected(self):
        bad_values = [
            ReserveSnapshot("USD", Decimal("NaN"), Decimal("2")),
            ReserveSnapshot("USD", Decimal("0"), Decimal("Infinity")),
            ReserveSnapshot("", Decimal("0"), Decimal("0")),
            ReserveSnapshot(" TRX", Decimal("0"), Decimal("0")),
            ReserveSnapshot("USD", 100, Decimal("100")),
            ReserveSnapshot("USD", Decimal("100"), "200"),
        ]
        for snapshot in bad_values:
            with self.subTest(snapshot=snapshot):
                self.assertFalse(snapshot.fully_reserved)
                ok, failed = self.verify([snapshot])
                self.assertFalse(ok)
                self.assertEqual(failed, (snapshot,))

    def test_duplicate_reserve_assets_are_rejected(self):
        snapshots = [
            ReserveSnapshot("USD", Decimal("10"), Decimal("10")),
            ReserveSnapshot("USD", Decimal("10"), Decimal("10")),
        ]
        with self.assertRaisesRegex(ValueError, "duplicate reserve asset"):
            self.verify(snapshots)

    def test_input_must_have_the_expected_evidence_type(self):
        with self.assertRaisesRegex(ValueError, "snapshot type"):
            self.verify([{"asset": "USD", "treasury_assets": "100"}])


if __name__ == "__main__":
    unittest.main()
