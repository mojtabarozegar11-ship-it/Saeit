"""Regression and tamper checks for the isolated MOJ Pay ledger core."""
import sqlite3
import tempfile
import unittest
from pathlib import Path

from banknew.ledger_core import (
    GENESIS_HASH, IdempotencyConflict, InsufficientFunds, Ledger, LedgerError,
    MAX_UNITS,
)


class LedgerTests(unittest.TestCase):
    def setUp(self):
        self.ledger = Ledger()
        for account_id, asset, side in (
            ("cash.usdt", "USDT", "D"),
            ("alice.usdt", "USDT", "C"),
            ("bob.usdt", "USDT", "C"),
        ):
            self.ledger.create_account(account_id, asset, side)

    def tearDown(self):
        self.ledger.close()

    def fund(self, value="100000000"):
        return self.ledger.post("fund-1", "verified-provider-1", [
            ("cash.usdt", "D", value), ("alice.usdt", "C", value)
        ])

    def test_balanced_post_transfer_and_payout(self):
        first_seq, first_hash = self.fund()
        self.assertEqual(first_seq, 1)
        self.assertEqual(len(first_hash), 64)
        self.assertEqual(self.ledger.balance("alice.usdt"), 100000000)
        self.ledger.post("transfer-1", "internal-1", [
            ("alice.usdt", "D", "25123456"),
            ("bob.usdt", "C", "25123456"),
        ])
        self.ledger.post("withdrawal-1", "verified-payout-1", [
            ("bob.usdt", "D", "10000000"),
            ("cash.usdt", "C", "10000000"),
        ])
        self.assertEqual(self.ledger.balance("alice.usdt"), 74876544)
        self.assertEqual(self.ledger.balance("bob.usdt"), 15123456)
        self.assertEqual(self.ledger.balance("cash.usdt"), 90000000)
        self.assertEqual(self.ledger.audit(), {
            "accounts": 3, "journals": 3, "postings": 6,
            "head_hash": self.ledger.db.execute(
                "SELECT journal_hash FROM journals ORDER BY seq DESC LIMIT 1"
            ).fetchone()[0]
        })

    def test_duplicate_same_request_returns_same_entry_only_once(self):
        result = self.fund()
        second = self.ledger.post("fund-1", "verified-provider-1", [
            ("cash.usdt", "D", "100000000"),
            ("alice.usdt", "C", "100000000"),
        ])
        self.assertEqual(second, result)
        self.assertEqual(self.ledger.balance("alice.usdt"), 100000000)
        self.assertEqual(self.ledger.audit()["journals"], 1)

    def test_conflicting_idempotency_key_fails_closed(self):
        self.fund()
        with self.assertRaises(IdempotencyConflict):
            self.ledger.post("fund-1", "different-settlement", [
                ("cash.usdt", "D", "100000000"),
                ("alice.usdt", "C", "100000000"),
            ])
        self.assertEqual(self.ledger.audit()["journals"], 1)

    def test_overdraft_rolls_back_without_partial_ledger(self):
        with self.assertRaises(InsufficientFunds):
            self.ledger.post("unfunded-1", "internal-0", [
                ("alice.usdt", "D", 1), ("bob.usdt", "C", 1)
            ])
        self.assertEqual(self.ledger.balance("alice.usdt"), 0)
        self.assertEqual(self.ledger.balance("bob.usdt"), 0)
        self.assertEqual(self.ledger.audit()["head_hash"], GENESIS_HASH)

    def test_unbalanced_entry_and_cross_currency_transfer_rejected(self):
        with self.assertRaisesRegex(LedgerError, "balance separately"):
            self.ledger.post("unbalanced-1", "internal-a", [
                ("cash.usdt", "D", 100), ("alice.usdt", "C", 99)
            ])
        self.ledger.create_account("cash.trx", "TRX", "D")
        with self.assertRaisesRegex(LedgerError, "balance separately"):
            self.ledger.post("crossasset-1", "internal-b", [
                ("cash.usdt", "D", 100), ("cash.trx", "C", 100)
            ])
        self.assertEqual(self.ledger.audit()["journals"], 0)

    def test_reject_floating_point_negative_and_noncanonical_amount(self):
        for bad in (1.0, True, 0, -1, "001", "0", "1.2", "1e6",
                    "NaN", "1,000", "1" * 39):
            with self.subTest(bad=bad), self.assertRaises(LedgerError):
                self.ledger.post("invalid-1", "invalid-ext", [
                    ("cash.usdt", "D", bad), ("alice.usdt", "C", 1)
                ])
        self.assertEqual(self.ledger.audit()["journals"], 0)

    def test_large_38_digit_integer_precision_is_exact(self):
        value = str(MAX_UNITS)
        self.ledger.post("big-1", "settlement-big-1", [
            ("cash.usdt", "D", value), ("alice.usdt", "C", value)
        ])
        self.assertEqual(self.ledger.balance("cash.usdt"), MAX_UNITS)
        self.assertEqual(self.ledger.balance("alice.usdt"), MAX_UNITS)
        self.assertEqual(self.ledger.audit()["postings"], 2)

    def test_immutable_journal_and_postings_trigger(self):
        self.fund()
        with self.assertRaises(sqlite3.DatabaseError):
            self.ledger.db.execute("UPDATE postings SET units='1'")
        with self.assertRaises(sqlite3.DatabaseError):
            self.ledger.db.execute("DELETE FROM journals")
        with self.assertRaises(sqlite3.DatabaseError):
            self.ledger.db.execute(
                "UPDATE accounts SET normal_side='D' WHERE account_id='alice.usdt'"
            )
        self.assertEqual(self.ledger.audit()["journals"], 1)

    def test_audit_detects_modified_materialized_balance(self):
        self.fund()
        self.ledger.db.execute(
            "UPDATE accounts SET balance_units='999' WHERE account_id='alice.usdt'"
        )
        with self.assertRaisesRegex(LedgerError, "differs"):
            self.ledger.audit()

    def test_two_connections_observe_atomic_conservation(self):
        with tempfile.TemporaryDirectory() as directory:
            path = str(Path(directory) / "ledger.sqlite3")
            first = Ledger(path)
            second = Ledger(path)
            try:
                first.create_account("cash.usdt", "USDT", "D")
                first.create_account("alice.usdt", "USDT", "C")
                first.create_account("bob.usdt", "USDT", "C")
                first.post("fund-1", "settle-1", [
                    ("cash.usdt", "D", 100), ("alice.usdt", "C", 100)
                ])
                second.post("transfer-1", "internal-1", [
                    ("alice.usdt", "D", 80), ("bob.usdt", "C", 80)
                ])
                with self.assertRaises(InsufficientFunds):
                    first.post("transfer-2", "internal-2", [
                        ("alice.usdt", "D", 80), ("bob.usdt", "C", 80)
                    ])
                self.assertEqual(first.balance("alice.usdt"), 20)
                self.assertEqual(second.balance("bob.usdt"), 80)
                self.assertEqual(first.audit()["journals"], 2)
            finally:
                first.close()
                second.close()


if __name__ == "__main__":
    unittest.main()
