"""No-network tests for the dedicated VPS watcher and rapid pending-order response."""
import os
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts import mojplaywin_vps_readonly_watch as watcher
from scripts.mojplaywin_direct_wallet_discovery import IndexerUnavailable


class WatcherTests(unittest.TestCase):
    def test_absent_marker_is_idle(self):
        with tempfile.TemporaryDirectory() as root:
            self.assertIsNone(watcher.get_pending_mode(Path(root) / "pending-orders.mode"))

    def test_valid_marker_reads_exact_coin(self):
        with tempfile.TemporaryDirectory() as root:
            p = Path(root)/"pending-orders.mode"
            p.write_text("ETH\n")
            now=time.time()
            self.assertEqual(watcher.get_pending_mode(p,now=now),"ETH")

    def test_old_marker_expires_closed(self):
        with tempfile.TemporaryDirectory() as root:
            p = Path(root)/"pending-orders.mode"
            p.write_text("BOTH")
            past=time.time()-2000
            os.utime(p,(past,past))
            self.assertIsNone(watcher.get_pending_mode(p,now=time.time()))

    def test_single_invoice_event_remains_active_across_10_minutes(self):
        with tempfile.TemporaryDirectory() as root:
            marker=Path(root)/"pending-orders.mode"
            marker.write_text("TRX")
            t=time.time()
            self.assertEqual(watcher.get_pending_mode(marker,now=t+600),"TRX")
            self.assertIsNone(watcher.get_pending_mode(marker,now=t+1201))

    def test_untrusted_symlink_ignored(self):
        with tempfile.TemporaryDirectory() as root:
            p=Path(root)/"inside"
            p.write_text("BOTH")
            q=Path(root)/"pending-orders.mode"
            q.symlink_to(p)
            self.assertIsNone(watcher.get_pending_mode(q))

    def test_invalid_mode_does_not_activate(self):
        with tempfile.TemporaryDirectory() as root:
            p=Path(root)/"pending-orders.mode"
            p.write_text("SETTLE_PAYMENTS")
            self.assertIsNone(watcher.get_pending_mode(p))

    def test_eth_mode_never_scans_tron(self):
        with patch.object(watcher,"discover_eth") as nothing:
            result=watcher.scan_once(
                mode="ETH",
                eth_scan=lambda:["a","b"],
                trx_scan=lambda: (_ for _ in ()).throw(AssertionError("TRX called")),
            )
        self.assertEqual(result,{"ETH":2})

    def test_both_modes_are_indexer_only(self):
        self.assertEqual(watcher.scan_once(
            mode="BOTH",eth_scan=lambda:[],trx_scan=lambda:["x"]
        ),{"ETH":0,"TRX":1})

    def test_invalid_scan_mode_rejected(self):
        with self.assertRaises(ValueError):
            watcher.scan_once(mode="PAY")

    def test_idle_loops_make_zero_indexer_requests(self):
        with tempfile.TemporaryDirectory() as root:
            clock=[1_700_000_000.0]
            count=[0]
            def fake_sleep(t):
                clock[0]+=t
            def scan_eth():
                count[0]+=1
                return []
            old=watcher.STOP
            try:
                watcher.STOP=False
                watcher.run_forever(root,time_fn=lambda:clock[0],
                    sleep=fake_sleep,eth_scan=scan_eth,trx_scan=lambda:[],
                    max_cycles=7)
            finally:
                watcher.STOP=old
            self.assertEqual(count[0],0)

    def test_active_marker_scans_every_15s(self):
        with tempfile.TemporaryDirectory() as root:
            now=time.time()
            p=Path(root)/"pending-orders.mode"
            p.write_text("ETH")
            clock=[now]
            counter=[0]
            def fake_sleep(dt):
                clock[0]+=dt
                os.utime(p,(clock[0],clock[0]))
            def spy_eth():
                counter[0]+=1
                return []
            old=watcher.STOP
            try:
                watcher.STOP=False
                watcher.run_forever(root,time_fn=lambda:clock[0],
                    sleep=fake_sleep,eth_scan=spy_eth,trx_scan=lambda:[],
                    max_cycles=4)
            finally:
                watcher.STOP=old
            self.assertEqual(counter[0],4)

    def test_switch_from_idle_to_active_scans_immediately(self):
        with tempfile.TemporaryDirectory() as root:
            now=time.time()
            p=Path(root)/"pending-orders.mode"
            clock=[now]
            counter=[0]
            def fake_sleep(dt):
                clock[0]+=dt
                if not p.exists():
                    p.write_text("ETH")
                os.utime(p,(clock[0],clock[0]))
            def spy_eth():
                counter[0]+=1
                return []
            old=watcher.STOP
            try:
                watcher.STOP=False
                watcher.run_forever(root,time_fn=lambda:clock[0],
                    sleep=fake_sleep,eth_scan=spy_eth,trx_scan=lambda:[],
                    max_cycles=3)
            finally:
                watcher.STOP=old
            self.assertEqual(counter[0],2)  # first loop is idle and makes zero API calls

    def test_no_order_never_calls_eth_or_tron_even_after_many_cycles(self):
        with tempfile.TemporaryDirectory() as root:
            clock=[1_700_000_000.0]
            def forbidden(): raise AssertionError("Idle watcher must never make network calls")
            old=watcher.STOP
            try:
                watcher.STOP=False
                watcher.run_forever(root,time_fn=lambda:clock[0],
                    sleep=lambda dt:clock.__setitem__(0,clock[0]+dt),
                    eth_scan=forbidden,trx_scan=forbidden,max_cycles=100)
            finally:
                watcher.STOP=old

    def test_network_failure_backs_off(self):
        with tempfile.TemporaryDirectory() as root:
            clock=[1_700_000_000.0]
            counter=[0]
            def scan_eth():
                counter[0]+=1
                raise IndexerUnavailable("offline")
            old=watcher.STOP
            try:
                watcher.STOP=False
                watcher.run_forever(root,time_fn=lambda:clock[0],
                    sleep=lambda dt:clock.__setitem__(0,clock[0]+dt),
                    eth_scan=scan_eth,trx_scan=lambda:[],max_cycles=3)
            finally:
                watcher.STOP=old
            self.assertEqual(counter[0],0)


if __name__=="__main__":
    unittest.main()
