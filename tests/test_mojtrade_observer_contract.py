"""Integration contract: the existing real observer code feeds watch-only audit.

Network is never used. Generated OHLC is expressly a test fixture, not market
evidence or an estimate of trading performance.
"""

from __future__ import annotations

import importlib.util
import unittest
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1] / "scripts"
LOCAL = Path(__file__).resolve().parent


def load(name):
    file = ROOT / (name + ".py")
    if not file.is_file():
        file = LOCAL / (name + ".py")
    spec = importlib.util.spec_from_file_location(name, file)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


observer = load("mojtrade_observe_market")
boundary = load("mojtrade_observer_boundary")
NOW = datetime(2026, 11, 7, 13, 30, tzinfo=timezone.utc)


def candles(now=NOW):
    floor_hour = int(now.timestamp()) // 3600 * 3600
    result = []
    for i in range(60):
        stamp = floor_hour - (60 - i) * 3600
        price = 30000.0 + i
        result.append([stamp, price - 10, price + 10, price - 1, price + 1, 2.5])
    return result


class ExistingObserverCompatibility(unittest.TestCase):
    def test_actual_observer_schema_passes_boundary_but_not_foundry(self):
        feed = observer.observe(now=NOW, fetcher=lambda _product: candles())
        report = boundary.audit_observer(feed, now=NOW)
        self.assertEqual(report["state"], "CONSISTENT_WATCH_PAYLOAD_RESEARCH_ONLY")
        self.assertEqual(report["watch_stances_validated"], 2)
        self.assertEqual(report["real_orders"], 0)
        self.assertEqual(report["public_signals"], 0)
        self.assertFalse(report["engine_input_eligible"])
        self.assertTrue(all("available_at" not in signal for signal in feed["signals"]))
        self.assertTrue(all("spread_bps" not in signal for signal in feed["signals"]))

    def test_exact_observer_id_detects_tamper(self):
        feed = observer.observe(now=NOW, fetcher=lambda _product: candles())
        changed = deepcopy(feed)
        changed["signals"][0]["data_source"] = "kraken-spot-public-ohlc"
        with self.assertRaisesRegex(boundary.ObserverReject, "id_mismatch"):
            boundary.audit_observer(changed, now=NOW)

    def test_real_observer_rejects_gapped_history(self):
        broken = candles()
        del broken[-10]
        with self.assertRaises(observer.MarketDataError):
            observer.observe(now=NOW, fetcher=lambda _product: broken)

    def test_real_observer_rejects_stale_history(self):
        old = candles(now=NOW - timedelta(days=2))
        with self.assertRaises(observer.MarketDataError):
            observer.observe(now=NOW, fetcher=lambda _product: old)

    def test_expiry_enforced_even_for_real_observer_output(self):
        feed = observer.observe(now=NOW, fetcher=lambda _product: candles())
        later = NOW + timedelta(minutes=90)
        with self.assertRaisesRegex(boundary.ObserverReject, "expired"):
            boundary.audit_observer(feed, now=later)

    def test_observer_source_contract_does_not_authorize_order_or_publication(self):
        feed = observer.observe(now=NOW, fetcher=lambda _product: candles())
        feed["signals"][0]["order"] = {"quantity": "1", "side": "buy"}
        with self.assertRaises(boundary.ObserverReject):
            boundary.audit_observer(feed, now=NOW)


if __name__ == "__main__":
    unittest.main()
