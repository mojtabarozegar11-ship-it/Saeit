"""Security regressions for the single agent's receipt and delivery boundaries.

These fixtures only simulate adapters; they are not independent chain, buyer,
or storage evidence and do not authorize live sales.
"""
import unittest

from services.mojtaba_signal_entitlement import (
    SignalEntitlementError, advance_signal_entitlement,
)


PAYMENT = {"verified": True, "receipt_id": "receipt:2026:0001"}
DELIVERY = {"delivery_id": "delivery:2026:0001"}


class IndependentSignalEntitlementEvidenceTests(unittest.TestCase):
    def pay(self, *, evidence=None, verifier=None):
        return advance_signal_entitlement(
            "offered", "payment_verified",
            evidence=PAYMENT if evidence is None else evidence,
            payment_verifier=verifier,
        )

    def deliver(self, *, evidence=None, verifier=None):
        return advance_signal_entitlement(
            "paid", "delivery_acknowledged",
            evidence=DELIVERY if evidence is None else evidence,
            delivery_verifier=verifier,
        )

    def test_caller_claim_verified_true_cannot_mark_an_order_paid(self):
        with self.assertRaisesRegex(SignalEntitlementError, "trusted server-side"):
            self.pay()

    def test_caller_supplied_delivery_id_cannot_mark_order_delivered(self):
        with self.assertRaisesRegex(SignalEntitlementError, "trusted server-side"):
            self.deliver()

    def test_callback_rejection_does_not_advance_paid_entitlement(self):
        with self.assertRaisesRegex(SignalEntitlementError, "rejected"):
            self.pay(verifier=lambda evidence: False)

    def test_callback_rejection_does_not_advance_delivery(self):
        with self.assertRaisesRegex(SignalEntitlementError, "rejected"):
            self.deliver(verifier=lambda evidence: False)

    def test_callback_integer_one_is_not_verified_boolean(self):
        for result in (1, "true", {"verified": True}, None):
            with self.subTest(result=result), self.assertRaises(SignalEntitlementError):
                self.pay(verifier=lambda evidence: result)

    def test_callback_exception_blocks_paid_state(self):
        def failing(_evidence):
            raise OSError("database unavailable")
        with self.assertRaisesRegex(SignalEntitlementError, "could not complete"):
            self.pay(verifier=failing)

    def test_callback_exception_blocks_claimed_delivery(self):
        def failing(_evidence):
            raise ConnectionError("storage unavailable")
        with self.assertRaisesRegex(SignalEntitlementError, "could not complete"):
            self.deliver(verifier=failing)

    def test_noncallable_verifier_never_approves_payment(self):
        for verifier in (True, "trusted", {}, None):
            with self.subTest(verifier=verifier), self.assertRaises(SignalEntitlementError):
                self.pay(verifier=verifier)

    def test_valid_simulated_server_payment_adapter_can_advance(self):
        checked = []
        def verify_stored_receipt(evidence):
            checked.append(evidence["receipt_id"])
            return evidence["receipt_id"] == "receipt:2026:0001"
        self.assertEqual(self.pay(verifier=verify_stored_receipt), "paid")
        self.assertEqual(checked, ["receipt:2026:0001"])

    def test_valid_simulated_delivery_adapter_can_advance(self):
        self.assertEqual(
            self.deliver(verifier=lambda evidence: evidence["delivery_id"] == "delivery:2026:0001"),
            "delivered",
        )

    def test_missing_receipt_prevents_invoking_verifier(self):
        checked = []
        with self.assertRaises(SignalEntitlementError):
            self.pay(
                evidence={"verified": True, "receipt_id": ""},
                verifier=lambda value: checked.append(value) or True,
            )
        self.assertEqual(checked, [])

    def test_missing_delivery_proof_prevents_invoking_verifier(self):
        checked = []
        with self.assertRaises(SignalEntitlementError):
            self.deliver(
                evidence={"delivery_id": ""},
                verifier=lambda value: checked.append(value) or True,
            )
        self.assertEqual(checked, [])

    def test_caller_bad_verified_value_does_not_invoke_verifier(self):
        checked = []
        with self.assertRaises(SignalEntitlementError):
            self.pay(
                evidence={"verified": 1, "receipt_id": "receipt:2026:0001"},
                verifier=lambda value: checked.append(value) or True,
            )
        self.assertEqual(checked, [])

    def test_payment_adapter_receives_independent_copy_of_mapping(self):
        data = dict(PAYMENT)
        def inspect(value):
            value["receipt_id"] = "spoofed:2026:9999"
            return True
        self.assertEqual(self.pay(evidence=data, verifier=inspect), "paid")
        self.assertEqual(data["receipt_id"], "receipt:2026:0001")

    def test_invalid_delivery_evidence_type_fails_before_adapter(self):
        with self.assertRaises(SignalEntitlementError):
            self.deliver(evidence=[], verifier=lambda x: True)
