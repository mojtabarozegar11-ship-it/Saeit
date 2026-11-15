"""Trusted verifier callbacks are mandatory for signal state changes."""
import unittest

from services.mojtaba_signal_entitlement import (
    SignalEntitlementError, advance_signal_entitlement,
)


class SignalTrustedVerifierTests(unittest.TestCase):
    def test_claimed_verified_flag_cannot_bypass_payment_verifier(self):
        with self.assertRaises(SignalEntitlementError):
            advance_signal_entitlement(
                "offered", "payment_verified",
                evidence={"verified": True, "receipt_id": "receipt:2026:0001"},
            )

    def test_verifier_must_return_actual_boolean_true(self):
        for result in (False, 1, "true", None):
            with self.subTest(result=result), self.assertRaises(SignalEntitlementError):
                advance_signal_entitlement(
                    "offered", "payment_verified",
                    evidence={"verified": True, "receipt_id": "receipt:2026:0001"},
                    payment_verifier=lambda _: result,
                )

    def test_delivery_verifier_is_required_even_for_a_valid_reference(self):
        with self.assertRaises(SignalEntitlementError):
            advance_signal_entitlement(
                "paid", "delivery_acknowledged",
                evidence={"delivery_id": "delivery:2026:0001"},
            )
        self.assertEqual(
            advance_signal_entitlement(
                "paid", "delivery_acknowledged",
                evidence={"delivery_id": "delivery:2026:0001"},
                delivery_verifier=lambda _: True,
            ),
            "delivered",
        )


if __name__ == "__main__":
    unittest.main()
