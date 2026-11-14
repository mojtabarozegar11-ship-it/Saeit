"""Real two-connection SQLite race tests for the canonical-TX claim protocol.

SQLite is not MariaDB; these results do NOT prove production engine semantics.
"""
from concurrent.futures import ThreadPoolExecutor
import sqlite3
import tempfile
from pathlib import Path
from threading import Barrier
import unittest

from core.tron_gateway_settlement_policy import canonical_settlement_claim

PROOF = {"txid":"a"*64,"proof_digest":"b"*64,"sender_hex":"41"+"c"*40,
         "block_height":42,"block_time_ms":1800000000000,"finality":"solidified"}

class CanonicalClaimRaceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.dbfile = str(Path(self.temp.name,'claims.sqlite3'))
        with sqlite3.connect(self.dbfile) as c:
            c.execute('PRAGMA journal_mode=WAL')
            c.execute('CREATE TABLE claims (txid TEXT PRIMARY KEY, provider TEXT NOT NULL)')
            c.execute('CREATE TABLE ledger (txid TEXT UNIQUE, amount INTEGER CHECK (amount>0))')

    def tearDown(self): self.temp.cleanup()

    def write(self, txid, provider, *, amount=1):
        conn=sqlite3.connect(self.dbfile, timeout=4)
        try:
            conn.execute('BEGIN IMMEDIATE')
            conn.execute('INSERT INTO claims (txid,provider) VALUES (?,?)',(txid,provider))
            conn.execute('INSERT INTO ledger (txid,amount) VALUES (?,?)',(txid,amount))
            conn.commit()
            return 'claimed'
        except sqlite3.IntegrityError:
            conn.rollback()
            return 'rejected'
        finally: conn.close()

    def canonical(self, value): return canonical_settlement_claim(dict(PROOF,txid=value))['txid']

    def test_two_provider_same_txid_one_wins(self):
        barrier=Barrier(2)
        def worker(provider,txid):
            barrier.wait(timeout=3)
            return self.write(self.canonical(txid),provider)
        with ThreadPoolExecutor(max_workers=2) as pool:
            f1=pool.submit(worker,'old',PROOF['txid'].upper())
            f2=pool.submit(worker,'new',PROOF['txid'])
            results=sorted((f1.result(timeout=8),f2.result(timeout=8)))
        self.assertEqual(results,['claimed','rejected'])
        with sqlite3.connect(self.dbfile) as db:
            self.assertEqual(db.execute('SELECT count(*) FROM claims').fetchone()[0],1)
            self.assertEqual(db.execute('SELECT count(*) FROM ledger').fetchone()[0],1)

    def test_unrelated_txids_both_win(self):
        self.assertEqual(self.write(self.canonical('a'*64),'new'),'claimed')
        self.assertEqual(self.write(self.canonical('b'*64),'old'),'claimed')
        with sqlite3.connect(self.dbfile) as db:
            self.assertEqual(db.execute('SELECT count(*) FROM claims').fetchone()[0],2)

    def test_failed_event_rolls_back_claim(self):
        self.assertEqual(self.write(self.canonical('a'*64),'new',amount=-1),'rejected')
        with sqlite3.connect(self.dbfile) as db:
            self.assertEqual(db.execute('SELECT count(*) FROM claims').fetchone()[0],0)

    def test_second_attempt_after_failed_event_can_succeed(self):
        self.assertEqual(self.write(self.canonical('a'*64),'new',amount=-1),'rejected')
        self.assertEqual(self.write(self.canonical('a'*64),'new',amount=1),'claimed')

    def test_same_provider_duplicate_denied(self):
        self.assertEqual(self.write(self.canonical('a'*64),'new'),'claimed')
        self.assertEqual(self.write(self.canonical('a'*64),'new'),'rejected')

    def test_old_provider_duplicate_denied_only_if_it_participates(self):
        self.assertEqual(self.write(self.canonical('a'*64),'old'),'claimed')
        self.assertEqual(self.write(self.canonical('a'*64),'new'),'rejected')

    def test_legacy_writer_bypassing_claim_table_not_protected(self):
        # Explicit demonstration of the remaining blocker: a writer directly
        # inserting ledger entries with a distinct legacy reference can avoid
        # this *participating-writer* claim mechanism entirely.
        with sqlite3.connect(self.dbfile) as db:
            db.execute('CREATE TABLE legacy_credits(reference TEXT UNIQUE)')
            db.execute('INSERT INTO legacy_credits VALUES (?)',('walletless:tron-mainnet:'+'a'*64,))
        self.assertEqual(self.write(self.canonical('a'*64),'new'),'claimed')
        with sqlite3.connect(self.dbfile) as db:
            self.assertEqual(db.execute('SELECT count(*) FROM legacy_credits').fetchone()[0],1)
            self.assertEqual(db.execute('SELECT count(*) FROM claims').fetchone()[0],1)
        # This is a model of missing shared participation, NOT an acceptable
        # live state. It is why settlement exclusivity defaults to False.

if __name__=='__main__':unittest.main()
