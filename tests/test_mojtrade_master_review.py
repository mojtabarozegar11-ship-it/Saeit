"""Single master MojTrade research-only review: reject unsafe/stale input."""
import json
import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

from core.canonical_bot_identity import CANONICAL_BOT_CODE

from core.mojtrade_research_review import (
    ResearchReviewError,
    inspect_private_observation,
    master_research_review,
    trusted_source,
)


NOW = datetime(2026, 11, 13, 10, 0, tzinfo=timezone.utc)


def sample(now=NOW):
    generated = now - timedelta(minutes=5)
    observed = now - timedelta(minutes=80)
    return {
        "schema_version": 1,
        "source": "mojtrade-vps",
        "generated_at": generated.isoformat(),
        "expires_at": (generated + timedelta(minutes=90)).isoformat(),
        "signals": [
            {
                "id": "btc-20261113", "symbol": "BTC/USD", "market": "crypto",
                "timeframe": "1h", "stance": "watch_buy",
                "data_source": "bitstamp-public-ohlc",
                "observed_at": observed.isoformat(),
                "method": "sma20-sma50-momentum10-v1-closed-1h",
            },
            {
                "id": "eth-20261113", "symbol": "ETH/USD", "market": "crypto",
                "timeframe": "1h", "stance": "neutral",
                "data_source": "kraken-spot-public-ohlc",
                "observed_at": observed.isoformat(),
                "method": "sma20-sma50-momentum10-v1-closed-1h",
            },
        ],
    }


class MasterMojTradeReviewTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        env_patch = mock.patch.dict(os.environ, {"HOME": self.temp.name,
                                                 "MOJ_FACTORY_LOCAL_MODE": "1"})
        env_patch.start()
        self.addCleanup(env_patch.stop)
        self.path = trusted_source()
        self.path.parent.mkdir(parents=True, mode=0o700)
        os.chmod(self.path.parent, 0o700)
        self.write()

    def write(self, content=None):
        self.path.write_text(json.dumps(sample() if content is None else content),
                             encoding="utf-8")
        os.chmod(self.path, 0o600)

    def test_review_preserves_provenance_without_claiming_performance_or_orders(self):
        reviewed = inspect_private_observation(self.path, NOW)
        self.assertEqual(reviewed["canonical_agent"], CANONICAL_BOT_CODE)
        self.assertEqual(len(reviewed["source_sha256"]), 64)
        self.assertEqual(reviewed["observed_symbols"], ["BTC/USD", "ETH/USD"])
        self.assertEqual(reviewed["observations"][0]["data_source"], "bitstamp-public-ohlc")
        self.assertEqual(reviewed["measurement"]["forward_outcome_samples"], 0)
        self.assertIsNone(reviewed["measurement"]["verified_net_pnl"])
        self.assertFalse(reviewed["controls"]["financial_actions_enabled"])
        self.assertEqual(reviewed["controls"]["orders"], 0)

    def test_missing_observation_rejected(self):
        self.path.unlink()
        with self.assertRaisesRegex(ResearchReviewError, "MISSING"):
            inspect_private_observation(self.path, NOW)

    def test_private_only_rejects_open_file_and_open_directory(self):
        os.chmod(self.path, 0o644)
        with self.assertRaisesRegex(ResearchReviewError, "FILE_UNSAFE"):
            inspect_private_observation(self.path, NOW)
        os.chmod(self.path, 0o600)
        os.chmod(self.path.parent, 0o755)
        with self.assertRaisesRegex(ResearchReviewError, "DIRECTORY_UNSAFE"):
            inspect_private_observation(self.path, NOW)

    def test_rejects_symlink_hardlink_and_outside_source(self):
        data = self.path.read_bytes()
        self.path.unlink()
        outside = Path(self.temp.name) / "outside.json"
        outside.write_bytes(data)
        os.chmod(outside, 0o600)
        self.path.symlink_to(outside)
        with self.assertRaisesRegex(ResearchReviewError, "PATH_REJECTED"):
            inspect_private_observation(self.path, NOW)
        self.path.unlink()
        os.link(outside, self.path)
        with self.assertRaisesRegex(ResearchReviewError, "FILE_UNSAFE"):
            inspect_private_observation(self.path, NOW)
        with self.assertRaisesRegex(ResearchReviewError, "PATH_REJECTED"):
            inspect_private_observation(outside, NOW)

    def test_rejects_expired_future_and_overlong_research_lifetime(self):
        for edit in ("expired", "future", "long"):
            value = sample()
            if edit == "expired":
                value["expires_at"] = (NOW - timedelta(minutes=1)).isoformat()
            elif edit == "future":
                value["generated_at"] = (NOW + timedelta(minutes=1)).isoformat()
            else:
                value["expires_at"] = (NOW + timedelta(days=2)).isoformat()
            self.write(value)
            with self.subTest(case=edit):
                with self.assertRaises(ResearchReviewError):
                    inspect_private_observation(self.path, NOW)

    def test_rejects_old_or_postgenerated_candles(self):
        for observed in (NOW - timedelta(hours=5),
                         NOW - timedelta(minutes=1)):
            value = sample()
            value["signals"][0]["observed_at"] = observed.isoformat()
            self.write(value)
            with self.assertRaisesRegex(ResearchReviewError, "CANDLE_STALE"):
                inspect_private_observation(self.path, NOW)

    def test_rejects_untrusted_usdt_source_as_usd(self):
        value = sample()
        value["signals"][0]["data_source"] = "binance-public-klines"
        self.write(value)
        with self.assertRaisesRegex(ResearchReviewError, "CONTENT_REJECTED"):
            inspect_private_observation(self.path, NOW)

    def test_rejects_oversize_and_truncated_payload(self):
        self.path.write_bytes(b"X" * 96001)
        with self.assertRaisesRegex(ResearchReviewError, "FILE_UNSAFE"):
            inspect_private_observation(self.path, NOW)
        self.path.write_bytes(b"{")
        with self.assertRaisesRegex(ResearchReviewError, "CONTENT_REJECTED"):
            inspect_private_observation(self.path, NOW)

    def test_master_refuses_external_runtime_and_source_override(self):
        with mock.patch.dict(os.environ, {"MOJ_FACTORY_LOCAL_MODE": "0"}):
            with self.assertRaisesRegex(ResearchReviewError, "PRIVATE_RUNTIME_ONLY"):
                master_research_review({})
        with self.assertRaisesRegex(ResearchReviewError, "UNAUTHORIZED_OVERRIDE"):
            master_research_review({"source_path": "/tmp/foreign.json"})

    def test_no_source_file_write_on_research_failure(self):
        before = self.path.read_bytes()
        with self.assertRaisesRegex(ResearchReviewError, "CONTENT_REJECTED"):
            bad = sample()
            bad["signals"][0]["stance"] = "buy_and_execute"
            self.write(bad)
            inspect_private_observation(self.path, NOW)
        # The reviewer does not repair/write observations, including invalid ones.
        self.assertNotEqual(self.path.read_bytes(), before)
        self.assertEqual(json.loads(self.path.read_text())["signals"][0]["stance"],
                         "buy_and_execute")


if __name__ == "__main__":
    unittest.main()
