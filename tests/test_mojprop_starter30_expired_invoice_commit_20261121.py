"""No live DB/network: prove expired invoice writes commit before buyer rejection."""
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone as utc_timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase, override_settings

from config.mojprop_db_router import MOJPROP_DB_ALIAS
from prop_firm import starter30_live as m


RELEASE = {
    "MPW_MOJPROP_DB_ALIAS_ENABLED": True,
    "MPW_MOJPROP_DEPLOYMENT_ENV": "production",
    "MPW_MOJPROP_PRODUCTION_RELEASE_APPROVED": True,
    "MPW_MOJPROP_TRX_RELEASE_ENABLED": True,
    "MPW_MOJPROP_TRX_RPC_ATTESTED": True,
}


@override_settings(**RELEASE)
class Starter30ExpiryCommitTests(SimpleTestCase):
    def setUp(self):
        self.now = datetime(2026, 11, 21, 12, 0, tzinfo=utc_timezone.utc)
        self.txid = "a" * 64
        self.receiver = "verified-owner-receiver"
        self.payment = MagicMock()
        self.payment.status = m.PropSimulationPayment.Status.AWAITING
        self.payment.expires_at = self.now - timedelta(seconds=1)
        self.payment.issued_at = self.now - timedelta(days=1)
        self.payment.txid = ""
        self.transfer = SimpleNamespace(
            tx_hash=self.txid,
            network=m.NETWORK,
            sender="test-sender",
            recipient=self.receiver,
            amount_sun=m.NATIVE_AMOUNT_SUN,
            block_time=self.now,  # strictly outside the expired invoice window
            solidified=True,
        )
        self.events = []
        self.payment.save.side_effect = lambda **kw: self.events.append("saved")
        self.mock_manager = self.enterContext(
            patch("prop_firm.starter30_live.PropSimulationPayment.objects")
        )
        self.lookup = (
            self.mock_manager.using.return_value
            .select_for_update.return_value
            .select_related.return_value
            .get
        )
        self.lookup.side_effect = self._locked_row
        self.mock_atomic = self.enterContext(
            patch("prop_firm.starter30_live.transaction.atomic", side_effect=self._atomic)
        )
        self.mock_clock = self.enterContext(
            patch("prop_firm.starter30_live.timezone.now", side_effect=self._clock)
        )
        self.mock_pair = self.enterContext(
            patch("prop_firm.starter30_live._provider_pair", return_value=(object(), object()))
        )
        self.mock_rpc = self.enterContext(
            patch("prop_firm.starter30_live.query_solidified_transfer", return_value=self.transfer)
        )
        self.mock_recipient = self.enterContext(
            patch("prop_firm.starter30_live.approved_recipient", return_value=self.receiver)
        )
        self.mock_accounts = self.enterContext(
            patch("prop_firm.starter30_live.PropSimulationAccount")
        )

    def _locked_row(self, **kwargs):
        self.events.append("row_locked")
        return self.payment

    def _clock(self):
        self.events.append("clock_checked")
        return self.now

    @contextmanager
    def _atomic(self, *, using):
        self.assertEqual(using, MOJPROP_DB_ALIAS)
        before_status = self.payment.status
        self.events.append("atomic_enter")
        try:
            yield
        except BaseException:
            # Simulates a database rollback on a raised exception.
            self.payment.status = before_status
            self.events.append("rollback")
            raise
        else:
            self.events.append("commit")

    def _settle(self):
        return m.settle_invoice(invoice_ref="invoice-1", txid=self.txid)

    def test_expired_invoice_is_committed_before_client_exception(self):
        with self.assertRaisesRegex(m.Starter30PaymentRejected, "invoice has expired"):
            self._settle()
        self.assertEqual(self.payment.status, m.PropSimulationPayment.Status.EXPIRED)
        self.payment.save.assert_called_once_with(
            using=MOJPROP_DB_ALIAS, update_fields=["status", "updated_at"]
        )
        self.assertEqual(
            self.events, ["atomic_enter", "row_locked", "clock_checked", "saved", "commit"]
        )
        self.mock_accounts.assert_not_called()
        self.mock_rpc.assert_called()
        self.assertEqual(self.mock_rpc.call_count, 2)

    def test_expiry_clock_is_read_after_locked_row(self):
        with self.assertRaises(m.Starter30PaymentRejected):
            self._settle()
        self.assertLess(self.events.index("row_locked"), self.events.index("clock_checked"))

    def test_repeated_expired_attempt_does_not_write_again(self):
        with self.assertRaisesRegex(m.Starter30PaymentRejected, "invoice has expired"):
            self._settle()
        self.payment.save.reset_mock()
        with self.assertRaisesRegex(m.Starter30PaymentRejected, "not awaiting"):
            self._settle()
        self.payment.save.assert_not_called()
        self.mock_accounts.assert_not_called()

    def test_out_of_invoice_transfer_window_rolls_back_and_does_not_expire_early(self):
        self.payment.expires_at = self.now + timedelta(hours=1)
        self.transfer.block_time = self.payment.issued_at - timedelta(seconds=1)
        with self.assertRaisesRegex(m.Starter30PaymentRejected, "outside the invoice window"):
            self._settle()
        self.assertEqual(self.payment.status, m.PropSimulationPayment.Status.AWAITING)
        self.payment.save.assert_not_called()
        self.assertIn("rollback", self.events)
        self.assertNotIn("commit", self.events)
        self.mock_accounts.assert_not_called()

    def test_unexpected_save_failure_does_not_claim_committed_expiry(self):
        self.payment.save.side_effect = RuntimeError("database save failed")
        with self.assertRaisesRegex(RuntimeError, "database save failed"):
            self._settle()
        self.assertEqual(self.payment.status, m.PropSimulationPayment.Status.AWAITING)
        self.assertIn("rollback", self.events)
        self.assertNotIn("commit", self.events)
        self.mock_accounts.assert_not_called()

    def test_already_paid_idempotent_reference_preserves_existing_behavior(self):
        self.payment.status = m.PropSimulationPayment.Status.PAID
        self.payment.txid = self.txid
        with patch("prop_firm.starter30_live._paid_result", return_value={"status": "paid"}) as paid:
            result = self._settle()
        self.assertEqual(result, {"status": "paid"})
        paid.assert_called_once_with(self.payment)
        self.payment.save.assert_not_called()
        self.assertIn("commit", self.events)
        self.mock_accounts.assert_not_called()

    def test_on_time_trx_is_credited_even_if_reconciled_after_expiry(self):
        # The customer's transfer landed before the deadline; the proof may
        # arrive after expiry. Do not confiscate or silently expire that payment.
        self.transfer.block_time = self.now - timedelta(minutes=5)
        self.payment.payer_hex41 = "41" + "0" * 40
        self.payment.payment_ref = "PAY-test"
        owner = MagicMock()
        owner.invoice_ref = "invoice-1"
        owner.identity = MagicMock()
        self.payment.invoice_owner = owner
        self.mock_manager.using.return_value.filter.return_value.exists.return_value = False
        # A MagicMock model constructor does not populate fields from kwargs.
        self.mock_accounts.return_value.account_ref = "MOJPROP30-ACC-valid"
        with patch(
            "prop_firm.starter30_live.hex_to_tron_address",
            return_value=self.transfer.sender,
        ), patch(
            "prop_firm.starter30_live._token",
            return_value="MOJPROP30-ACC-valid",
        ):
            result = self._settle()
        self.assertEqual(result["status"], "paid")
        self.assertEqual(result["invoice_ref"], "invoice-1")
        self.assertEqual(result["account_ref"], "MOJPROP30-ACC-valid")
        self.assertEqual(result["txid"], self.txid)
        self.assertEqual(self.payment.status, m.PropSimulationPayment.Status.PAID)
        self.assertEqual(self.payment.txid, self.txid)
        self.assertTrue(owner.settlement_verified)
        self.assertEqual(owner.settlement_reference, self.txid)
        self.mock_accounts.assert_called_once()
        self.mock_accounts.return_value.save.assert_called_once_with(
            using=MOJPROP_DB_ALIAS
        )
        self.assertIn("commit", self.events)
        self.assertNotIn("rollback", self.events)

    def test_future_or_post_expiry_transfer_is_never_credited(self):
        self.transfer.block_time = self.now + timedelta(seconds=10)
        with self.assertRaisesRegex(m.Starter30PaymentRejected, "invoice has expired"):
            self._settle()
        self.payment.save.assert_called_once()
        self.assertEqual(self.payment.status, m.PropSimulationPayment.Status.EXPIRED)
        self.mock_accounts.assert_not_called()
