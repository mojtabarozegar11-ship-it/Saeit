"""No-funds, no-production tests for the private TRON Mainnet canary."""
from __future__ import annotations

import json
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from scripts import mpw_trx_private_canary_20261023 as canary
from services.mpw_trx_walletless_core import PaymentHold
from services.mpw_walletless_commercial_intent import _commercial_db


class PrivateCanaryIsolationTests(unittest.TestCase):
    def setUp(self):
        self.config = SimpleNamespace(
            DEBUG=False,
            MPW_COMMERCE_RELEASE_READY=True,
            MPW_COMMERCE_DOWNLOADS_ENABLED=True,
            MPW_WALLETLESS_TRX_PUBLIC_ENABLED=False,
            MPW_WALLETLESS_TRX_MERCHANT_CANARY_PASSED=False,
        )
        self.db = SimpleNamespace(vendor="mysql", alias="default")

    def test_private_reservation_only_does_not_modify_actual_public_flags(self):
        with self.assertRaises(PaymentHold):
            _commercial_db(self.config, self.db)
        scoped = canary.scoped_canary_settings(self.config, self.db)
        _commercial_db(scoped, self.db)
        self.assertIs(scoped.MPW_WALLETLESS_TRX_PUBLIC_ENABLED, True)
        self.assertIs(scoped.MPW_WALLETLESS_TRX_MERCHANT_CANARY_PASSED, True)
        self.assertIs(self.config.MPW_WALLETLESS_TRX_PUBLIC_ENABLED, False)
        self.assertIs(self.config.MPW_WALLETLESS_TRX_MERCHANT_CANARY_PASSED, False)
        with self.assertRaises(PaymentHold):
            _commercial_db(self.config, self.db)

    def test_cannot_run_private_bypass_with_public_or_financial_backend_open(self):
        for field in ("MPW_WALLETLESS_TRX_PUBLIC_ENABLED",
                      "MPW_WALLETLESS_TRX_MERCHANT_CANARY_PASSED"):
            setattr(self.config, field, True)
            with self.subTest(field=field), self.assertRaises(PaymentHold):
                canary.scoped_canary_settings(self.config, self.db)
            setattr(self.config, field, False)
        self.config.MPW_COMMERCE_DOWNLOADS_ENABLED = False
        with self.assertRaises(PaymentHold):
            canary.scoped_canary_settings(self.config, self.db)
        self.config.MPW_COMMERCE_DOWNLOADS_ENABLED = True
        with self.assertRaises(PaymentHold):
            canary.scoped_canary_settings(self.config, SimpleNamespace(vendor="sqlite",alias="default"))

    def test_exact_server_configured_buyer_and_product_only(self):
        with patch.dict("os.environ", {"MPW_TRX_CANARY_BUYER_ID": "42",
                                       "MPW_TRX_CANARY_PRODUCT_ID": "779"}):
            self.assertEqual(canary._configured_ids(), (42, 779))
        for value in ("", "0", "-1", "42x", "000000000000000000001", "2147483648"):
            with patch.dict("os.environ", {"MPW_TRX_CANARY_BUYER_ID": value,
                                           "MPW_TRX_CANARY_PRODUCT_ID": "779"}):
                with self.subTest(buyer=value), self.assertRaises(PaymentHold):
                    canary._configured_ids()

    def test_private_receipt_is_atomic_owner_private_and_tamper_checked(self):
        with tempfile.TemporaryDirectory() as d, patch.object(canary, "RECEIPTS", Path(d) / "receipts"):
            record = {"network": "tron-mainnet", "invoice_id": 412, "amount_sun": 123456}
            path = canary._write_receipt(412, record)
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            self.assertEqual(canary._read_receipt(412), record)
            with self.assertRaises(FileExistsError):
                canary._write_receipt(412, record)
            path.write_text('{"invoice_id":412,"network":"shasta"}', encoding="utf8")
            with self.assertRaises(PaymentHold):
                canary._read_receipt(412)

    def test_private_file_evidence_must_be_real_and_not_symlink(self):
        with tempfile.TemporaryDirectory() as d:
            original = Path(d) / "product.zip"
            original.write_bytes(b"PK\x03\x04real-small-test-file")
            digest, length = canary._asset_hash(original)
            self.assertEqual(length, original.stat().st_size)
            self.assertEqual(len(digest), 64)
            symlink = Path(d) / "link.zip"
            symlink.symlink_to(original)
            with self.assertRaises(PaymentHold):
                canary._asset_hash(symlink)
            original.write_bytes(b"")
            with self.assertRaises(PaymentHold):
                canary._asset_hash(original)


if __name__ == "__main__":
    unittest.main()
