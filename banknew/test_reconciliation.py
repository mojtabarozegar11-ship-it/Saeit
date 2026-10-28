"""Read-only settlement reconciliation regression tests."""
import unittest

from banknew.ledger_core import Ledger, LedgerError
from banknew.reconciliation import ReconciliationError, reconcile


class ReconciliationTests(unittest.TestCase):
    def setUp(self):
        self.ledger = Ledger()
        for name, asset, side in (
            ("cash.usdt", "USDT", "D"),
            ("alice.usdt", "USDT", "C"),
            ("bob.usdt", "USDT", "C"),
            ("cash.trx", "TRX", "D"),
            ("alice.trx", "TRX", "C"),
        ):
            self.ledger.create_account(name, asset, side)
        self.mapping = {"USDT": "cash.usdt", "TRX": "cash.trx"}

    def tearDown(self):
        self.ledger.close()

    def fund(self, ref="provider-deposit-1", units=100):
        return self.ledger.post("fund-" + ref, ref, [
            ("cash.usdt", "D", units), ("alice.usdt", "C", units)
        ])

    def statement(self, ref="provider-deposit-1", units=100,
                  direction="IN", asset="USDT"):
        return {"reference": ref, "asset": asset,
                "direction": direction, "units": str(units)}

    def codes(self, report):
        return {issue["code"] for issue in report["issues"]}

    def test_matching_inbound_and_outbound_settlements(self):
        self.fund()
        self.ledger.post("withdraw-1", "provider-payout-1", [
            ("alice.usdt", "D", 25), ("cash.usdt", "C", 25)
        ])
        batch = [self.statement(), self.statement("provider-payout-1", 25, "OUT")]
        report = reconcile(self.ledger, batch, self.mapping)
        self.assertEqual(report["status"], "balanced")
        self.assertEqual(report["matched"], 2)
        self.assertEqual(report["statement_count"], 2)
        self.assertEqual(report["ledger_cash_movements"], 2)
        self.assertEqual(report["issues"], [])
        self.assertEqual(report["source_authentication"], "not_performed_by_this_module")
        self.assertEqual(len(report["statement_digest"]), 64)

    def test_internal_wallet_transfer_not_mistaken_for_provider_cash(self):
        self.fund()
        self.ledger.post("transfer-1", "internal-1", [
            ("alice.usdt", "D", 20), ("bob.usdt", "C", 20)
        ])
        report = reconcile(self.ledger, [self.statement()], self.mapping)
        self.assertEqual(report["status"], "balanced")
        self.assertEqual(report["ledger_cash_movements"], 1)

    def test_statement_absent_from_ledger_is_exception(self):
        report = reconcile(self.ledger, [self.statement("external-only")], self.mapping)
        self.assertIn("missing_ledger_entry", self.codes(report))
        self.assertEqual(report["matched"], 0)

    def test_ledger_absent_from_provider_statement_is_exception(self):
        self.fund()
        report = reconcile(self.ledger, [], self.mapping)
        self.assertIn("missing_provider_statement", self.codes(report))
        self.assertEqual(report["status"], "unreconciled")

    def test_amount_and_direction_mismatch_are_not_approved(self):
        self.fund()
        for statement in (
            self.statement(units=101),
            self.statement(direction="OUT"),
            self.statement(asset="TRX")
        ):
            with self.subTest(statement=statement):
                result = reconcile(self.ledger, [statement], self.mapping)
                self.assertIn("settlement_mismatch", self.codes(result))
                self.assertEqual(result["matched"], 0)

    def test_duplicate_provider_reference_detected(self):
        self.fund()
        report = reconcile(self.ledger, [self.statement(), self.statement()], self.mapping)
        self.assertIn("duplicate_statement_reference", self.codes(report))
        self.assertEqual(report["matched"], 0)

    def test_duplicate_ledger_external_reference_detected(self):
        self.fund()
        self.ledger.post("second-funding", "provider-deposit-1", [
            ("cash.usdt", "D", 50), ("alice.usdt", "C", 50)
        ])
        report = reconcile(self.ledger, [self.statement()], self.mapping)
        self.assertIn("duplicate_ledger_reference", self.codes(report))
        self.assertEqual(report["matched"], 0)

    def test_statement_rejects_imprecise_or_forged_input_shapes(self):
        for amount in (0, -1, 1.2, True, "01", "1e3", "0.01"):
            with self.subTest(amount=amount), self.assertRaises(LedgerError):
                reconcile(self.ledger, [self.statement(units=amount)], self.mapping)
        for row in (
            dict(self.statement(), extra="forged"),
            dict(self.statement(), direction="UNKNOWN"),
            dict(self.statement(), asset="unrecognized"),
        ):
            with self.subTest(row=row), self.assertRaises(LedgerError):
                reconcile(self.ledger, [row], self.mapping)

    def test_unregistered_cash_account_and_invalid_mapping_fail_closed(self):
        with self.assertRaises(ReconciliationError):
            reconcile(self.ledger, [], {"USDT": "missing.account"})
        with self.assertRaises(ReconciliationError):
            reconcile(self.ledger, [], {"USDT": "alice.usdt"})
        with self.assertRaises(ReconciliationError):
            reconcile(self.ledger, [], {"USDT": "cash.usdt", "TRX": "cash.usdt"})
        with self.assertRaises(ReconciliationError):
            reconcile(self.ledger, [self.statement("missing", asset="EUR")], self.mapping)

    def test_tampered_ledger_blocks_reconciliation_before_comparison(self):
        self.fund()
        self.ledger.db.execute(
            "UPDATE accounts SET balance_units='999' WHERE account_id='alice.usdt'"
        )
        with self.assertRaisesRegex(LedgerError, "differs"):
            reconcile(self.ledger, [self.statement()], self.mapping)

    def test_reconciliation_does_not_mutate_financial_balances_or_history(self):
        self.fund()
        before = self.ledger.audit()
        first_balance = self.ledger.balance("alice.usdt")
        first = reconcile(self.ledger, [self.statement()], self.mapping)
        second = reconcile(self.ledger, [self.statement()], self.mapping)
        self.assertEqual(first, second)
        self.assertEqual(self.ledger.audit(), before)
        self.assertEqual(self.ledger.balance("alice.usdt"), first_balance)

    def test_multiple_assets_reconciled_independently(self):
        self.fund()
        self.ledger.post("trx-funding", "provider-trx-1", [
            ("cash.trx", "D", 1234567), ("alice.trx", "C", 1234567)
        ])
        batch = [self.statement(), self.statement(
            "provider-trx-1", 1234567, asset="TRX"
        )]
        report = reconcile(self.ledger, batch, self.mapping)
        self.assertEqual(report["matched"], 2)
        self.assertEqual(report["status"], "balanced")


if __name__ == "__main__":
    unittest.main()
