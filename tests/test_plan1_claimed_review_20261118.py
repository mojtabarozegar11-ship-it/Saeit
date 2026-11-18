"""B-only integration regressions: signed-review result -> durable replay claim.

The original HMAC/terms verifier is tested in its owning suite; here it is
stubbed so the boundary can be probed without fake customer signatures.
No payment, KYC, broker or production side effect is exercised.
"""
from dataclasses import replace
import os
import sqlite3
import tempfile
from unittest import TestCase
from unittest.mock import patch

from prop_firm.buyer_order_review import Plan1OrderGateClosed
from prop_firm.plan1_private_review_replay import SCHEMA_SQL
from prop_firm.plan1_reviewed_buyer_terms import (
    IndependentlyReviewedTerms, bind_and_claim_independently_reviewed_terms,
)


class ClaimBuyerReviewBoundaryTests(TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.tmp.name, "private-review.sqlite3")
        self.db = sqlite3.connect(self.path)
        self.db.executescript(SCHEMA_SQL)
        self.review = IndependentlyReviewedTerms(
            acceptance_sha256="a" * 64,
            review_ref="PROP1-REVIEW-" + "A" * 32,
            reviewer_attestation_sha256="b" * 64,
        )

    def tearDown(self):
        self.db.close()
        self.tmp.cleanup()

    def apply(self, review=None, connection=None):
        if review is None:
            review = self.review
        if connection is None:
            connection = self.db
        with patch(
            "prop_firm.plan1_reviewed_buyer_terms.bind_independently_reviewed_terms",
            return_value=review,
        ):
            return bind_and_claim_independently_reviewed_terms(
                private_review_connection=connection,
                expected_reviewer_authority_ref="TRUSTED-AUTHORITY",
            )

    def count(self):
        return self.db.execute(
            "SELECT COUNT(*) FROM prop1_review_claims").fetchone()[0]

    def test_01_valid_private_review_claimed(self):
        claim = self.apply()
        self.assertEqual(claim.state, "PRIVATE_INDEPENDENT_REVIEW_CLAIMED_ONLY")
        self.assertEqual(self.count(), 1)

    def test_02_claim_is_frozen(self):
        claim = self.apply()
        with self.assertRaises(AttributeError):
            claim.state = "PAYABLE"

    def test_03_no_authority_in_claim(self):
        claim = self.apply()
        for attr in (
            "identity_verified", "legal_signature_verified",
            "jurisdiction_verified", "capital_verified",
            "invoice_authorized", "payment_authorized",
            "enrollment_authorized", "real_account_authorized",
            "marketing_authorized",
        ):
            with self.subTest(field=attr):
                self.assertIs(getattr(claim, attr), False)

    def test_04_replay_same_review_rejected(self):
        self.apply()
        with self.assertRaises(Plan1OrderGateClosed):
            self.apply()
        self.assertEqual(self.count(), 1)

    def test_05_reused_acceptance_rejected(self):
        self.apply()
        changed = replace(
            self.review, review_ref="PROP1-REVIEW-" + "B" * 32,
            reviewer_attestation_sha256="c" * 64)
        with self.assertRaises(Plan1OrderGateClosed):
            self.apply(changed)

    def test_06_reused_reviewer_evidence_rejected(self):
        self.apply()
        changed = replace(
            self.review, review_ref="PROP1-REVIEW-" + "B" * 32,
            acceptance_sha256="c" * 64)
        with self.assertRaises(Plan1OrderGateClosed):
            self.apply(changed)

    def test_07_bad_reference_rejected(self):
        for bad in ("", "PROP1-REVIEW-" + "a" * 32,
                    "PROP1-REVIEW-" + "A" * 31, self.review.review_ref + "\n"):
            with self.subTest(ref=repr(bad)):
                with self.assertRaises(Plan1OrderGateClosed):
                    self.apply(replace(self.review, review_ref=bad))
        self.assertEqual(self.count(), 0)

    def test_08_bad_acceptance_digest_rejected(self):
        for bad in ("", "A" * 64, "a" * 63, "0" * 64):
            with self.subTest(digest=repr(bad)):
                with self.assertRaises(Plan1OrderGateClosed):
                    self.apply(replace(self.review, acceptance_sha256=bad))
        self.assertEqual(self.count(), 0)

    def test_09_bad_attestation_digest_rejected(self):
        for bad in ("", "B" * 64, "b" * 65, "0" * 64):
            with self.subTest(digest=repr(bad)):
                with self.assertRaises(Plan1OrderGateClosed):
                    self.apply(replace(self.review,
                                       reviewer_attestation_sha256=bad))
        self.assertEqual(self.count(), 0)

    def test_10_identical_evidence_digests_rejected(self):
        with self.assertRaises(Plan1OrderGateClosed):
            self.apply(replace(self.review,
                               reviewer_attestation_sha256="a" * 64))

    def test_11_memory_registry_rejected(self):
        memory = sqlite3.connect(":memory:")
        try:
            memory.executescript(SCHEMA_SQL)
            with self.assertRaises(Plan1OrderGateClosed):
                self.apply(connection=memory)
        finally:
            memory.close()

    def test_12_temp_registry_rejected(self):
        memory = sqlite3.connect("")
        try:
            memory.executescript(SCHEMA_SQL)
            with self.assertRaises(Plan1OrderGateClosed):
                self.apply(connection=memory)
        finally:
            memory.close()

    def test_13_missing_schema_rejected(self):
        missing = sqlite3.connect(os.path.join(self.tmp.name, "missing.sqlite3"))
        try:
            with self.assertRaises(Plan1OrderGateClosed):
                self.apply(connection=missing)
        finally:
            missing.close()

    def test_14_unsafe_journal_rejected(self):
        self.db.execute("PRAGMA journal_mode=OFF")
        with self.assertRaises(Plan1OrderGateClosed):
            self.apply()

    def test_15_unsafe_sync_rejected(self):
        self.db.execute("PRAGMA synchronous=OFF")
        with self.assertRaises(Plan1OrderGateClosed):
            self.apply()

    def test_16_caller_transaction_preserved(self):
        self.db.execute("BEGIN")
        self.db.execute("CREATE TABLE caller (x INTEGER)")
        self.db.execute("INSERT INTO caller VALUES (7)")
        with self.assertRaises(Plan1OrderGateClosed):
            self.apply()
        self.assertTrue(self.db.in_transaction)
        self.assertEqual(self.db.execute("SELECT x FROM caller").fetchone()[0], 7)
        self.db.rollback()

    def test_17_non_review_object_rejected(self):
        with self.assertRaises(Plan1OrderGateClosed):
            self.apply(review=object())
        self.assertEqual(self.count(), 0)

    def test_18_unrecognized_review_state_rejected(self):
        with self.assertRaises(Plan1OrderGateClosed):
            self.apply(replace(self.review, state="ISSUE_INVOICE"))
        self.assertEqual(self.count(), 0)

    def test_19_any_elevated_privilege_rejected(self):
        for key in (
            "identity_verified", "legal_signature_verified",
            "jurisdiction_verified", "capital_verified", "invoice_authorized",
            "payment_authorized", "enrollment_authorized",
            "real_account_authorized", "marketing_authorized",
        ):
            with self.subTest(privilege=key):
                with self.assertRaises(Plan1OrderGateClosed):
                    self.apply(replace(self.review, **{key: True}))
        self.assertEqual(self.count(), 0)

    def test_20_underlying_review_failure_causes_no_claim(self):
        with patch(
            "prop_firm.plan1_reviewed_buyer_terms.bind_independently_reviewed_terms",
            side_effect=Plan1OrderGateClosed("invalid real terms"),
        ):
            with self.assertRaises(Plan1OrderGateClosed):
                bind_and_claim_independently_reviewed_terms(
                    private_review_connection=self.db)
        self.assertEqual(self.count(), 0)

    def test_21_review_inputs_pass_to_verifier_not_registry(self):
        with patch(
            "prop_firm.plan1_reviewed_buyer_terms.bind_independently_reviewed_terms",
            return_value=self.review,
        ) as verify:
            claim = bind_and_claim_independently_reviewed_terms(
                private_review_connection=self.db, server_now_sec=1800000000)
        verify.assert_called_once_with(server_now_sec=1800000000)
        self.assertEqual(claim.review_ref, self.review.review_ref)

    def test_22_review_claim_survives_reopening_database(self):
        self.apply()
        self.db.close()
        self.db = sqlite3.connect(self.path)
        with self.assertRaises(Plan1OrderGateClosed):
            self.apply()
        self.assertEqual(self.count(), 1)

    def test_23_concurrent_connection_replay_rejected(self):
        self.apply()
        other = sqlite3.connect(self.path)
        try:
            with self.assertRaises(Plan1OrderGateClosed):
                self.apply(connection=other)
        finally:
            other.close()

    def test_24_sql_injection_like_reference_rejected(self):
        with self.assertRaises(Plan1OrderGateClosed):
            self.apply(replace(self.review, review_ref="'; DROP TABLE prop1_review_claims; --"))
        self.assertEqual(self.count(), 0)

    def test_25_missing_connection_rejected(self):
        with self.assertRaises(Plan1OrderGateClosed):
            self.apply(connection=object())

    def test_26_closed_connection_rejected(self):
        other = sqlite3.connect(self.path)
        other.close()
        with self.assertRaises(Plan1OrderGateClosed):
            self.apply(connection=other)


if __name__ == "__main__":
    import unittest
    unittest.main()
