"""Pure proof-claim policy tests; no network/credentials/actual payments."""
import copy
import sqlite3
import tempfile
import unittest
from core.tron_gateway_settlement_policy import canonical_settlement_claim, InvalidSettlementProof

PROOF = {
    "txid": "a"*64, "proof_digest": "b"*64,
    "sender_hex": "41"+"c"*40, "block_height": 12345,
    "block_time_ms": 1800000000000, "finality": "solidified",
}


class SettlementClaimPolicyTests(unittest.TestCase):
    def check_invalid(self, **changes):
        bad = dict(PROOF, **changes)
        with self.assertRaises(InvalidSettlementProof):
            canonical_settlement_claim(bad)

    def test_valid(self):
        self.assertEqual(canonical_settlement_claim(PROOF), {"txid":"a"*64,"proof_digest":"b"*64})
    def test_upper_tx_canonicalized(self):
        self.assertEqual(canonical_settlement_claim(dict(PROOF,txid="A"*64))["txid"],"a"*64)
    def test_no_mutation_of_proof(self):
        before=copy.deepcopy(PROOF); canonical_settlement_claim(PROOF); self.assertEqual(PROOF,before)
    def test_wrong_type(self):
        for x in (None, [], "", True, 4):
            with self.subTest(x=x), self.assertRaises(InvalidSettlementProof): canonical_settlement_claim(x)
    def test_invalid_txid_length(self): self.check_invalid(txid="a"*63)
    def test_invalid_txid_alphabet(self): self.check_invalid(txid="z"*64)
    def test_invalid_txid_whitespace(self): self.check_invalid(txid="a"*64+"\n")
    def test_invalid_txid_bool(self): self.check_invalid(txid=True)
    def test_invalid_digest_length(self): self.check_invalid(proof_digest="b"*63)
    def test_invalid_digest_uppercase(self): self.check_invalid(proof_digest="B"*64)
    def test_invalid_digest_bool(self): self.check_invalid(proof_digest=True)
    def test_invalid_sender_prefix(self): self.check_invalid(sender_hex="42"+"c"*40)
    def test_invalid_sender_length(self): self.check_invalid(sender_hex="41"+"c"*39)
    def test_invalid_sender_uppercase(self): self.check_invalid(sender_hex="41"+"C"*40)
    def test_invalid_height_zero(self): self.check_invalid(block_height=0)
    def test_invalid_height_negative(self): self.check_invalid(block_height=-1)
    def test_invalid_height_bool(self): self.check_invalid(block_height=True)
    def test_invalid_timestamp_zero(self): self.check_invalid(block_time_ms=0)
    def test_invalid_timestamp_bool(self): self.check_invalid(block_time_ms=False)
    def test_missing_finality(self):
        bad=dict(PROOF);del bad['finality']
        with self.assertRaises(InvalidSettlementProof):canonical_settlement_claim(bad)
    def test_wrong_finality(self): self.check_invalid(finality="confirmed")
    def test_missing_digest(self):
        bad=dict(PROOF);del bad['proof_digest']
        with self.assertRaises(InvalidSettlementProof):canonical_settlement_claim(bad)
    def test_extra_metadata_ignored(self):
        self.assertEqual(canonical_settlement_claim(dict(PROOF,buyer_email='do not persist')),{"txid":"a"*64,"proof_digest":"b"*64})
    def test_canonical_unique_txid_in_sqlite(self):
        with sqlite3.connect(':memory:') as db:
            db.execute('CREATE TABLE claim(txid TEXT PRIMARY KEY, provider TEXT NOT NULL)')
            first=canonical_settlement_claim(PROOF)['txid']
            second=canonical_settlement_claim(dict(PROOF,txid="A"*64))['txid']
            db.execute('INSERT INTO claim VALUES (?,?)',(first,'new'))
            with self.assertRaises(sqlite3.IntegrityError):
                db.execute('INSERT INTO claim VALUES (?,?)',(second,'old'))
            self.assertEqual(db.execute('SELECT count(*) FROM claim').fetchone()[0],1)
    def test_transaction_rolls_back_claim_with_failed_credit_sqlite(self):
        with sqlite3.connect(':memory:') as db:
            db.execute('CREATE TABLE claim(txid TEXT PRIMARY KEY)')
            db.execute('CREATE TABLE credit(txid TEXT PRIMARY KEY, amount INTEGER CHECK(amount > 0))')
            try:
                with db:
                    db.execute('INSERT INTO claim VALUES (?)',(PROOF['txid'],))
                    db.execute('INSERT INTO credit VALUES (?,?)',(PROOF['txid'], -1))
            except sqlite3.IntegrityError:pass
            self.assertEqual(db.execute('SELECT count(*) FROM claim').fetchone()[0],0)
    def test_distinct_txids_can_coexist_sqlite(self):
        with sqlite3.connect(':memory:') as db:
            db.execute('CREATE TABLE claim(txid TEXT PRIMARY KEY)')
            db.execute('INSERT INTO claim VALUES (?)',(PROOF['txid'],))
            db.execute('INSERT INTO claim VALUES (?)',('d'*64,))
            self.assertEqual(db.execute('SELECT count(*) FROM claim').fetchone()[0],2)

if __name__=='__main__':unittest.main()
