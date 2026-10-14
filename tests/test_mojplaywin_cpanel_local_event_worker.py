"""No-chain, no-AI tests of event-driven local Unix socket checkout notification."""
import os
from pathlib import Path
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.mojplaywin_purchase_events import make_event, signed_message
from scripts.mojplaywin_cpanel_local_event_worker import (
    run_local_worker, socket_request, SOCKET_BASENAME, LocalEventUnavailable,
)
KEY=b"no-real-purchase-secret-unit-test-"*2


class LocalPurchaseWorkerTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.home=Path(self.temp.name)/"user-0700"
        self.home.mkdir(mode=0o700)
        self.calls=[]
        self.failures=[]

    def start(self, expected_events=1):
        def eth():
            self.calls.append("ETH")
            return []
        def trx():
            self.calls.append("TRX")
            return []
        def worker():
            try:
                run_local_worker(
                    self.home,KEY,eth_scan=eth,trx_scan=trx,
                    stop_after_events=expected_events,
                )
            except BaseException as exc:
                self.failures.append(exc)
        thread=threading.Thread(target=worker,daemon=True)
        thread.start()
        deadline=time.time()+3
        while time.time()<deadline and not (self.home/SOCKET_BASENAME).exists():
            time.sleep(.01)
        self.assertTrue((self.home/SOCKET_BASENAME).exists())
        return thread

    def send(self, action, invoice=51, asset="ETH", order=72):
        stamp=int(time.time())
        e=make_event(action,invoice,order,asset,stamp+600,now_epoch=stamp)
        data,sig=signed_message(e,KEY)
        return socket_request(self.home/SOCKET_BASENAME,data,sig)

    def done(self,thread):
        thread.join(timeout=3)
        self.assertFalse(thread.is_alive())
        self.assertEqual(self.failures,[])

    def test_idle_uses_no_indexer_calls_even_with_open_socket(self):
        thread=self.start()
        time.sleep(.25)
        self.assertEqual(self.calls,[])
        self.assertEqual(self.send("invoice_open"),"delivered")
        self.done(thread)
        self.assertEqual(self.calls,["ETH"])

    def test_close_stops_watch_without_extra_scan(self):
        thread=self.start(expected_events=2)
        self.send("invoice_open")
        self.send("invoice_closed")
        self.done(thread)
        self.assertEqual(self.calls,["ETH"])
        self.assertFalse((self.home/"pending-orders.mode").exists())

    def test_two_invoices_only_required_coins(self):
        thread=self.start(expected_events=3)
        self.send("invoice_open",invoice=51,asset="ETH")
        self.send("invoice_open",invoice=52,asset="TRX",order=73)
        self.assertEqual((self.home/"pending-orders.mode").read_text(),"BOTH\n")
        self.send("invoice_closed",invoice=51,asset="ETH")
        self.done(thread)
        self.assertEqual((self.home/"pending-orders.mode").read_text(),"TRX\n")
        self.assertEqual(self.calls,["ETH","ETH","TRX","TRX"])

    def test_bad_hmac_does_not_wake_or_ack(self):
        thread=self.start()
        stamp=int(time.time())
        message=make_event("invoice_open",12,34,"ETH",stamp+600,now_epoch=stamp)
        body,_=signed_message(message,KEY)
        with self.assertRaises(LocalEventUnavailable):
            socket_request(self.home/SOCKET_BASENAME,body,"sha256="+"0"*64)
        self.assertEqual(self.calls,[])
        self.assertFalse((self.home/"pending-orders.mode").exists())
        self.send("invoice_open")
        self.done(thread)

    def test_missing_worker_refuses_delivery(self):
        stamp=int(time.time())
        e=make_event("invoice_open",6,77,"TRX",stamp+600,now_epoch=stamp)
        body,sig=signed_message(e,KEY)
        with self.assertRaises(OSError):
            socket_request(self.home/SOCKET_BASENAME,body,sig,timeout=.1)
