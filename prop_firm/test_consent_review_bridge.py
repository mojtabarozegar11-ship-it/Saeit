"""Fail-closed regression tests for source-only consent review bridge."""
import unittest

from prop_firm.consent_review_bridge import BridgeClosed, prepare_consent_review
from prop_firm.order_readiness import REQUIRED


class ConsentReviewBridgeTests(unittest.TestCase):
    def packet(self):
        return dict(
            interest_ref="interest:001",
            interest_digest="a" * 64,
            buyer_ref="buyer:001",
            consent_recorded=True,
            independent_buyer_link_verified=True,
            signed_customer_terms_sha256="b" * 64,
            trusted_contract_sha256="b" * 64,
            trusted_gate_evidence={k: True for k in REQUIRED},
        )

    def test_all_gates_never_authorize_money_or_enrollment(self):
        result = prepare_consent_review(**self.packet())
        self.assertEqual(result.missing_gates, ())
        self.assertFalse(result.invoice_authorized)
        self.assertFalse(result.payment_authorized)
        self.assertFalse(result.enrollment_authorized)
        self.assertFalse(result.marketing_authorized)
        self.assertEqual(result.state, "private_review_only")

    def test_each_of_twenty_missing_gates_remains_blocked(self):
        for gate in REQUIRED:
            with self.subTest(gate=gate):
                data = self.packet()
                data["trusted_gate_evidence"][gate] = False
                result = prepare_consent_review(**data)
                self.assertIn(gate, result.missing_gates)
                self.assertFalse(result.invoice_authorized)

    def test_missing_consent_fails(self):
        data = self.packet()
        data["consent_recorded"] = False
        with self.assertRaises(BridgeClosed):
            prepare_consent_review(**data)

    def test_missing_buyer_provenance_fails(self):
        data = self.packet()
        data["independent_buyer_link_verified"] = False
        with self.assertRaises(BridgeClosed):
            prepare_consent_review(**data)

    def test_unsigned_or_informational_document_fails(self):
        data = self.packet()
        data["signed_customer_terms_sha256"] = "c" * 64
        with self.assertRaises(BridgeClosed):
            prepare_consent_review(**data)

    def test_invalid_digest_fails(self):
        data = self.packet()
        data["interest_digest"] = "not-a-digest"
        with self.assertRaises(BridgeClosed):
            prepare_consent_review(**data)

    def test_non_boolean_gate_fails_closed(self):
        data = self.packet()
        data["trusted_gate_evidence"]["buyer_kyc_verified"] = 1
        result = prepare_consent_review(**data)
        self.assertIn("buyer_kyc_verified", result.missing_gates)


if __name__ == "__main__":
    unittest.main()
