"""Deterministic unit tests for staging-only direct-wallet fiat quotes."""
import importlib.util
from pathlib import Path
import sys
import unittest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
import mojplaywin_direct_wallet_invoice as m

NOW = 1791950000
ETH_FROM = "0x" + "a" * 40
TRON_FROM = "THFNU1iEXHd71WjEgjqUksd2UnMg2pUi73"


class DirectWalletQuoteTests(unittest.TestCase):
    def prepare(self, asset="ETH", sender=ETH_FROM, **changes):
        price = "3000" if asset == "ETH" else "0.30"
        args = dict(
            order_id=9001,
            customer_id=101,
            asset=asset,
            rate=m.SpotRate(asset, price, "coingecko", NOW - 30),
            expected_sender=sender,
            sender_proof_verified=True,
            now_epoch=NOW,
            invoice_dust=9,
            reserve_amount=lambda chain, address, amount, order_id: True,
        )
        args.update(changes)
        return args

    def test_eth_quote_amount_and_destination(self):
        invoice=m.build_direct_invoice(**self.prepare())
        self.assertEqual(invoice.recipient,m.NETWORKS["ETH"]["recipient"])
        self.assertEqual(invoice.amount_smallest_units,2500000000000000+9)
        self.assertEqual(invoice.expires_at_epoch,NOW+600)
        self.assertTrue(m.can_submit_transaction(invoice,NOW+1))
        self.assertFalse(m.can_submit_transaction(invoice,NOW+601))

    def test_trx_quote_amount_and_destination(self):
        invoice=m.build_direct_invoice(**self.prepare(asset="TRX",sender=TRON_FROM))
        self.assertEqual(invoice.amount_smallest_units,25000000+9)
        self.assertEqual(invoice.recipient,m.TRX_RECEIVER if hasattr(m,"TRX_RECEIVER") else m.NETWORKS["TRX"]["recipient"])

    def test_unverified_sender_blocks_checkout(self):
        with self.assertRaises(m.InvoiceError):
            m.build_direct_invoice(**self.prepare(sender_proof_verified=False))

    def test_missing_sender_blocks_checkout(self):
        with self.assertRaises(m.InvoiceError):
            m.build_direct_invoice(**self.prepare(expected_sender=""))

    def test_stale_rate_blocks_checkout(self):
        rate=m.SpotRate("ETH","3000","coingecko",NOW-200)
        with self.assertRaises(m.InvoiceError):
            m.build_direct_invoice(**self.prepare(rate=rate))

    def test_future_rate_blocks_checkout(self):
        rate=m.SpotRate("ETH","3000","coingecko",NOW+4)
        with self.assertRaises(m.InvoiceError):
            m.build_direct_invoice(**self.prepare(rate=rate))

    def test_untrusted_rate_source_blocks_checkout(self):
        rate=m.SpotRate("ETH","3000","buyer_supplied",NOW-1)
        with self.assertRaises(m.InvoiceError):
            m.build_direct_invoice(**self.prepare(rate=rate))

    def test_zero_rate_blocks_checkout(self):
        rate=m.SpotRate("ETH","0","coingecko",NOW-1)
        with self.assertRaises(m.InvoiceError):
            m.build_direct_invoice(**self.prepare(rate=rate))

    def test_infinite_rate_blocks_checkout(self):
        rate=m.SpotRate("ETH","NaN","coingecko",NOW-1)
        with self.assertRaises(m.InvoiceError):
            m.build_direct_invoice(**self.prepare(rate=rate))

    def test_dust_outside_limit_blocks_checkout(self):
        with self.assertRaises(m.InvoiceError):
            m.build_direct_invoice(**self.prepare(invoice_dust=0))

    def test_existing_amount_blocks_checkout(self):
        with self.assertRaises(m.InvoiceError):
            m.build_direct_invoice(**self.prepare(reserve_amount=lambda *args: False))

    def test_rate_asset_mismatch_blocks_checkout(self):
        rate=m.SpotRate("TRX","0.30","coingecko",NOW-1)
        with self.assertRaises(m.InvoiceError):
            m.build_direct_invoice(**self.prepare(rate=rate))

    def test_wrong_network_sender_format_blocks_checkout(self):
        with self.assertRaises(m.InvoiceError):
            m.build_direct_invoice(**self.prepare(expected_sender=TRON_FROM))

    def test_unsupported_asset_blocks_checkout(self):
        with self.assertRaises(m.InvoiceError):
            m.build_direct_invoice(**self.prepare(asset="USDT"))

    def test_too_long_sender_blocks_checkout(self):
        with self.assertRaises(m.InvoiceError):
            m.build_direct_invoice(**self.prepare(expected_sender="0x"+"e"*240))


if __name__=="__main__":
    unittest.main()
