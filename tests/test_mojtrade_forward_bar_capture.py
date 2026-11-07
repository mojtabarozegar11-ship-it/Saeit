"""Offline journal, delayed-source and fail-closed regression tests."""

from __future__ import annotations

import importlib.util
import json
import os
import sys
import tempfile
import unittest
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path


REPO_SOURCE = Path(__file__).resolve().parents[1] / "scripts" / "mojtrade_forward_bar_capture.py"
SOURCE = REPO_SOURCE if REPO_SOURCE.is_file() else Path(__file__).with_name("mojtrade_forward_bar_capture.py")
spec = importlib.util.spec_from_file_location("mojtrade_forward_bar_capture", SOURCE)
capture = importlib.util.module_from_spec(spec)
sys.path.insert(0, str(SOURCE.parent))
try:
    spec.loader.exec_module(capture)
finally:
    sys.path.pop(0)


NOW = datetime(2026, 11, 7, 13, 30, tzinfo=timezone.utc)


def rows_for(clock):
    floor = int(clock.timestamp()) // 3600 * 3600
    result = []
    for i in range(60):
        stamp = floor - (60 - i) * 3600
        price = 30000.0 + i
        result.append([stamp, price - 10, price + 10, price - 1, price + 1, 3.0])
    return result


def observation(now=NOW, source=None):
    return capture.latest_capture("BTC-USD", rows_for(now), source or capture.observer.SOURCE,
                                  received_at=now)


class ProspectiveCaptureTests(unittest.TestCase):
    def test_latest_bar_uses_actual_receipt_time_not_historical_close(self):
        event = observation()
        self.assertEqual(event["bar_close_utc"], "2026-11-07T13:00:00+00:00")
        self.assertEqual(event["first_observed_at_utc"], "2026-11-07T13:30:00+00:00")
        self.assertIsNone(event["spread_bps"])
        self.assertFalse(event["research_dataset_eligible"])
        self.assertFalse(event["provenance_authenticated"])
        self.assertEqual(event["real_orders"], 0)

    def test_reject_two_hour_delayed_capture_instead_of_backdating(self):
        with self.assertRaisesRegex(capture.CaptureReject, "too_late"):
            capture.latest_capture("BTC-USD", rows_for(NOW - timedelta(hours=2)),
                                   capture.observer.SOURCE, received_at=NOW)

    def test_mocked_source_fallback_retains_actual_provider(self):
        def fail(_):
            raise capture.observer.MarketDataError("source_unavailable")
        providers = ((capture.observer.SOURCE, fail),
                     (capture.observer.KRAKEN_SOURCE, lambda _: rows_for(NOW)))
        event = capture.capture_public_once("BTC-USD", venues=providers, clock=lambda: NOW)
        self.assertEqual(event["venue_claim"], capture.observer.KRAKEN_SOURCE)

    def test_all_mocked_sources_fail_closed(self):
        with self.assertRaisesRegex(capture.CaptureReject, "no_valid_public_capture"):
            capture.capture_public_once("BTC-USD", venues=((capture.observer.SOURCE,
                lambda _: []),), clock=lambda: NOW)

    def test_journal_append_and_idempotent_repoll(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp) / "private"
            folder.mkdir(mode=0o700)
            path = folder / "hourly.jsonl"
            first = capture.append_private(observation(), path)
            repeat = capture.append_private(observation(), path)
            self.assertTrue(first["written"])
            self.assertFalse(repeat["written"])
            self.assertEqual(repeat["sequence"], 1)
            self.assertEqual(oct(path.stat().st_mode & 0o777), "0o600")
            later = capture.append_private(observation(NOW + timedelta(hours=1)), path)
            self.assertEqual(later["sequence"], 2)
            events = capture._read_rows(path.read_bytes())
            self.assertEqual(len(events), 2)
            self.assertEqual(events[1]["previous_sha256"], events[0]["entry_sha256"])

    def test_conflicting_repeated_observation_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp) / "private"
            folder.mkdir(mode=0o700)
            path = folder / "hourly.jsonl"
            capture.append_private(observation(), path)
            conflict = observation(source=capture.observer.KRAKEN_SOURCE)
            with self.assertRaisesRegex(capture.CaptureReject, "conflicting"):
                capture.append_private(conflict, path)

    def test_corrupt_journal_hash_never_appended(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp) / "private"
            folder.mkdir(mode=0o700)
            path = folder / "hourly.jsonl"
            capture.append_private(observation(), path)
            raw = path.read_bytes()
            path.write_bytes(raw.replace(b'"volume":3.0', b'"volume":5.0'))
            with self.assertRaisesRegex(capture.CaptureReject, "hash_chain"):
                capture.append_private(observation(NOW + timedelta(hours=1)), path)

    def test_reject_fake_spread_and_action(self):
        for key, value in (("spread_bps", 1.3), ("execution", "enabled"),
                           ("publication", "enabled"), ("real_orders", 1)):
            wrong = observation()
            wrong[key] = value
            with self.subTest(key=key), self.assertRaises(capture.CaptureReject):
                capture.validate_observation(wrong)

    def test_reject_fabricated_first_observed_before_bar_close(self):
        wrong = observation()
        wrong["first_observed_at_utc"] = wrong["bar_open_utc"]
        with self.assertRaises(capture.CaptureReject):
            capture.validate_observation(wrong)

    def test_reject_insecure_private_folder(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp) / "private"
            folder.mkdir(mode=0o755)
            with self.assertRaises(capture.CaptureReject):
                capture.append_private(observation(), folder / "hourly.jsonl")

    def test_reject_symlinked_journal(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp) / "private"
            folder.mkdir(mode=0o700)
            original = folder / "safe.jsonl"
            original.touch(mode=0o600)
            alias = folder / "alias.jsonl"
            alias.symlink_to(original)
            with self.assertRaises(capture.CaptureReject):
                capture.append_private(observation(), alias)

    def test_reject_out_of_order_hour(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp) / "private"
            folder.mkdir(mode=0o700)
            path = folder / "hourly.jsonl"
            capture.append_private(observation(NOW + timedelta(hours=2)), path)
            with self.assertRaisesRegex(capture.CaptureReject, "out_of_order"):
                capture.append_private(observation(), path)


if __name__ == "__main__":
    unittest.main()
