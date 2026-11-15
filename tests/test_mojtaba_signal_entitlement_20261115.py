"""Regression tests for signal entitlement evidence gates."""
import unittest

from services.mojtaba_signal_entitlement import (
    SignalEntitlementError, advance_signal_entitlement, commercial_flags,
)

class SignalEntitlementTests(unittest.TestCase):
    def test_expected_review_to_delivery_path(self):
        state = advance_signal_entitlement("requested", "offer_issued")
        state = advance_signal_entitlement(
            state, "payment_verified",
            evidence={"verified": True, "receipt_id": "receipt:2026:0001"},
            payment_verifier=lambda stored: stored["receipt_id"] == "receipt:2026:0001",
        )
        state = advance_signal_entitlement(
            state, "delivery_acknowledged",
            evidence={"delivery_id": "delivery:2026:0001"},
            delivery_verifier=lambda stored: stored["delivery_id"] == "delivery:2026:0001",
        )
        self.assertEqual(state, "delivered")
        self.assertTrue(commercial_flags(state)["delivery_confirmed"])

    def test_payment_cannot_be_inferred_from_offer(self):
        with self.assertRaises(SignalEntitlementError):
            advance_signal_entitlement("offered", "payment_verified")

    def test_unverified_receipt_is_blocked(self):
        for evidence in (
            {"verified": False, "receipt_id": "receipt:2026:0001"},
            {"verified": True, "receipt_id": ""},
            {"verified": True, "receipt_id": "x"},
        ):
            with self.subTest(evidence=evidence), self.assertRaises(SignalEntitlementError):
                advance_signal_entitlement("offered", "payment_verified", evidence=evidence)

    def test_delivery_requires_a_paid_state(self):
        with self.assertRaises(SignalEntitlementError):
            advance_signal_entitlement("offered", "delivery_acknowledged",
                                       evidence={"delivery_id": "delivery:2026:0001"})

    def test_delivery_requires_acknowledgement_reference(self):
        with self.assertRaises(SignalEntitlementError):
            advance_signal_entitlement("paid", "delivery_acknowledged")

    def test_no_transition_can_enable_trading_or_publication(self):
        for state in ("requested", "offered", "paid", "delivered", "closed"):
            flags = commercial_flags(state)
            self.assertFalse(flags["publication_allowed"])
            self.assertFalse(flags["trading_enabled"])

    def test_invalid_event_and_state_fail_closed(self):
        for state, event in (("bad", "offer_issued"), ("requested", ""), ("paid", "close")):
            with self.subTest(state=state, event=event), self.assertRaises(SignalEntitlementError):
                advance_signal_entitlement(state, event)


    def test_typed_receipt_evidence_rejects_coercion_and_faulty_payloads(self):
        for value in (True, 123456, ["receipt:2026:0001"],
                      {"id": "receipt:2026:0001"}, None):
            with self.subTest(receipt=repr(value)), self.assertRaises(SignalEntitlementError):
                advance_signal_entitlement(
                    "offered", "payment_verified",
                    evidence={"verified": True, "receipt_id": value},
                )

    def test_delivery_reference_requires_canonical_string(self):
        for value in (True, 12345678, ["delivery:2026:0001"], None):
            with self.subTest(delivery=repr(value)), self.assertRaises(SignalEntitlementError):
                advance_signal_entitlement(
                    "paid", "delivery_acknowledged",
                    evidence={"delivery_id": value},
                    delivery_verifier=lambda _: True,
                )

    def test_malformed_states_and_evidence_return_domain_error(self):
        for value in (None, [], {}, 1, True):
            with self.subTest(state=repr(value)):
                with self.assertRaises(SignalEntitlementError):
                    advance_signal_entitlement(value, "offer_issued")
                with self.assertRaises(SignalEntitlementError):
                    commercial_flags(value)
        for value in ([], "", False, 0):
            with self.subTest(evidence=repr(value)), self.assertRaises(SignalEntitlementError):
                advance_signal_entitlement("offered", "payment_verified", evidence=value)

if __name__ == "__main__":
    unittest.main()
