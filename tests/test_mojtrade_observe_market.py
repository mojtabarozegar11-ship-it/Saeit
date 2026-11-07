"""Safety and reproducibility checks for the independent read-only observer."""

import importlib.util
import json
import os
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch


SOURCE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "mojtrade_observe_market.py"
spec = importlib.util.spec_from_file_location("mojtrade_observe_market", SOURCE_PATH)
observer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(observer)


def sample(now, start=100.0):
    latest = (int(now.timestamp()) // 3600) * 3600 - 3600
    rows = []
    for n in range(80):
        close = start + n
        stamp = latest - (79 - n) * 3600
        rows.append([stamp, close - 1, close + 1, close, close, 12.0])
    return list(reversed(rows))  # Coinbase sends latest bars first.


class ObserverTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 11, 5, 12, 25, tzinfo=timezone.utc)

    def test_real_format_produces_expected_private_payload_without_orders(self):
        result = observer.observe(self.now, lambda product: sample(self.now))
        self.assertEqual(result["schema_version"], 1)
        self.assertEqual(result["source"], "mojtrade-vps")
        self.assertEqual(len(result["signals"]), 2)
        self.assertEqual([s["symbol"] for s in result["signals"]], ["BTC/USD", "ETH/USD"])
        self.assertEqual([s["stance"] for s in result["signals"]], ["watch_buy", "watch_buy"])
        self.assertNotIn("account", json.dumps(result))
        self.assertEqual(result, observer.observe(self.now, lambda product: sample(self.now)))

    def test_neutral_and_declining_market(self):
        self.assertEqual(observer._signal("BTC-USD", sample(self.now, start=100), self.now)["stance"], "watch_buy")
        down = sample(self.now, start=200)
        for i, row in enumerate(reversed(down)):
            close = 200 - i
            row[1:5] = [close - 1, close + 1, close, close]
        self.assertEqual(observer._signal("BTC-USD", down, self.now)["stance"], "watch_sell")
        flat = sample(self.now)
        for row in flat:
            row[1:5] = [99, 101, 100, 100]
        self.assertEqual(observer._signal("BTC-USD", flat, self.now)["stance"], "neutral")

    def test_reject_gaps_duplicates_future_and_stale(self):
        for change in ("gap", "duplicate", "stale", "invalid-price"):
            rows = sample(self.now)
            if change == "gap":
                del rows[20]
            elif change == "duplicate":
                rows[20] = rows[21]
            elif change == "stale":
                for row in rows:
                    row[0] -= 4 * 3600
            elif change == "invalid-price":
                rows[20][4] = float("nan")
            with self.subTest(change=change):
                with self.assertRaises(observer.MarketDataError):
                    observer._signal("BTC-USD", rows, self.now)

    def test_no_partial_payload_if_one_provider_request_fails(self):
        def broken(product):
            if product == "ETH-USD":
                raise observer.MarketDataError("Provider unavailable")
            return sample(self.now)
        with self.assertRaises(observer.MarketDataError):
            observer.observe(self.now, broken)

    def test_private_file_and_atomic_replacement(self):
        payload = observer.observe(self.now, lambda product: sample(self.now))
        with tempfile.TemporaryDirectory() as root:
            private = Path(root) / "private"
            private.mkdir(mode=0o700)
            filename = private / "payload.json"
            observer.write_private(payload, filename)
            self.assertEqual(json.loads(filename.read_text()), payload)
            self.assertEqual(filename.stat().st_mode & 0o777, 0o600)
            self.assertEqual(list(private.iterdir()), [filename])
            os.chmod(private, 0o755)
            with self.assertRaises(ValueError):
                observer.write_private(payload, filename)
            self.assertEqual(json.loads(filename.read_text()), payload)

    def test_public_path_and_symlink_prohibited(self):
        with tempfile.TemporaryDirectory() as root:
            private = Path(root) / "private"
            private.mkdir(mode=0o700)
            public = Path(root) / "public_html"
            public.mkdir(mode=0o700)
            payload = observer.observe(self.now, lambda product: sample(self.now))
            with self.assertRaises(ValueError):
                observer.write_private(payload, public / "feed.json")
            link = private / "linked.json"
            link.symlink_to(private / "target.json")
            with self.assertRaises(ValueError):
                observer.write_private(payload, link)

    def test_kraken_response_normalizes_to_common_ohlc_schema(self):
        coinbase_rows = sample(self.now)
        kraken_rows = [
            [row[0], str(row[3]), str(row[2]), str(row[1]), str(row[4]), str(row[4]), str(row[5]), 5]
            for row in coinbase_rows
        ]
        with patch.object(observer, "_fetch_json", return_value={
            "error": [], "result": {"XXBTZUSD": kraken_rows, "last": coinbase_rows[0][0]},
        }):
            normalized = observer._fetch_kraken_candles("BTC-USD")
            self.assertEqual(
                observer._validated_closes(normalized, self.now),
                observer._validated_closes(coinbase_rows, self.now),
            )

    def test_binance_response_normalizes_to_common_ohlc_schema(self):
        coinbase_rows = sample(self.now)
        binance_rows = [
            [row[0] * 1000, str(row[3]), str(row[2]), str(row[1]), str(row[4]), str(row[5]), row[0] * 1000 + 3599999]
            for row in coinbase_rows
        ]
        with patch.object(observer, "_fetch_json", return_value=binance_rows):
            normalized = observer._fetch_binance_candles("BTC-USD")
            self.assertEqual(
                observer._validated_closes(normalized, self.now),
                observer._validated_closes(coinbase_rows, self.now),
            )

    def test_fallback_tracks_real_provider_and_never_fabricates_on_total_outage(self):
        with patch.object(observer, "_fetch_candles", side_effect=observer.MarketDataError("coinbase_http_403")):
            with patch.object(observer, "_fetch_binance_candles", return_value=sample(self.now)):
                result = observer._observed_signal("BTC-USD", self.now)
                self.assertEqual(result["data_source"], observer.BINANCE_SOURCE)
                self.assertEqual(result["stance"], "watch_buy")
            with patch.object(observer, "_fetch_binance_candles", side_effect=observer.MarketDataError("binance_http_403")):
                with patch.object(observer, "_fetch_kraken_candles", side_effect=observer.MarketDataError("kraken_http_403")):
                    with patch.object(observer, "_fetch_bitfinex_candles", side_effect=observer.MarketDataError("bitfinex_network_timeout")):
                        with self.assertRaisesRegex(
                            observer.MarketDataError,
                            "coinbase_http_403;binance_http_403;kraken_http_403;bitfinex_network_timeout",
                        ):
                            observer._observed_signal("BTC-USD", self.now)


if __name__ == "__main__":
    unittest.main()
