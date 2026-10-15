"""Pure deterministic event-to-wallet-watch tests; no network, AI model or blockchain."""
import json
import pathlib
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from scripts.mojplaywin_purchase_events import (
    EventRejected, make_event, signed_message, verify_event, handle_verified_event,
)

KEY = b"vps-event-test-secret-only-" * 3
NOW = 1_800_000_000


class PurchaseWatchEventTests(unittest.TestCase):
    def message(self, action="invoice_open", invoice=10, order=72,
                asset="ETH", expires=None):
        if expires is None: expires=NOW + 600
        event=make_event(action,invoice,order,asset,expires,now_epoch=NOW)
        body,signature=signed_message(event,KEY)
        return body,signature

    def test_authentic_event_is_accepted(self):
        body,sig=self.message()
        parsed=verify_event(body,sig,KEY,now_epoch=NOW)
        self.assertEqual(parsed["invoice"],10)
        self.assertEqual(parsed["asset"],"ETH")

    def test_wrong_signature_blocks(self):
        body,sig=self.message()
        with self.assertRaises(EventRejected):
            verify_event(body,"sha256="+"a"*64,KEY,now_epoch=NOW)

    def test_stale_event_blocks(self):
        body,sig=self.message()
        with self.assertRaises(EventRejected):
            verify_event(body,sig,KEY,now_epoch=NOW+1000)

    def test_fake_asset_blocks(self):
        with self.assertRaises(EventRejected):
            make_event("invoice_open",10,72,"USDT",NOW+600,now_epoch=NOW)

    def test_far_future_order_blocks(self):
        with self.assertRaises(EventRejected):
            make_event("invoice_open",10,72,"ETH",NOW+999999,now_epoch=NOW)

    def test_open_wakes_ETH_marker(self):
        with tempfile.TemporaryDirectory() as home:
            body,sig=self.message()
            state=handle_verified_event(body,sig,KEY,home,now_epoch=NOW)
            self.assertEqual(state,{"state":"watching","open_invoices":1,"mode":"ETH"})
            self.assertEqual((pathlib.Path(home)/"pending-orders.mode").read_text(),"ETH\n")

    def test_close_removes_last_marker(self):
        with tempfile.TemporaryDirectory() as home:
            opened=self.message()
            handle_verified_event(*opened,KEY,home,now_epoch=NOW)
            close=self.message("invoice_closed")
            out=handle_verified_event(*close,KEY,home,now_epoch=NOW)
            self.assertEqual(out["state"],"idle")
            self.assertFalse((pathlib.Path(home)/"pending-orders.mode").exists())

    def test_two_open_invoices_aggregate_both_chains(self):
        with tempfile.TemporaryDirectory() as home:
            handle_verified_event(*self.message("invoice_open",10,72,"ETH"),
                                  KEY,home,now_epoch=NOW)
            out=handle_verified_event(*self.message("invoice_open",11,73,"TRX"),
                                      KEY,home,now_epoch=NOW)
            self.assertEqual(out["mode"],"BOTH")
            out=handle_verified_event(*self.message("invoice_closed",10,72,"ETH"),
                                      KEY,home,now_epoch=NOW)
            self.assertEqual(out["mode"],"TRX")
            self.assertEqual((pathlib.Path(home)/"pending-orders.mode").read_text(),"TRX\n")

    def test_replayed_message_blocks_without_mutating_state(self):
        with tempfile.TemporaryDirectory() as home:
            body,sig=self.message()
            handle_verified_event(body,sig,KEY,home,now_epoch=NOW)
            with self.assertRaises(EventRejected):
                handle_verified_event(body,sig,KEY,home,now_epoch=NOW)
            self.assertEqual((pathlib.Path(home)/"pending-orders.mode").read_text(),"ETH\n")

    def test_wrong_invoice_close_cannot_stop_other_order(self):
        with tempfile.TemporaryDirectory() as home:
            handle_verified_event(*self.message(),KEY,home,now_epoch=NOW)
            out=handle_verified_event(*self.message("invoice_closed",10,99,"ETH"),
                                      KEY,home,now_epoch=NOW)
            self.assertEqual(out["mode"],"ETH")

    def test_expired_signal_rejected_at_source_before_network(self):
        with self.assertRaises(EventRejected):
            self.message(expires=NOW-10)

    def test_no_ai_or_network_functions_in_signal_receipt(self):
        with tempfile.TemporaryDirectory() as home:
            body,sig=self.message()
            with patch("urllib.request.urlopen",side_effect=AssertionError("Network called")):
                out=handle_verified_event(body,sig,KEY,home,now_epoch=NOW)
            self.assertEqual(out["open_invoices"],1)


if __name__=="__main__":
    unittest.main()
