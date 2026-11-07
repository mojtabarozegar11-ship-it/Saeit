"""Contract tests for public inside-book quote capture; never use network."""

from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1] / "scripts"
LOCAL = Path(__file__).resolve().parent


def load(name):
    path = ROOT / (name + ".py")
    path = path if path.is_file() else LOCAL / (name + ".py")
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(path.parent))
    try:
        spec.loader.exec_module(module)
    finally:
        sys.path.pop(0)
    return module


quotes = load("mojtrade_market_quote_evidence")
capture = load("mojtrade_forward_bar_capture")
NOW = datetime(2026, 11, 7, 13, 30, tzinfo=timezone.utc)


def coinbase():
    return {"sequence": 10, "time": NOW.isoformat(),
            "bids": [["100.0", "2.0", 1]],
            "asks": [["100.1", "1.0", 2]]}


def kraken():
    return {"error": [], "result": {"XETHZUSD": {
        "a": ["100.1", "1", "1"], "b": ["100", "2", "2"]}}}


def rows_for(clock):
    floor = int(clock.timestamp()) // 3600 * 3600
    result = []
    for i in range(60):
        stamp = floor - (60 - i) * 3600
        price = 100.0 + i
        result.append([stamp, price - 1.5, price + 1.5, price - 1, price + 1, 3.0])
    return result


class PublicQuoteTests(unittest.TestCase):
    def test_coinbase_public_book_price_and_receipt(self):
        evidence = quotes.fetch_public_quote("BTC-USD", quotes.observer.SOURCE,
            fetch_json=lambda url, label: coinbase(), clock=lambda: NOW)
        self.assertEqual(evidence["bid"], 100)
        self.assertEqual(evidence["ask"], 100.1)
        self.assertGreater(evidence["spread_bps"], 0)
        self.assertFalse(evidence["venue_authenticity_independently_verified"])
        self.assertEqual(evidence["real_orders"], 0)

    def test_kraken_public_ticker(self):
        e = quotes.fetch_public_quote("ETH-USD", quotes.observer.KRAKEN_SOURCE,
            fetch_json=lambda url, label: kraken(), clock=lambda: NOW)
        self.assertEqual(e["bid"], 100)
        self.assertEqual(e["ask"], 100.1)
        self.assertIsNone(e["book_source_timestamp_utc"])

    def test_kraken_rejects_wrong_ticker_product(self):
        with self.assertRaisesRegex(quotes.QuoteReject, "product_mismatch"):
            quotes.fetch_public_quote("BTC-USD", quotes.observer.KRAKEN_SOURCE,
                fetch_json=lambda url, label: kraken(), clock=lambda: NOW)

    def test_unsupported_venue_never_calls_endpoint(self):
        called = []
        with self.assertRaises(quotes.QuoteReject):
            quotes.fetch_public_quote("BTC-USD", quotes.observer.BITSTAMP_SOURCE,
                fetch_json=lambda url, label: called.append(url))
        self.assertEqual(called, [])

    def test_stale_coinbase_book_rejected(self):
        bad = coinbase()
        bad["time"] = (NOW - timedelta(minutes=2)).isoformat()
        with self.assertRaisesRegex(quotes.QuoteReject, "stale"):
            quotes.fetch_public_quote("BTC-USD", quotes.observer.SOURCE,
                fetch_json=lambda url, label: bad, clock=lambda: NOW)

    def test_crossed_and_excessive_quotes_rejected(self):
        for ask in ("99", "110"):
            bad = coinbase()
            bad["asks"][0][0] = ask
            with self.subTest(ask=ask), self.assertRaises(quotes.QuoteReject):
                quotes.fetch_public_quote("BTC-USD", quotes.observer.SOURCE,
                    fetch_json=lambda url, label: bad, clock=lambda: NOW)

    def test_missing_or_nonfinite_bid_ask_rejected(self):
        for bid in ("nan", "inf", "", "0", "-1"):
            bad = coinbase()
            bad["bids"][0][0] = bid
            with self.subTest(bid=bid), self.assertRaises(quotes.QuoteReject):
                quotes.fetch_public_quote("BTC-USD", quotes.observer.SOURCE,
                    fetch_json=lambda url, label: bad, clock=lambda: NOW)

    def test_too_slow_quote_fetch_rejected(self):
        times = iter((NOW, NOW + timedelta(seconds=17)))
        with self.assertRaisesRegex(quotes.QuoteReject, "latency"):
            quotes.fetch_public_quote("BTC-USD", quotes.observer.SOURCE,
                fetch_json=lambda url, label: coinbase(), clock=lambda: next(times))

    def test_same_venue_quote_enriches_bar_journal_but_never_trading(self):
        quote = quotes.fetch_public_quote("BTC-USD", quotes.observer.SOURCE,
            fetch_json=lambda url, label: coinbase(), clock=lambda: NOW)
        event = capture.capture_public_once("BTC-USD",
            venues=((quotes.observer.SOURCE, lambda _: rows_for(NOW)),),
            clock=lambda: NOW, quote_fetcher=lambda symbol, venue: quote)
        self.assertEqual(event["spread_bps"], quote["spread_bps"])
        self.assertIn("quote_receipt", event)
        self.assertFalse(event["research_dataset_eligible"])
        with tempfile.TemporaryDirectory() as root:
            folder = Path(root) / "private"
            folder.mkdir(mode=0o700)
            info = capture.append_private(event, folder / "evidence.jsonl")
            self.assertEqual(info["sequence"], 1)

    def test_wrong_venue_or_missing_quote_keeps_spread_null(self):
        valid = quotes.fetch_public_quote("BTC-USD", quotes.observer.SOURCE,
            fetch_json=lambda url, label: coinbase(), clock=lambda: NOW)
        bad = {**valid, "venue_claim": quotes.observer.KRAKEN_SOURCE}
        for injected in (bad, {}):
            with self.subTest(injected=injected):
                event = capture.capture_public_once("BTC-USD",
                    venues=((quotes.observer.SOURCE, lambda _: rows_for(NOW)),),
                    clock=lambda: NOW, quote_fetcher=lambda symbol, venue: injected)
                self.assertIsNone(event["spread_bps"])
                self.assertNotIn("quote_receipt", event)

    def test_forged_quote_spread_rejected(self):
        quote = quotes.fetch_public_quote("BTC-USD", quotes.observer.SOURCE,
            fetch_json=lambda url, label: coinbase(), clock=lambda: NOW)
        forged = {**quote, "spread_bps": 0}
        bar = capture.latest_capture("BTC-USD", rows_for(NOW), quotes.observer.SOURCE,
                                     received_at=NOW)
        with self.assertRaisesRegex(capture.CaptureReject, "mismatched"):
            capture.validate_observation({**bar, "quote_receipt": forged, "spread_bps": 0})

    def test_delayed_quote_rejected_from_bar_observation(self):
        quote = quotes.fetch_public_quote("BTC-USD", quotes.observer.SOURCE,
            fetch_json=lambda url, label: coinbase(), clock=lambda: NOW)
        quote["quote_received_at_utc"] = (NOW + timedelta(seconds=31)).isoformat()
        bar = capture.latest_capture("BTC-USD", rows_for(NOW), quotes.observer.SOURCE,
                                     received_at=NOW)
        with self.assertRaisesRegex(capture.CaptureReject, "not_contemporaneous"):
            capture.validate_observation({**bar, "quote_receipt": quote,
                                          "spread_bps": quote["spread_bps"]})

    def test_book_source_timestamp_cannot_be_forged_in_private_journal(self):
        quote = quotes.fetch_public_quote("BTC-USD", quotes.observer.SOURCE,
            fetch_json=lambda url, label: coinbase(), clock=lambda: NOW)
        quote["book_source_timestamp_utc"] = "2026-11-01T00:00:00+00:00"
        bar = capture.latest_capture("BTC-USD", rows_for(NOW), quotes.observer.SOURCE,
                                     received_at=NOW)
        with self.assertRaisesRegex(capture.CaptureReject, "not_fresh"):
            capture.validate_observation({**bar, "quote_receipt": quote,
                                          "spread_bps": quote["spread_bps"]})


if __name__ == "__main__":
    unittest.main()
