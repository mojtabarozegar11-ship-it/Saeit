"""Regression tests for fail-closed walletless TRX evidence validation.

Run locally: python -m unittest discover -s tests -p 'test_mpw_walletless_recipient.py'
No network, wallet, transaction, or external payment is performed.
"""
import unittest
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from services.mpw_trx_walletless_core import (
    InvoiceIntent, PaymentHold, SolidifiedTransfer,
    verify_two_source_transfer,
)

NOW = datetime(2026, 11, 13, 12, 0, tzinfo=timezone.utc)
MERCHANT = "T" + "A" * 33
SENDER = "T" + "B" * 33
TX = "a" * 64


def fixture():
    invoice = InvoiceIntent(
        order_id=1, customer_id=2, network="tron-mainnet",
        recipient=MERCHANT, amount_sun=1_000_000,
        usd_total=Decimal("1"), issued_at=NOW,
        expires_at=NOW + timedelta(minutes=10),
        quote_usd_per_trx=Decimal("1"),
    )
    transfer = SolidifiedTransfer(
        source_id="node-1", tx_hash=TX, network="tron-mainnet",
        recipient=MERCHANT, sender=SENDER, amount_sun=1_000_000,
        block_time=NOW + timedelta(minutes=1), solidified=True,
        transfer_contract=True, execution_success=True,
    )
    return invoice, transfer, replace(transfer, source_id="node-2")


class WalletlessRecipientRegression(unittest.TestCase):
    def test_non_string_invoice_recipient_fails_closed(self):
        invoice, first, second = fixture()
        for invalid in (None, 123, [], {}, b"not-an-address", True):
            with self.subTest(value=repr(invalid)):
                with self.assertRaises(PaymentHold):
                    verify_two_source_transfer(
                        replace(invoice, recipient=invalid), first, second,
                        tx_previously_consumed=lambda network, tx: False,
                    )

    def test_valid_independent_evidence_succeeds(self):
        invoice, first, second = fixture()
        self.assertEqual(
            verify_two_source_transfer(
                invoice, first, second,
                tx_previously_consumed=lambda network, tx: False,
            ), (TX, SENDER),
        )

    def test_consumed_transaction_fails_closed(self):
        invoice, first, second = fixture()
        with self.assertRaises(PaymentHold):
            verify_two_source_transfer(
                invoice, first, second,
                tx_previously_consumed=lambda network, tx: True,
            )

    def test_duplicate_provider_fails_closed(self):
        invoice, first, _ = fixture()
        with self.assertRaises(PaymentHold):
            verify_two_source_transfer(
                invoice, first, replace(first),
                tx_previously_consumed=lambda network, tx: False,
            )


if __name__ == "__main__":
    unittest.main()
