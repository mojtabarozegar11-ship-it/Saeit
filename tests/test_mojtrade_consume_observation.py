import importlib.util
import json
import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path


SOURCE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "mojtrade_consume_observation.py"
spec = importlib.util.spec_from_file_location("mojtrade_consume_observation", SOURCE_PATH)
consumer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(consumer)


def payload(now, expires_delta=timedelta(minutes=30)):
    generated = now - timedelta(minutes=5)
    return {
        "schema_version": 1,
        "source": "mojtrade-vps",
        "generated_at": generated.isoformat(),
        "expires_at": (now + expires_delta).isoformat(),
        "signals": [
            {
                "id": "btc-1", "market": "crypto", "symbol": "BTC/USD", "timeframe": "1h",
                "stance": "watch_buy", "observed_at": generated.isoformat(),
                "method": "sma20-sma50-momentum10-v1-closed-1h",
                "data_source": "coinbase-exchange-public-candles",
            },
            {
                "id": "eth-1", "market": "crypto", "symbol": "ETH/USD", "timeframe": "1h",
                "stance": "neutral", "observed_at": generated.isoformat(),
                "method": "sma20-sma50-momentum10-v1-closed-1h",
                "data_source": "kraken-spot-public-ohlc",
            },
        ],
    }


class ObservationConsumerTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 11, 6, 14, 0, tzinfo=timezone.utc)

    def test_consumes_valid_payload_as_research_only(self):
        with tempfile.TemporaryDirectory() as root:
            private = Path(root) / "private"
            private.mkdir(mode=0o700)
            source = private / "observation.json"
            source.write_text(json.dumps(payload(self.now)), encoding="utf-8")
            os.chmod(source, 0o600)
            report = consumer.read_observation(source, self.now)
            self.assertEqual(report["action"], "research_only")
            self.assertEqual(report["execution"], "disabled")
            self.assertEqual(report["orders"], 0)
            self.assertEqual([s["symbol"] for s in report["signals"]], ["BTC/USD", "ETH/USD"])

    def test_rejects_expired_or_future_payload(self):
        with tempfile.TemporaryDirectory() as root:
            private = Path(root) / "private"
            private.mkdir(mode=0o700)
            source = private / "observation.json"
            for item in (
                payload(self.now, timedelta(minutes=-1)),
                {**payload(self.now), "generated_at": (self.now + timedelta(minutes=1)).isoformat()},
            ):
                source.write_text(json.dumps(item), encoding="utf-8")
                os.chmod(source, 0o600)
                with self.assertRaises(consumer.ObservationError):
                    consumer.read_observation(source, self.now)

    def test_rejects_untrusted_provider_and_open_permissions(self):
        with tempfile.TemporaryDirectory() as root:
            private = Path(root) / "private"
            private.mkdir(mode=0o700)
            source = private / "observation.json"
            item = payload(self.now)
            item["signals"][0]["data_source"] = "untrusted"
            source.write_text(json.dumps(item), encoding="utf-8")
            os.chmod(source, 0o600)
            with self.assertRaises(consumer.ObservationError):
                consumer.read_observation(source, self.now)
            os.chmod(source, 0o644)
            with self.assertRaises(consumer.ObservationError):
                consumer.read_observation(source, self.now)

    def test_rejects_missing_signal_identity_or_method(self):
        for field in ("id", "method"):
            with tempfile.TemporaryDirectory() as root:
                private = Path(root) / "private"
                private.mkdir(mode=0o700)
                source = private / "observation.json"
                item = payload(self.now)
                item["signals"][0].pop(field)
                source.write_text(json.dumps(item), encoding="utf-8")
                os.chmod(source, 0o600)
                with self.assertRaises(consumer.ObservationError):
                    consumer.read_observation(source, self.now)

    def test_private_report_write_is_atomic_and_mode_600(self):
        with tempfile.TemporaryDirectory() as root:
            private = Path(root) / "private"
            private.mkdir(mode=0o700)
            destination = private / "report.json"
            consumer.write_private({"orders": 0, "execution": "disabled"}, destination)
            self.assertEqual(json.loads(destination.read_text()), {"orders": 0, "execution": "disabled"})
            self.assertEqual(destination.stat().st_mode & 0o777, 0o600)
            self.assertEqual(list(private.iterdir()), [destination])

    def test_bitstamp_usd_fallback_reaches_private_research_report(self):
        with tempfile.TemporaryDirectory() as root:
            private = Path(root) / "private"
            private.mkdir(mode=0o700)
            source = private / "observation.json"
            item = payload(self.now)
            for signal in item["signals"]:
                signal["data_source"] = "bitstamp-public-ohlc"
            source.write_text(json.dumps(item), encoding="utf-8")
            os.chmod(source, 0o600)
            report = consumer.read_observation(source, self.now)
            self.assertEqual([s["data_source"] for s in report["signals"]],
                             ["bitstamp-public-ohlc"] * 2)
            self.assertEqual(report["execution"], "disabled")
            self.assertEqual(report["orders"], 0)

    def test_binance_usdt_market_cannot_claim_usd_provenance(self):
        with tempfile.TemporaryDirectory() as root:
            private = Path(root) / "private"
            private.mkdir(mode=0o700)
            source = private / "observation.json"
            item = payload(self.now)
            item["signals"][0]["data_source"] = "binance-public-klines"
            source.write_text(json.dumps(item), encoding="utf-8")
            os.chmod(source, 0o600)
            with self.assertRaisesRegex(consumer.ObservationError, "provider_invalid"):
                consumer.read_observation(source, self.now)



if __name__ == "__main__":
    unittest.main()
