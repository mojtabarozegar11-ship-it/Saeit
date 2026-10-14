"""Unit tests for live-priced ETH/TRX quotes; never call third-party APIs."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import mojplaywin_direct_wallet_rates as rates

NOW=1_791_950_000

class RateTests(unittest.TestCase):
    def sample(self):
        return {
            "ethereum": {"usd": "3010.25", "last_updated_at": NOW-20},
            "tron": {"usd": "0.287", "last_updated_at": NOW-20},
        }

    def assert_bad(self, edit):
        data=self.sample()
        edit(data)
        with self.assertRaises(rates.RateFeedUnavailable):
            rates.parse_coin_gecko_rates(data, NOW)

    def test_valid_rate_has_correct_asset_and_provider(self):
        x=rates.parse_coin_gecko_rates(self.sample(), NOW)
        self.assertEqual(x["ETH"].usd_per_asset, "3010.25")
        self.assertEqual(x["TRX"].provider, "coingecko")
        self.assertEqual(x["TRX"].observed_at_epoch, NOW-20)

    def test_missing_asset(self):
        self.assert_bad(lambda x:x.pop("tron"))

    def test_stale_rate(self):
        self.assert_bad(lambda x:x["tron"].update(last_updated_at=NOW-91))

    def test_future_rate(self):
        self.assert_bad(lambda x:x["ethereum"].update(last_updated_at=NOW+1))

    def test_missing_time(self):
        self.assert_bad(lambda x:x["tron"].pop("last_updated_at"))

    def test_zero_or_negative_price(self):
        self.assert_bad(lambda x:x["ethereum"].update(usd=0))
        self.assert_bad(lambda x:x["tron"].update(usd="-2.5"))

    def test_nan_rate(self):
        self.assert_bad(lambda x:x["ethereum"].update(usd="NaN"))

    def test_invalid_response(self):
        with self.assertRaises(rates.RateFeedUnavailable):
            rates.parse_coin_gecko_rates([], NOW)

if __name__=="__main__":
    unittest.main()
