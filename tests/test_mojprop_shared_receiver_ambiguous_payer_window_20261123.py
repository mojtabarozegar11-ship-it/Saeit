"""Fail-closed invoice attribution under one shared TRON receiver.

These are read-only mock tests: no real customer, DB mutation, payment,
wallet, TRON RPC or network access. Real signer-ownership challenge remains
a separate mandatory prerequisite for fully automated billing.
"""
from datetime import datetime, timezone
from unittest.mock import Mock, patch
from django.test import SimpleTestCase
from prop_firm.starter30_payer_claim_guard import (
    AmbiguousPayerClaim,
    require_unambiguous_payer_claim,
)


class OneReceiverPayerOverlapGuard(SimpleTestCase):
    PAYER = "41" + "1" * 40
    RECEIVER = "T" + "A" * 33
    BLOCK_TIME = datetime(2026, 11, 23, 12, tzinfo=timezone.utc)

    def check(self, *, competing):
        manager = Mock()
        manager.using.return_value.filter.return_value.exclude.return_value.exists.return_value = competing
        with patch(
            "prop_firm.starter30_payer_claim_guard.PropSimulationPayment.objects",
            manager,
        ):
            if competing:
                with self.assertRaisesRegex(
                    AmbiguousPayerClaim, "ambiguous sending-wallet"
                ):
                    require_unambiguous_payer_claim(
                        payment_pk=7,
                        payer_hex41=self.PAYER,
                        recipient=self.RECEIVER,
                        block_time=self.BLOCK_TIME,
                    )
            else:
                self.assertIsNone(require_unambiguous_payer_claim(
                    payment_pk=7,
                    payer_hex41=self.PAYER,
                    recipient=self.RECEIVER,
                    block_time=self.BLOCK_TIME,
                ))
        manager.using.assert_called_once()
        qs = manager.using.return_value
        qs.filter.assert_called_once_with(
            payer_hex41=self.PAYER,
            recipient=self.RECEIVER,
            issued_at__lte=self.BLOCK_TIME,
            expires_at__gt=self.BLOCK_TIME,
        )
        qs.filter.return_value.exclude.assert_called_once_with(pk=7)

    def test_distinct_sender_no_ambiguous_claim_is_not_blocked_by_guard(self):
        self.check(competing=False)

    def test_second_identity_claim_same_sender_window_is_held(self):
        self.check(competing=True)

    def test_missing_sender_never_auto_credits(self):
        with patch("prop_firm.starter30_live.PropSimulationPayment.objects") as manager:
            for payer in (None, ""):
                with self.subTest(payer=payer):
                    with self.assertRaisesRegex(
                        AmbiguousPayerClaim, "wallet ownership is unverified"
                    ):
                        require_unambiguous_payer_claim(
                            payment_pk=7,
                            payer_hex41=payer,
                            recipient=self.RECEIVER,
                            block_time=self.BLOCK_TIME,
                        )
            manager.using.assert_not_called()

    def test_live_source_not_silently_modified_before_release(self):
        import inspect
        from prop_firm import starter30_live
        source = inspect.getsource(starter30_live._settle_verified_invoice)
        self.assertNotIn("require_unambiguous_payer_claim(", source)

    def test_guard_has_no_save_or_create_calls(self):
        import inspect
        source = inspect.getsource(require_unambiguous_payer_claim)
        self.assertNotIn(".save(", source)
        self.assertNotIn(".create(", source)
        self.assertIn(".exclude(pk=payment_pk)", source)
        self.assertIn("expires_at__gt=block_time", source)
        self.assertIn("issued_at__lte=block_time", source)


if __name__ == "__main__":
    import unittest
    unittest.main()
