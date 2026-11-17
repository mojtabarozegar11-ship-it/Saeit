"""Regression coverage for the private, fail-closed replay registry."""
import sqlite3
import unittest

from prop_firm.plan1_private_review_replay import (
    SCHEMA_SQL, ReviewReplayClosed, claim_review_once,
)

R1 = "PROP1-REVIEW-" + "A" * 32
R2 = "PROP1-REVIEW-" + "B" * 32
A = "a" * 64
B = "b" * 64
C = "c" * 64
D = "d" * 64


class ReviewReplayTests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(":memory:")
        self.db.executescript(SCHEMA_SQL)

    def tearDown(self):
        self.db.close()

    def claim(self, ref=R1, acceptance=A, attestation=B, db=None):
        return claim_review_once(
            self.db if db is None else db, review_ref=ref,
            acceptance_sha256=acceptance,
            reviewer_attestation_sha256=attestation,
        )

    def test_first_claim_is_private_only(self):
        self.assertEqual(self.claim(), "PRIVATE_REVIEW_CLAIMED_ONLY")
        self.assertEqual(self.db.execute("SELECT count(*) FROM prop1_review_claims").fetchone()[0], 1)

    def test_duplicate_review_ref_closed(self):
        self.claim()
        with self.assertRaises(ReviewReplayClosed):
            self.claim(R1, C, D)
        self.assertEqual(self.db.execute("SELECT count(*) FROM prop1_review_claims").fetchone()[0], 1)

    def test_duplicate_acceptance_closed(self):
        self.claim()
        with self.assertRaises(ReviewReplayClosed):
            self.claim(R2, A, C)

    def test_duplicate_attestation_closed(self):
        self.claim()
        with self.assertRaises(ReviewReplayClosed):
            self.claim(R2, C, B)

    def test_distinct_review_is_allowed(self):
        self.claim()
        self.assertEqual(self.claim(R2, C, D), "PRIVATE_REVIEW_CLAIMED_ONLY")
        self.assertEqual(self.db.execute("SELECT count(*) FROM prop1_review_claims").fetchone()[0], 2)

    def test_invalid_inputs_fail_closed(self):
        cases = [
            (None, A, B), ("", A, B), ("PROP1-REVIEW-" + "a"*32, A, B),
            (R1, None, B), (R1, "0"*64, B), (R1, A.upper(), B),
            (R1, A, None), (R1, A, "0"*64), (R1, A, A),
            (R1, "z"*64, B), (R1, A, "z"*64), (R1, A, B+"x"),
            (R1+"x", A, B), (R1, A+"x", B), (R1, A, B.upper()),
        ]
        for ref, acceptance, attestation in cases:
            with self.subTest(ref=ref, acceptance=acceptance):
                with self.assertRaises(ReviewReplayClosed):
                    self.claim(ref, acceptance, attestation)
        self.assertEqual(self.db.execute("SELECT count(*) FROM prop1_review_claims").fetchone()[0], 0)

    def test_missing_schema_fails_closed(self):
        empty = sqlite3.connect(":memory:")
        try:
            with self.assertRaises(ReviewReplayClosed):
                self.claim(db=empty)
            self.assertFalse(empty.in_transaction)
        finally:
            empty.close()

    def test_non_database_fails_closed(self):
        with self.assertRaises(ReviewReplayClosed):
            self.claim(db="not-a-database")

    def test_rollback_after_duplicate_allows_new_claim(self):
        self.claim()
        with self.assertRaises(ReviewReplayClosed):
            self.claim()
        self.assertFalse(self.db.in_transaction)
        self.assertEqual(self.claim(R2, C, D), "PRIVATE_REVIEW_CLAIMED_ONLY")


if __name__ == "__main__":
    unittest.main()
