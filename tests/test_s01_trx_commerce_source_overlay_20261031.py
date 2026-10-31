"""S-01 TRX checkout exact-source one-file overlay: fail-closed synthetic QA.

No live commerce imports, DB queries, invoices, orders, network calls or writes.
"""
import ast
from decimal import Decimal
import json
import sys
from types import ModuleType
import unittest
from unittest.mock import patch

from scripts import s01_trx_commerce_source_overlay_20261031 as overlay

BASE = '''def _rate_provider():
    from mpw_commerce.buyer_wallets import fetch_server_rate
    quote=fetch_server_rate("TRX")
    return quote.usd_per_asset, quote.observed_at

def unrelated(value):
    return value * 2
'''
URL = ("https://api.coingecko.com/api/v3/simple/price"
       "?ids=tron&vs_currencies=usd&include_last_updated_at=true")
NOW = 1793470000


class RateFeedUnavailable(Exception):
    pass


class FakeResponse:
    def __init__(self, body, *, url=URL, status=200):
        self.body, self.url, self.status = body, url, status
    def geturl(self):
        return self.url
    def read(self, count):
        return self.body[:count]
    def __enter__(self):
        return self
    def __exit__(self, *_):
        return False


def quote(price="0.285", timestamp=NOW):
    return json.dumps({"tron": {"usd": price,
                                "last_updated_at": timestamp}}).encode("utf8")


class TrxCommerceOverlayTests(unittest.TestCase):
    def candidate(self, source=BASE):
        raw = source.encode("utf8")
        return overlay.build(raw, expected_sha256=overlay.digest(raw))

    def invoke(self, *, body=None, url=URL, status=200, error=None):
        fn = overlay._function(ast.parse(self.candidate()))
        namespace = {}
        exec(compile(ast.Module(body=[fn], type_ignores=[]),
                     "<synthetic-quote-provider>", "exec"), namespace)
        market = ModuleType("scripts.mojplaywin_direct_wallet_rates")
        market.RateFeedUnavailable = RateFeedUnavailable
        with patch.dict(sys.modules, {"scripts.mojplaywin_direct_wallet_rates": market}), \
             patch("time.time", return_value=NOW), \
             patch("urllib.request.urlopen", side_effect=error,
                   return_value=FakeResponse(quote() if body is None else body,
                                             url=url, status=status)):
            return namespace["_rate_provider"]()

    def test_preserves_unrelated_source_and_tuple_contract(self):
        candidate = self.candidate()
        self.assertIn(b"def unrelated(value):\n    return value * 2", candidate)
        self.assertNotIn(b'fetch_server_rate("TRX")', candidate)
        self.assertNotIn(b"s01_trx_rate_isolation_candidate", candidate)
        fn = overlay._function(ast.parse(candidate))
        self.assertFalse(any(isinstance(n, ast.Name) and n.id == "fetch_server_rate"
                             for n in ast.walk(fn)))

    def test_fresh_trx_preserves_decimal_and_timestamp(self):
        self.assertEqual(self.invoke(), (Decimal("0.285"), NOW))

    def test_stale_trx_fails_closed(self):
        with self.assertRaises(RateFeedUnavailable):
            self.invoke(body=quote(timestamp=NOW-301))

    def test_future_trx_fails_closed(self):
        with self.assertRaises(RateFeedUnavailable):
            self.invoke(body=quote(timestamp=NOW+46))

    def test_out_of_range_trx_fails_closed(self):
        for price in ("0", "-0.2", "150", "NaN", "Infinity"):
            with self.subTest(price=price), self.assertRaises(RateFeedUnavailable):
                self.invoke(body=quote(price=price))

    def test_invalid_price_type_fails_closed(self):
        for price in (True, [], None, {}):
            with self.subTest(price=price), self.assertRaises(RateFeedUnavailable):
                self.invoke(body=quote(price=price))

    def test_duplicate_market_key_fails_closed(self):
        with self.assertRaises(RateFeedUnavailable):
            self.invoke(body=b'{"tron":{"usd":0.2,"usd":0.3,"last_updated_at":1793470000}}')

    def test_bad_json_fails_closed(self):
        with self.assertRaises(RateFeedUnavailable):
            self.invoke(body=b'{"tron":')

    def test_missing_trx_observation_fails_closed(self):
        with self.assertRaises(RateFeedUnavailable):
            self.invoke(body=b'{"ethereum":{"usd":0.2}}')

    def test_missing_timestamp_fails_closed(self):
        with self.assertRaises(RateFeedUnavailable):
            self.invoke(body=b'{"tron":{"usd":0.2}}')

    def test_redirect_fails_closed(self):
        with self.assertRaises(RateFeedUnavailable):
            self.invoke(url="https://example.org/redirect")

    def test_http_failure_fails_closed(self):
        with self.assertRaises(RateFeedUnavailable):
            self.invoke(status=429)

    def test_oversized_response_fails_closed(self):
        with self.assertRaises(RateFeedUnavailable):
            self.invoke(body=b"x"*4097)

    def test_transport_failure_fails_closed(self):
        with self.assertRaises(RateFeedUnavailable):
            self.invoke(error=TimeoutError("network timeout"))

    def test_source_drift_refused(self):
        with self.assertRaisesRegex(overlay.SourceContractChanged, "SHA drift"):
            overlay.build(BASE.encode("utf8"))

    def test_tuple_order_change_refused(self):
        changed = BASE.replace(
            "return quote.usd_per_asset, quote.observed_at",
            "return quote.observed_at, quote.usd_per_asset")
        with self.assertRaisesRegex(overlay.SourceContractChanged, "Return field"):
            self.candidate(changed)

    def test_extra_side_effect_refused(self):
        changed = BASE.replace('quote=fetch_server_rate("TRX")',
                               'print("unexpected")\n    quote=fetch_server_rate("TRX")')
        with self.assertRaisesRegex(overlay.SourceContractChanged, "body changed"):
            self.candidate(changed)

    def test_unrecognized_rate_error_contract_refused(self):
        changed = BASE.replace(
            "from mpw_commerce.buyer_wallets import fetch_server_rate",
            "from scripts.changed_rate_module import fetch_server_rate")
        with self.assertRaisesRegex(overlay.SourceContractChanged, "original import"):
            self.candidate(changed)

    def test_actual_source_ast_smoke_with_stubs(self):
        overlay.actual_source_in_memory_smoke(self.candidate())

    def test_no_install_mode_exists(self):
        self.assertFalse(hasattr(overlay, "install"))
        self.assertFalse(hasattr(overlay, "publish"))


if __name__ == "__main__":
    unittest.main()
