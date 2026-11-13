import json
import os
import stat
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from mojtrade_build_research_product import ProductArtifactError, build_artifact


class ResearchProductArtifactTests(unittest.TestCase):
    def _report(self, path, **changes):
        report = {
            "report_type": "mojtrade-research-observation-consumption",
            "generated_at": "2026-11-06T10:00:00+00:00",
            "observation_expires_at": "2026-11-06T12:00:00+00:00",
            "action": "research_only", "execution": "disabled", "orders": 0,
            "signals": [
                {"symbol": "BTC/USD", "stance": "neutral",
                 "observed_at": "2026-11-06T09:00:00+00:00",
                 "data_source": "bitfinex-public-candles", "method": "sma"},
                {"symbol": "ETH/USD", "stance": "watch_buy",
                 "observed_at": "2026-11-06T09:00:00+00:00",
                 "data_source": "bitfinex-public-candles", "method": "sma"},
            ],
        }
        report.update(changes)
        path.write_text(json.dumps(report), encoding="utf-8")
        os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)

    def test_builds_hashed_noncommercial_artifact(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "report.json"
            self._report(path)
            artifact = build_artifact(path, datetime(2026, 11, 6, 11, tzinfo=timezone.utc))
            self.assertTrue(artifact["source_report_sha256"])
            self.assertEqual(artifact["schema"], "mojtrade.research-product-artifact.v1")
            self.assertFalse(artifact["publication_enabled"])
            self.assertFalse(artifact["delivery_enabled"])
            self.assertFalse(artifact["revenue_verified"])
            self.assertFalse(artifact["trading_pnl_included"])
            self.assertEqual(artifact["orders"], 0)

    def test_rejects_execution_boundary_change(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "report.json"
            self._report(path, execution="enabled")
            with self.assertRaisesRegex(ProductArtifactError, "execution_boundary"):
                build_artifact(path, datetime(2026, 11, 6, 11, tzinfo=timezone.utc))

    def test_rejects_expired_or_incoherent_window(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "report.json"
            self._report(path)
            with self.assertRaisesRegex(ProductArtifactError, "time_window"):
                build_artifact(path, datetime(2026, 11, 6, 13, tzinfo=timezone.utc))
            self._report(path, generated_at="2026-11-06T13:00:00+00:00")
            with self.assertRaisesRegex(ProductArtifactError, "time_window"):
                build_artifact(path, datetime(2026, 11, 6, 11, tzinfo=timezone.utc))

    def test_rejects_malformed_signal(self):
        cases = (
            ({"signals": [{}]}, "signal_count"),
            ({"signals": [
                {"symbol": "BTC/USD", "stance": "neutral",
                 "observed_at": "2026-11-06T09:00:00+00:00",
                 "data_source": "unknown", "method": "sma"},
                {"symbol": "ETH/USD", "stance": "neutral",
                 "observed_at": "2026-11-06T09:00:00+00:00",
                 "data_source": "bitfinex-public-candles", "method": "sma"},
            ]}, "provider"),
            ({"signals": [
                {"symbol": "BTC/USD", "stance": "neutral",
                 "observed_at": "2026-11-06T09:00:00+00:00",
                 "data_source": "bitfinex-public-candles", "method": ""},
                {"symbol": "ETH/USD", "stance": "neutral",
                 "observed_at": "2026-11-06T09:00:00+00:00",
                 "data_source": "bitfinex-public-candles", "method": "sma"},
            ]}, "method"),
        )
        for changes, reason in cases:
            with self.subTest(reason=reason):
                with tempfile.TemporaryDirectory() as folder:
                    path = Path(folder) / "report.json"
                    self._report(path, **changes)
                    with self.assertRaisesRegex(ProductArtifactError, reason):
                        build_artifact(path, datetime(2026, 11, 6, 11, tzinfo=timezone.utc))

    def test_bitstamp_usd_report_becomes_private_nontrading_product(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "report.json"
            self._report(path, signals=[
                {"symbol": sym, "stance": "neutral",
                 "observed_at": "2026-11-06T09:00:00+00:00",
                 "data_source": "bitstamp-public-ohlc", "method": "sma"}
                for sym in ("BTC/USD", "ETH/USD")
            ])
            product = build_artifact(path, datetime(2026, 11, 6, 11, tzinfo=timezone.utc))
            self.assertEqual(len(product["signals"]), 2)
            self.assertEqual(product["signals"][0]["data_source"], "bitstamp-public-ohlc")
            self.assertFalse(product["publication_enabled"])
            self.assertFalse(product["delivery_enabled"])
            self.assertFalse(product["revenue_verified"])
            self.assertEqual(product["orders"], 0)

    def test_rejects_usdt_quotation_as_usd_product(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "report.json"
            self._report(path, signals=[
                {"symbol": sym, "stance": "neutral",
                 "observed_at": "2026-11-06T09:00:00+00:00",
                 "data_source": "binance-public-klines", "method": "sma"}
                for sym in ("BTC/USD", "ETH/USD")
            ])
            with self.assertRaisesRegex(ProductArtifactError, "report_provider_invalid"):
                build_artifact(path, datetime(2026, 11, 6, 11, tzinfo=timezone.utc))



if __name__ == "__main__":
    unittest.main()
