"""Regression tests for the single owner-approved TRX receive wallet source."""
from __future__ import annotations

import unittest

from mpw_commerce.invoicing import RECEIVERS
from services.mojtaba_tron_owner_receiver import approved_recipient


OWNER_RECEIVER = "THFNU1iEXHd71WjEgjqUksd2UnMg2pUi73"


class SingleReceiveWalletSourceTests(unittest.TestCase):
    def test_commerce_invoice_receiver_is_owner_qr_source(self):
        network, recipient, decimals = RECEIVERS["TRX"]
        self.assertEqual(network, "tron-mainnet")
        self.assertEqual(decimals, 6)
        self.assertEqual(recipient, OWNER_RECEIVER)
        self.assertEqual(recipient, approved_recipient())

    def test_only_native_trx_receiver_is_exposed_by_commerce_registry(self):
        self.assertEqual(
            [value[1] for asset, value in RECEIVERS.items() if asset == "TRX"],
            [OWNER_RECEIVER],
        )


if __name__ == "__main__":
    unittest.main()
