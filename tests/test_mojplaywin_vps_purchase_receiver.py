"""Localhost-only tests of signed purchase events waking the VPS marker."""
import json
from pathlib import Path
import sys
import tempfile
import threading
import time
from urllib.error import HTTPError
from urllib.request import Request, urlopen
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.mojplaywin_purchase_events import make_event, signed_message
from scripts.mojplaywin_vps_purchase_receiver import (
    LocalOnlyHTTPServer, EventHTTPHandler, ALLOWED_PATH,
)

KEY = b"automated-test-not-a-production-secret-" * 2


class VPSPurchaseReceiverTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name) / "watch"
        self.home.mkdir(mode=0o700)
        self.http = LocalOnlyHTTPServer(
            ("127.0.0.1", 0), EventHTTPHandler,
            home=self.home, signing_key=KEY,
        )
        self.thread = threading.Thread(target=self.http.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.http.server_close)
        self.addCleanup(self.http.shutdown)
        self.port = self.http.server_address[1]

    def send(self, *, action="invoice_open", asset="ETH", invoice=11,
             order=72, tamper_signature=False):
        stamp = int(time.time())
        event = make_event(
            action, invoice, order, asset, stamp + 600,
            now_epoch=stamp,
        )
        data, signature = signed_message(event, KEY)
        if tamper_signature:
            signature = "sha256=" + "0" * 64
        request = Request(
            "http://127.0.0.1:" + str(self.port) + ALLOWED_PATH,
            data=data, method="POST",
            headers={
                "Content-Type": "application/json",
                "X-MPW-Signature": signature,
            },
        )
        with urlopen(request, timeout=2) as response:
            return response.status, json.loads(response.read().decode())

    def test_real_loopback_event_creates_watch_marker(self):
        code, body = self.send()
        self.assertEqual(code, 200)
        self.assertEqual(body["state"], "watching")
        self.assertEqual((self.home / "pending-orders.mode").read_text(), "ETH\n")

    def test_close_last_order_stops_watch(self):
        self.send()
        code, body = self.send(action="invoice_closed")
        self.assertEqual(code, 200)
        self.assertEqual(body["state"], "idle")
        self.assertFalse((self.home / "pending-orders.mode").exists())

    def test_two_simultaneous_coins_then_close_one(self):
        self.send(invoice=11, asset="ETH")
        self.send(invoice=12, order=73, asset="TRX")
        self.assertEqual((self.home / "pending-orders.mode").read_text(), "BOTH\n")
        self.send(action="invoice_closed", invoice=11, asset="ETH")
        self.assertEqual((self.home / "pending-orders.mode").read_text(), "TRX\n")

    def test_wrong_hmac_cannot_wake(self):
        with self.assertRaises(HTTPError) as caught:
            self.send(tamper_signature=True)
        self.assertEqual(caught.exception.code, 403)
        self.assertFalse((self.home / "pending-orders.mode").exists())

    def test_plain_get_discloses_no_state(self):
        with self.assertRaises(HTTPError) as caught:
            urlopen("http://127.0.0.1:" + str(self.port) + ALLOWED_PATH, timeout=2)
        self.assertEqual(caught.exception.code, 404)

    def test_no_public_bind_allowed(self):
        with self.assertRaises(ValueError):
            LocalOnlyHTTPServer(
                ("0.0.0.0", 0), EventHTTPHandler, home=self.home, signing_key=KEY,
            )

    def test_short_hmac_key_refused(self):
        with self.assertRaises(ValueError):
            LocalOnlyHTTPServer(
                ("127.0.0.1", 0), EventHTTPHandler,
                home=self.home, signing_key=b"short",
            )

    def test_invalid_content_type_blocks(self):
        stamp = int(time.time())
        event = make_event("invoice_open", 99, 72, "ETH", stamp + 600, now_epoch=stamp)
        data, signature = signed_message(event, KEY)
        req = Request(
            "http://127.0.0.1:" + str(self.port) + ALLOWED_PATH,
            data=data, method="POST",
            headers={"Content-Type": "text/plain", "X-MPW-Signature": signature},
        )
        with self.assertRaises(HTTPError) as caught:
            urlopen(req, timeout=2)
        self.assertEqual(caught.exception.code, 415)
