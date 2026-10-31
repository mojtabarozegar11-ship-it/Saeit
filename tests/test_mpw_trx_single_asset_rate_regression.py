"""Synthetic TRX/ETH rate isolation regression; no network, DB or order."""
import io
import unittest
from scripts.mojplaywin_direct_wallet_rates import (
    RateFeedUnavailable, parse_coin_gecko_rates, fetch_fresh_rates,
    COINGECKO_URL,
)

NOW = 1800000000


def rates(trx_age=3, eth_age=3):
    return {
        "tron": {"usd": "0.25", "last_updated_at": NOW - trx_age},
        "ethereum": {"usd": "2500", "last_updated_at": NOW - eth_age},
    }


class Response:
    def __init__(self, payload):
        self.data = io.BytesIO(payload)
    def __enter__(self): return self
    def __exit__(self, *_): return False
    def read(self, n): return self.data.read(n)


class SingleAssetRateTests(unittest.TestCase):
    def test_fresh_trx_ignores_expired_eth(self):
        quote = parse_coin_gecko_rates(
            rates(trx_age=5, eth_age=900), NOW, required_assets=("TRX",)
        )
        self.assertEqual(tuple(quote), ("TRX",))
        self.assertEqual(quote["TRX"].usd_per_asset, "0.25")

    def test_trx_only_fetch_does_not_require_eth(self):
        payload = b'{"tron":{"usd":0.25,"last_updated_at":1799999995},"ethereum":{"usd":2500,"last_updated_at":1799999000}}'
        fetched = []
        def fetch(url, timeout):
            fetched.append((url, timeout))
            return Response(payload)
        quote = fetch_fresh_rates(fetch=fetch, now=NOW, required_assets=("TRX",))
        self.assertEqual(tuple(quote), ("TRX",))
        self.assertEqual(fetched, [(COINGECKO_URL, 12)])

    def test_expired_trx_is_still_rejected(self):
        with self.assertRaisesRegex(RateFeedUnavailable, "stale"):
            parse_coin_gecko_rates(rates(trx_age=91), NOW, required_assets=("TRX",))

    def test_90_second_boundary_remains_valid(self):
        self.assertEqual(
            parse_coin_gecko_rates(rates(trx_age=90), NOW, required_assets=("TRX",))["TRX"].observed_at_epoch,
            NOW - 90,
        )

    def test_future_trx_is_rejected(self):
        with self.assertRaisesRegex(RateFeedUnavailable, "future"):
            parse_coin_gecko_rates(rates(trx_age=-1), NOW, required_assets=("TRX",))

    def test_missing_requested_trx_is_rejected(self):
        with self.assertRaisesRegex(RateFeedUnavailable, "Missing"):
            parse_coin_gecko_rates({"ethereum": rates()["ethereum"]}, NOW, required_assets=("TRX",))

    def test_bad_trx_price_is_rejected(self):
        doc = rates()
        doc["tron"]["usd"] = "NaN"
        with self.assertRaises(RateFeedUnavailable):
            parse_coin_gecko_rates(doc, NOW, required_assets=("TRX",))

    def test_both_assets_default_still_requires_both_fresh(self):
        with self.assertRaisesRegex(RateFeedUnavailable, "ETH"):
            parse_coin_gecko_rates(rates(eth_age=900), NOW)

    def test_eth_only_ignores_expired_trx(self):
        self.assertEqual(
            tuple(parse_coin_gecko_rates(rates(trx_age=900), NOW, required_assets=("ETH",))),
            ("ETH",),
        )

    def test_invalid_selector_fails_closed(self):
        for requested in ((), ("FOO",), ("TRX", "TRX"), ["TRX"], ("TRX", "ETH")):
            with self.subTest(requested=requested), self.assertRaises(RateFeedUnavailable):
                parse_coin_gecko_rates(rates(), NOW, required_assets=requested)


    def _isolated_buyer_rate_loader(self):
        # Compile only the real source function with inert dependencies.
        # No Django setup, order, database, network, session or wallet.
        import ast
        from datetime import datetime, timezone
        from decimal import Decimal
        from pathlib import Path
        from types import SimpleNamespace
        source = Path(__file__).resolve().parents[1] / "mpw_commerce/buyer_wallets.py"
        tree = ast.parse(source.read_text("utf8"))
        nodes = [n for n in tree.body if isinstance(n, ast.FunctionDef)
                 and n.name == "fetch_server_rate"]
        self.assertEqual(len(nodes), 1)
        ns = {"RECEIVERS": {"TRX": ("tron-mainnet", "synthetic", 6)},
              "WalletLinkRejected": ValueError,
              "TrustedRate": SimpleNamespace, "datetime": datetime,
              "utc_timezone": timezone, "Decimal": Decimal}
        exec(compile(ast.Module(body=nodes, type_ignores=[]),
                     "<isolated-rate-loader>", "exec"), ns)
        return ns["fetch_server_rate"]

    def test_buyer_loader_requests_only_trx_and_preserves_source_timestamp(self):
        from unittest.mock import patch
        from types import SimpleNamespace
        from scripts import mojplaywin_direct_wallet_rates as feed
        calls = []
        def fake_feed(*, required_assets):
            calls.append(required_assets)
            return {"TRX": SimpleNamespace(usd_per_asset="0.25",
                                         observed_at_epoch=NOW-5,
                                         provider="coingecko")}
        with patch.object(feed, "fetch_fresh_rates", fake_feed):
            quote = self._isolated_buyer_rate_loader()("TRX")
        self.assertEqual(calls, [("TRX",)])
        self.assertEqual(str(quote.usd_per_asset), "0.25")
        self.assertEqual(quote.source, "coingecko")
        self.assertEqual(int(quote.observed_at.timestamp()), NOW-5)

    def test_buyer_loader_maps_unavailable_trx_to_fail_closed(self):
        from unittest.mock import patch
        from scripts import mojplaywin_direct_wallet_rates as feed
        with patch.object(feed, "fetch_fresh_rates",
                          side_effect=RateFeedUnavailable("stale TRX")):
            with self.assertRaisesRegex(ValueError, "Trusted server rate unavailable"):
                self._isolated_buyer_rate_loader()("TRX")


if __name__ == "__main__":
    unittest.main()
