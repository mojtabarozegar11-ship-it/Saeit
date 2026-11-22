"""Offline scientific data boundary, never a trading authorization test."""

from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1] / "scripts"
LOCAL = Path(__file__).resolve().parent


def load(name):
    file = ROOT / (name + ".py")
    file = file if file.is_file() else LOCAL / (name + ".py")
    spec = importlib.util.spec_from_file_location(name, file)
    module = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(file.parent))
    try:
        spec.loader.exec_module(module)
    finally:
        sys.path.pop(0)
    return module


gate = load("mojtrade_forward_dataset_gate")
capture = gate.capture
quotes = load("mojtrade_market_quote_evidence")
START = datetime(2026, 11, 1, 0, 30, tzinfo=timezone.utc)


def rows_for(now):
    floor = int(now.timestamp()) // 3600 * 3600
    return [[floor - (60 - i) * 3600, 90 + i, 110 + i,
             100 + i, 101 + i, 2.0] for i in range(60)]


def one_record(now, source=None, *, with_quote=True):
    source = source or capture.observer.SOURCE
    event = capture.latest_capture("BTC-USD", rows_for(now), source, received_at=now)
    if not with_quote:
        return event
    book = {"sequence": 7, "time": now.isoformat(),
            "bids": [["100", "1", 1]], "asks": [["100.1", "1", 1]]}
    quote = quotes.fetch_public_quote("BTC-USD", quotes.observer.SOURCE,
        fetch_json=lambda url, label: book, clock=lambda: now)
    if source != capture.observer.SOURCE:
        quote["venue_claim"] = source
        quote["book_source_timestamp_utc"] = None
        quote["book_sequence"] = None
    event["spread_bps"] = quote["spread_bps"]
    event["quote_receipt"] = quote
    return event


def journal(count=100, *, gap_at=None, no_quote_at=None, mixed_at=None):
    events = []
    previous = "0" * 64
    for i in range(count):
        offset = i + (1 if gap_at is not None and i >= gap_at else 0)
        at = START + timedelta(hours=offset)
        source = (capture.observer.KRAKEN_SOURCE if i == mixed_at else capture.observer.SOURCE)
        obs = one_record(at, source, with_quote=i != no_quote_at)
        entry = {"sequence": i + 1, "previous_sha256": previous, "observation": obs}
        entry["entry_sha256"] = capture.sha(entry)
        events.append(entry)
        previous = entry["entry_sha256"]
    raw = ("\n".join(capture.canonical(e) for e in events) + "\n").encode()
    return events, raw


class ForwardDatasetGateTests(unittest.TestCase):
    def test_full_contiguous_100_bar_dataset_is_research_only(self):
        events, raw = journal()
        result = gate.assemble(events, __import__("hashlib").sha256(raw).hexdigest())
        self.assertEqual(len(result["dataset"]["bars"]), 100)
        self.assertEqual(result["dataset"]["interval_seconds"], 3600)
        self.assertEqual(result["dataset"]["bars"][0]["available_at"],
                         events[0]["observation"]["quote_receipt"]["quote_received_at_utc"])
        self.assertEqual(result["manifest"]["status"], "UNVERIFIED_FORWARD_RESEARCH_ONLY")
        self.assertFalse(result["manifest"]["provider_authenticity_verified"])
        self.assertFalse(result["manifest"]["production_eligible"])
        self.assertEqual(result["manifest"]["real_orders"], 0)

    def test_99_bars_cannot_pass(self):
        events, raw = journal(99)
        with self.assertRaisesRegex(gate.ForwardDatasetReject, "insufficient"):
            gate.assemble(events, __import__("hashlib").sha256(raw).hexdigest())

    def test_overlapping_rolling_window_remains_one_research_source(self):
        a, raw_a = journal(100)
        b, raw_b = journal(101)
        first = gate.assemble(a, __import__("hashlib").sha256(raw_a).hexdigest())
        second = gate.assemble(b, __import__("hashlib").sha256(raw_b).hexdigest())
        self.assertEqual(first["dataset"]["source_id"], second["dataset"]["source_id"])
        self.assertNotEqual(first["manifest"]["dataset_sha256"],
                            second["manifest"]["dataset_sha256"])

    def test_gap_at_last_rows_blocks_latest_suffix(self):
        events, raw = journal(120, gap_at=90)
        with self.assertRaisesRegex(gate.ForwardDatasetReject, "insufficient"):
            gate.assemble(events, __import__("hashlib").sha256(raw).hexdigest())

    def test_missing_latest_quote_blocks(self):
        events, raw = journal(100, no_quote_at=99)
        with self.assertRaises(gate.ForwardDatasetReject):
            gate.assemble(events, __import__("hashlib").sha256(raw).hexdigest())

    def test_mixed_venue_in_latest_segment_blocks(self):
        events, raw = journal(100, mixed_at=30)
        with self.assertRaises(gate.ForwardDatasetReject):
            gate.assemble(events, __import__("hashlib").sha256(raw).hexdigest())

    def test_private_journal_hash_chain_read(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp) / "private"
            folder.mkdir(mode=0o700)
            path = folder / "hourly.jsonl"
            _, raw = journal()
            path.write_bytes(raw)
            path.chmod(0o600)
            events, journal_sha = gate.read_journal(path)
            self.assertEqual(len(events), 100)
            self.assertEqual(gate.assemble(events, journal_sha)["manifest"]["bar_count"], 100)

    def test_tampered_journal_read_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp) / "private"
            folder.mkdir(mode=0o700)
            path = folder / "hourly.jsonl"
            _, raw = journal()
            path.write_bytes(raw.replace(b'"volume":2.0', b'"volume":5.0', 1))
            path.chmod(0o600)
            with self.assertRaisesRegex(gate.ForwardDatasetReject, "chain"):
                gate.read_journal(path)

    def test_read_rejects_unsafe_journal_permissions(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp) / "private"
            folder.mkdir(mode=0o700)
            path = folder / "hourly.jsonl"
            _, raw = journal(1)
            path.write_bytes(raw)
            path.chmod(0o644)
            with self.assertRaisesRegex(gate.ForwardDatasetReject, "permissions"):
                gate.read_journal(path)

    def test_output_new_private_file_cannot_overwrite(self):
        events, raw = journal()
        result = gate.assemble(events, __import__("hashlib").sha256(raw).hexdigest())
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp) / "private"
            folder.mkdir(mode=0o700)
            target = folder / "dataset.json"
            receipt = gate.write_private(result, target)
            self.assertFalse(receipt["production_eligible"])
            self.assertEqual(target.stat().st_mode & 0o777, 0o600)
            self.assertEqual(json.loads(target.read_text())["manifest"]["bar_count"], 100)
            with self.assertRaisesRegex(gate.ForwardDatasetReject, "new_private_file"):
                gate.write_private(result, target)


if __name__ == "__main__":
    unittest.main()
