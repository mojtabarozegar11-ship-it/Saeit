"""Regression tests for the Plan 1 private reviewer replay reference anchor.

No buyer data, live payment, network, or production database is used.
"""
import sqlite3
import unittest

from prop_firm.plan1_private_review_replay import (
    ReviewReplayClosed, SCHEMA_SQL, claim_review_once,
)


class ReviewReplayAnchorTests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(":memory:")
        self.db.executescript(SCHEMA_SQL)
        self.acceptance = "a" * 64
        self.attestation = "b" * 64
        self.ref = "PROP1-REVIEW-" + "A" * 32

    def tearDown(self):
        self.db.close()

    def claim(self, **overrides):
        kwargs = dict(review_ref=self.ref, acceptance_sha256=self.acceptance,
                      reviewer_attestation_sha256=self.attestation)
        kwargs.update(overrides)
        return claim_review_once(self.db, **kwargs)

    def test_valid_ref_claims_once(self):
        self.assertEqual(self.claim(), "PRIVATE_REVIEW_CLAIMED_ONLY")
        self.assertEqual(self.db.execute("SELECT count(*) FROM prop1_review_claims").fetchone()[0], 1)

    def test_duplicate_ref_fails_closed(self):
        self.claim()
        with self.assertRaises(ReviewReplayClosed):
            self.claim(acceptance_sha256="c" * 64, reviewer_attestation_sha256="d" * 64)

    def test_duplicate_acceptance_fails_closed(self):
        self.claim()
        with self.assertRaises(ReviewReplayClosed):
            self.claim(review_ref="PROP1-REVIEW-" + "B" * 32,
                       reviewer_attestation_sha256="c" * 64)

    def test_duplicate_attestation_fails_closed(self):
        self.claim()
        with self.assertRaises(ReviewReplayClosed):
            self.claim(review_ref="PROP1-REVIEW-" + "B" * 32,
                       acceptance_sha256="c" * 64)

    def test_malformed_refs_rejected(self):
        bad = ["", "PROP1-REVIEW-" + "A" * 31, "PROP1-REVIEW-" + "A" * 33,
               "PROP1-REVIEW-" + "a" * 32, self.ref + "\\Z",
               self.ref + "\n", "X" + self.ref, None, 17]
        for value in bad:
            with self.subTest(value=repr(value)), self.assertRaises(ReviewReplayClosed):
                self.claim(review_ref=value)
        self.assertEqual(self.db.execute("SELECT count(*) FROM prop1_review_claims").fetchone()[0], 0)

    def test_invalid_digests_rejected(self):
        bad = ["", "0" * 64, "G" * 64, "a" * 63, "a" * 65, None, 1]
        for value in bad:
            with self.subTest(value=repr(value)), self.assertRaises(ReviewReplayClosed):
                self.claim(acceptance_sha256=value)
        with self.assertRaises(ReviewReplayClosed):
            self.claim(reviewer_attestation_sha256=self.acceptance)

    def test_nested_transaction_rejected_without_rolling_back_caller(self):
        self.db.execute("BEGIN")
        self.db.execute("CREATE TABLE caller_data (value TEXT)")
        self.db.execute("INSERT INTO caller_data VALUES ('preserve')")
        with self.assertRaises(ReviewReplayClosed):
            self.claim()
        self.assertTrue(self.db.in_transaction)
        self.assertEqual(self.db.execute("SELECT value FROM caller_data").fetchone()[0],
                         "preserve")
        self.db.rollback()

    def test_missing_schema_rejected(self):
        other = sqlite3.connect(":memory:")
        try:
            with self.assertRaises(ReviewReplayClosed):
                claim_review_once(other, review_ref=self.ref,
                                  acceptance_sha256=self.acceptance,
                                  reviewer_attestation_sha256=self.attestation)
        finally:
            other.close()


if __name__ == "__main__":
    unittest.main()
