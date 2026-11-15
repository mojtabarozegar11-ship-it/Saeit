"""Type-integrity regressions for signal entitlement evidence."""
import unittest

from services.mojtaba_signal_entitlement import (
    SignalEntitlementError, advance_signal_entitlement,
)

class SignalEvidenceTypeTests(unittest.TestCase):
    def test_receipt_id_must_be_an_actual_string(self):
        for receipt_id in (123456, b"receipt:2026:0001", True, object()):
            with self.subTest(receipt_id=type(receipt_id).__name__), self.assertRaises(SignalEntitlementError):
                advance_signal_entitlement(
                    "offered", "payment_verified",
                    evidence={"verified": True, "receipt_id": receipt_id},
                )

    def test_delivery_id_must_be_an_actual_string(self):
        for delivery_id in (123456, b"delivery:2026:0001", True, object()):
            with self.subTest(delivery_id=type(delivery_id).__name__), self.assertRaises(SignalEntitlementError):
                advance_signal_entitlement(
                    "paid", "delivery_acknowledged",
                    evidence={"delivery_id": delivery_id},
                )

    def test_canonical_string_evidence_still_transitions(self):
        self.assertEqual(
            advance_signal_entitlement(
                "offered", "payment_verified",
                evidence={"verified": True, "receipt_id": "receipt:2026:0001"},
                payment_verifier=lambda item: item["receipt_id"] == "receipt:2026:0001",
            ),
            "paid",
        )

if __name__ == "__main__":
    unittest.main()
