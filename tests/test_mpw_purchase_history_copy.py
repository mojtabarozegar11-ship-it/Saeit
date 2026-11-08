"""Isolated, no-network customer status copy contract tests."""
import unittest
from datetime import datetime, timedelta, timezone
from services.mpw_purchase_history_copy import buyer_invoice_action


NOW = datetime(2026, 11, 8, 14, 0, tzinfo=timezone.utc)


class PurchaseHistoryCopyTests(unittest.TestCase):
    def test_paid_and_verified_returns_download(self):
        text = buyer_invoice_action(59, "paid", {"status": "paid", "can_download": True}, NOW, NOW)
        self.assertIn('/download/59/', text)

    def test_reviewed_paid_never_grants_download(self):
        text = buyer_invoice_action(59, "paid", {"status": "review", "can_download": False}, NOW, NOW)
        self.assertIn("requires verification", text)
        self.assertNotIn('/download/', text)

    def test_unproven_paid_never_grants_download(self):
        text = buyer_invoice_action(59, "paid", {"status": "awaiting", "can_download": False}, NOW, NOW)
        self.assertIn("requires verification", text)
        self.assertNotIn('/download/', text)

    def test_active_invoice_only_before_expiry(self):
        text = buyer_invoice_action(53, "awaiting_chain", {"status": "awaiting", "can_download": False}, NOW + timedelta(seconds=1), NOW)
        self.assertIn('/invoice/53/', text)

    def test_expiry_boundary_is_not_payable(self):
        text = buyer_invoice_action(54, "awaiting_chain", {"status": "awaiting", "can_download": False}, NOW, NOW)
        self.assertIn("Invoice expired", text)
        self.assertNotIn('/invoice/', text)

    def test_expired_invoice_retains_safe_support_instruction(self):
        text = buyer_invoice_action(55, "awaiting_chain", {"status": "awaiting", "can_download": False}, NOW - timedelta(days=1), NOW)
        self.assertIn("do not pay again", text)
        self.assertIn("transaction hash", text)

    def test_unsupported_state_does_not_offer_invoice(self):
        text = buyer_invoice_action(59, "cancelled", {"status": "awaiting", "can_download": False}, NOW, NOW)
        self.assertIn("not available", text)
        self.assertNotIn('/invoice/', text)

    def test_spoofed_can_download_without_paid_state_is_refused(self):
        text = buyer_invoice_action(59, "awaiting_chain", {"status": "awaiting", "can_download": True}, NOW, NOW)
        self.assertNotIn('/download/', text)

    def test_paid_proof_does_not_override_nonpaid_intent(self):
        text = buyer_invoice_action(59, "awaiting_chain", {"status": "paid", "can_download": True}, NOW, NOW)
        self.assertNotIn('/download/', text)

    def test_malformed_id_and_status_rejected(self):
        for value in (0, -1, "59", True):
            with self.subTest(value=value), self.assertRaises(ValueError):
                buyer_invoice_action(value, "paid", {"status": "paid", "can_download": True}, NOW, NOW)
        with self.assertRaises(ValueError):
            buyer_invoice_action(59, "paid", None, NOW, NOW)


if __name__ == "__main__":
    unittest.main()
