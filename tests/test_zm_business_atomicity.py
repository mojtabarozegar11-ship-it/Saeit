"""Prevent simultaneous Zomorod business requests from overspending an invoice
or withdrawing the same last inventory item twice.

The concurrency model uses disposable SQLite databases only. Source checks
ensure the real PHP branches use BEGIN IMMEDIATE before balance reads and
ROLLBACK for both validation errors and SQL exceptions.
"""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import sqlite3
import tempfile
import threading
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "content/zomorod-business/app.php"


def action_block(name, next_name):
    source = APP.read_text(encoding="utf-8")
    begin = source.index("} elseif($action==='" + name + "'){")
    end = source.index("} elseif($action==='" + next_name + "'){", begin)
    return source[begin:end]


def attempt(db_path, barrier, kind):
    conn = sqlite3.connect(db_path, timeout=5, isolation_level=None)
    conn.execute("PRAGMA busy_timeout=5000")
    try:
        barrier.wait(timeout=5)
        conn.execute("BEGIN IMMEDIATE")
        try:
            if kind == "stock":
                available = conn.execute("SELECT COALESCE(SUM(qty),0) FROM movements").fetchone()[0]
                if available - 1 < 0:
                    conn.execute("ROLLBACK")
                    return False
                time.sleep(0.08)
                conn.execute("INSERT INTO movements (qty) VALUES (-1)")
            else:
                paid = conn.execute("SELECT COALESCE(SUM(amount),0) FROM payments").fetchone()[0]
                if 70 > 100 - paid:
                    conn.execute("ROLLBACK")
                    return False
                time.sleep(0.08)
                conn.execute("INSERT INTO payments (amount) VALUES (70)")
            conn.execute("COMMIT")
            return True
        except BaseException:
            conn.execute("ROLLBACK")
            raise
    finally:
        conn.close()


class BusinessAtomicityTests(unittest.TestCase):
    def test_payment_source_locks_before_outstanding_balance_and_rolls_back(self):
        block = action_block("payment", "inventory")
        self.assertLess(block.index("BEGIN IMMEDIATE"), block.index("SELECT i.*,COALESCE"))
        self.assertLess(block.index("try{"), block.index("if(!$rows)"))
        self.assertLess(block.index("if($amount<=0"), block.index("INSERT INTO invoice_payments"))
        self.assertLess(block.index("INSERT INTO invoice_payments"), block.index("COMMIT"))
        self.assertIn("catch(Throwable $e)", block)
        self.assertIn("ROLLBACK", block)
        self.assertNotIn("$db->beginTransaction()", block)

    def test_stock_source_locks_before_balance_check_and_insert(self):
        block = action_block("stock", "employee")
        self.assertLess(block.index("BEGIN IMMEDIATE"), block.index("SELECT COALESCE(SUM(qty),0)"))
        self.assertLess(block.index("SELECT COALESCE(SUM(qty),0)"), block.index("INSERT INTO inventory_movements"))
        self.assertLess(block.index("if($now+$qty<0)"), block.index("COMMIT"))
        self.assertIn("catch(Throwable $e)", block)
        self.assertIn("ROLLBACK", block)

    def test_simultaneous_stock_withdrawals_cannot_go_negative(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "stock.sqlite3"
            with sqlite3.connect(path) as conn:
                conn.execute("CREATE TABLE movements (qty INTEGER NOT NULL)")
                conn.execute("INSERT INTO movements VALUES (1)")
            barrier = threading.Barrier(2)
            with ThreadPoolExecutor(max_workers=2) as workers:
                a = workers.submit(attempt, path, barrier, "stock")
                b = workers.submit(attempt, path, barrier, "stock")
                self.assertEqual(sorted([a.result(), b.result()]), [False, True])
            with sqlite3.connect(path) as conn:
                self.assertEqual(conn.execute("SELECT SUM(qty) FROM movements").fetchone()[0], 0)

    def test_simultaneous_invoice_payments_cannot_exceed_remainder(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "payment.sqlite3"
            with sqlite3.connect(path) as conn:
                conn.execute("CREATE TABLE payments (amount INTEGER NOT NULL)")
            barrier = threading.Barrier(2)
            with ThreadPoolExecutor(max_workers=2) as workers:
                a = workers.submit(attempt, path, barrier, "payment")
                b = workers.submit(attempt, path, barrier, "payment")
                self.assertEqual(sorted([a.result(), b.result()]), [False, True])
            with sqlite3.connect(path) as conn:
                self.assertEqual(conn.execute("SELECT SUM(amount) FROM payments").fetchone()[0], 70)

    def test_failed_validation_releases_writer_lock(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "release.sqlite3"
            with sqlite3.connect(path) as first:
                first.execute("CREATE TABLE records (amount INTEGER)")
            first = sqlite3.connect(path, isolation_level=None, timeout=3)
            second = sqlite3.connect(path, isolation_level=None, timeout=3)
            try:
                first.execute("BEGIN IMMEDIATE")
                first.execute("ROLLBACK")
                second.execute("BEGIN IMMEDIATE")
                second.execute("INSERT INTO records VALUES (5)")
                second.execute("COMMIT")
                self.assertEqual(second.execute("SELECT SUM(amount) FROM records").fetchone()[0], 5)
            finally:
                first.close()
                second.close()


if __name__ == "__main__":
    unittest.main()
