"""Synthetic contracts for read-only TRX source-shape classification."""
import ast
import unittest

from scripts.mpw_trx_live_runtime_shape_readonly_20261101 import classify


class ShapeTests(unittest.TestCase):
    def test_trx_only_source_contract(self):
        docs = {
            "buyer": "def fetch_server_rate(asset):\n    return fetch_fresh_rates(required_assets=(asset,))\n",
            "rates": (
                "def fetch_fresh_rates(*, required_assets=('TRX',)):\n"
                "    return parse_coin_gecko_rates({}, 1, required_assets=required_assets)\n"
                "def parse_coin_gecko_rates(doc, now, *, required_assets=('TRX',)):\n"
                "    return doc['last_updated_at']\n"
            ),
            "web": "def _rate_provider():\n    return fetch_server_rate('TRX')\n",
        }
        result = classify({name: ast.parse(code) for name, code in docs.items()})
        for k in ("buyer_requests_asset_only", "rate_fetch_accepts_assets",
                  "rate_parser_accepts_assets", "rate_parser_checks_observed_at",
                  "web_requests_native_trx"):
            self.assertTrue(result[k], k)
        self.assertFalse(result["passenger_effective_source_proven"])
        self.assertFalse(result["payment_created"])
        self.assertFalse(result["db_accessed"])
        self.assertFalse(result["release_permitted"])

    def test_legacy_eth_coupling_is_observable_without_source_export(self):
        docs = {
            "buyer": "def fetch_server_rate(asset):\n    return fetch_fresh_rates()\n",
            "rates": (
                "def fetch_fresh_rates():\n    return parse_coin_gecko_rates({}, 1)\n"
                "def parse_coin_gecko_rates(doc, now):\n    return doc\n"
            ),
            "web": "def _rate_provider():\n    return fetch_server_rate('TRX')\n",
        }
        result = classify({name: ast.parse(code) for name, code in docs.items()})
        for k in ("buyer_requests_asset_only", "rate_fetch_accepts_assets",
                  "rate_parser_accepts_assets", "rate_parser_checks_observed_at"):
            self.assertFalse(result[k], k)
        self.assertTrue(result["web_requests_native_trx"])


if __name__ == "__main__":
    unittest.main()
