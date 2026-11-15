"""Offline real-SQLite regression for immutable native-TRX invoice settlement.

No blockchain, RPC, wallet, customer, or production database is contacted.
The test compiles the actual confirm() function AST because its production
chain-verifier imports are private cPanel dependencies, not public source.
"""
import ast
import re
import sqlite3
import tempfile
import unittest
from pathlib import Path


SOURCE = Path(__file__).resolve().parents[1] / "mpw_guest_trx_20261020/guest_settlement.py"
RECEIVER = "T" + "A" * 33
SCHEMA = """
CREATE TABLE guest_orders (
    id INTEGER PRIMARY KEY,
    claim_sha TEXT NOT NULL UNIQUE,
    product_id INTEGER NOT NULL,
    usd TEXT NOT NULL,
    rate TEXT NOT NULL,
    amount_sun INTEGER NOT NULL UNIQUE,
    sender TEXT NOT NULL,
    receiver TEXT NOT NULL,
    issued_ms INTEGER NOT NULL,
    expires_ms INTEGER NOT NULL,
    txid TEXT UNIQUE,
    status TEXT NOT NULL CHECK(status IN ('pending','paid'))
)
"""


class DummyQuote:
    def __init__(self, **kwargs):
        self.fields = kwargs


def real_confirmation(dbpath):
    tree = ast.parse(SOURCE.read_text(encoding="utf-8"), filename=str(SOURCE))
    funcs = [node for node in tree.body if isinstance(node, ast.FunctionDef)
             and node.name == "confirm"]
    if len(funcs) != 1:
        raise AssertionError("Expected exactly one real native TRX confirmation function")
    # Explicit local fake chain-verifier only, with fixed receipt evidence.
    namespace = {
        "re": re,
        "sqlite3": sqlite3,
        "LockedQuote": DummyQuote,
        "TRX_RECEIVER": RECEIVER,
        "receive_wallet": lambda: RECEIVER,
        "tron_solidity_rpc": object(),
        "verify_trx_transfer": lambda tx, quote, rpc: {
            "transaction_hash": tx, "finality": "tron-solidity",
        },
        "connect": lambda: sqlite3.connect(dbpath, timeout=1),
    }
    module = ast.Module(body=funcs, type_ignores=[])
    exec(compile(module, str(SOURCE), "exec"), namespace)
    return namespace["confirm"], namespace


class LockedInvoiceSqliteTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dbpath = str(Path(self.tmp.name) / "invoice.sqlite3")
        self.invoice = {
            "id": 1,
            "claim_sha": "synthetic-claim-hash",
            "product_id": 72,
            "usd": "7.50",
            "rate": "0.25",
            "amount_sun": 30000000,
            "sender": "T" + "B" * 33,
            "receiver": RECEIVER,
            "issued_ms": 1700000000000,
            "expires_ms": 1700000600000,
            "status": "pending",
        }
        with self.db() as db:
            db.executescript(SCHEMA)
            db.execute(
                "INSERT INTO guest_orders "
                "(id,claim_sha,product_id,usd,rate,amount_sun,sender,receiver,"
                "issued_ms,expires_ms,status) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                tuple(self.invoice[k] for k in (
                    "id", "claim_sha", "product_id", "usd", "rate", "amount_sun",
                    "sender", "receiver", "issued_ms", "expires_ms", "status",
                )),
            )
        self.confirm, self.dependencies = real_confirmation(self.dbpath)

    def db(self):
        return sqlite3.connect(self.dbpath)

    def status(self):
        with self.db() as db:
            return db.execute("SELECT status,txid FROM guest_orders WHERE id=1").fetchone()

    def test_matching_verified_invoice_can_settle_once(self):
        self.assertTrue(self.confirm(self.invoice, "a" * 64))
        self.assertEqual(self.status(), ("paid", "a" * 64))
        with self.assertRaisesRegex(RuntimeError, "Concurrent invoice"):
            self.confirm(self.invoice, "b" * 64)
        self.assertEqual(self.status(), ("paid", "a" * 64))

    def test_every_changed_locked_quote_field_blocks_stale_paid_write(self):
        variations = {
            "claim_sha": "different-claim",
            "product_id": 225,
            "usd": "8.00",
            "rate": "0.30",
            "amount_sun": 30000001,
            "sender": "T" + "C" * 33,
            "receiver": "T" + "D" * 33,
            "issued_ms": 1700000000100,
            "expires_ms": 1700000700000,
        }
        for field, drifted in variations.items():
            with self.subTest(field=field):
                with self.db() as db:
                    db.execute(f"UPDATE guest_orders SET {field}=? WHERE id=1", (drifted,))
                with self.assertRaisesRegex(RuntimeError, "Concurrent invoice or locked quote changed"):
                    self.confirm(self.invoice, "a" * 64)
                self.assertEqual(self.status(), ("pending", None))
                with self.db() as db:
                    db.execute(f"UPDATE guest_orders SET {field}=? WHERE id=1",
                               (self.invoice[field],))

    def test_invalid_transaction_id_never_marks_invoice_paid(self):
        for invalid in (None, 123, [], {}, "x", "0x" + "a" * 64):
            with self.subTest(value=type(invalid).__name__), self.assertRaises(ValueError):
                self.confirm(self.invoice, invalid)
        self.assertEqual(self.status(), ("pending", None))

    def test_unsolidified_proof_never_marks_invoice_paid(self):
        self.dependencies["verify_trx_transfer"] = lambda tx, quote, rpc: {
            "transaction_hash": tx, "finality": "unconfirmed",
        }
        with self.assertRaisesRegex(ValueError, "finality evidence missing"):
            self.confirm(self.invoice, "f" * 64)
        self.assertEqual(self.status(), ("pending", None))


if __name__ == "__main__":
    unittest.main()
