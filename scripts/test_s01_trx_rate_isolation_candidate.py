"""Synthetic tests only; no live API, order, payment or site access."""
import io
import unittest
from scripts.s01_trx_rate_isolation_candidate import (
    parse_trx_only, fetch_trx_only, TrustedRateUnavailable,
    COINGECKO_TRX_ONLY_URL,
)

NOW = 1_800_000_000


class FakeResponse:
    status = 200
    def __init__(self, data, url=COINGECKO_TRX_ONLY_URL):
        self.data = io.BytesIO(data)
        self.url = url
    def __enter__(self): return self
    def __exit__(self, *_): return False
    def read(self, n): return self.data.read(n)
    def geturl(self): return self.url


class RateTests(unittest.TestCase):
    def test_fresh_trx_ignores_stale_eth(self):
        quote = parse_trx_only({
            "tron": {"usd": 0.23, "last_updated_at": NOW-2},
            "ethereum": {"usd": 2500, "last_updated_at": NOW-9000}
        }, now=NOW)
        self.assertEqual(str(quote.usd_per_trx), "0.23")

    def test_stale_trx_fails(self):
        with self.assertRaises(TrustedRateUnavailable):
            parse_trx_only({"tron":{"usd":0.23,"last_updated_at":NOW-301}},now=NOW)

    def test_future_trx_fails(self):
        with self.assertRaises(TrustedRateUnavailable):
            parse_trx_only({"tron":{"usd":0.23,"last_updated_at":NOW+46}},now=NOW)

    def test_boundary_freshness(self):
        self.assertEqual(parse_trx_only({
            "tron":{"usd":"0.25","last_updated_at":NOW-300}
        },now=NOW).age_seconds,300)

    def test_missing_trx_fails(self):
        with self.assertRaises(TrustedRateUnavailable):
            parse_trx_only({"ethereum":{"usd":2}},now=NOW)

    def test_missing_timestamp_fails(self):
        with self.assertRaises(TrustedRateUnavailable):
            parse_trx_only({"tron":{"usd":0.23}},now=NOW)

    def test_bool_price_fails(self):
        with self.assertRaises(TrustedRateUnavailable):
            parse_trx_only({"tron":{"usd":True,"last_updated_at":NOW}},now=NOW)

    def test_zero_price_fails(self):
        with self.assertRaises(TrustedRateUnavailable):
            parse_trx_only({"tron":{"usd":0,"last_updated_at":NOW}},now=NOW)

    def test_nan_price_fails(self):
        with self.assertRaises(TrustedRateUnavailable):
            parse_trx_only({"tron":{"usd":float('nan'),"last_updated_at":NOW}},now=NOW)

    def test_network_success(self):
        resp = FakeResponse(b'{"tron":{"usd":0.24,"last_updated_at":1800000000}}')
        quote = fetch_trx_only(clock=lambda:NOW, opener=lambda req, timeout:resp)
        self.assertEqual(str(quote.usd_per_trx),"0.24")

    def test_bad_origin_fails(self):
        resp = FakeResponse(
            b'{"tron":{"usd":0.24,"last_updated_at":1800000000}}',
            "http://evil.example"
        )
        with self.assertRaises(TrustedRateUnavailable):
            fetch_trx_only(clock=lambda:NOW,opener=lambda req,timeout:resp)

    def test_oversized_response_fails(self):
        with self.assertRaises(TrustedRateUnavailable):
            fetch_trx_only(
                clock=lambda:NOW,
                opener=lambda req,timeout:FakeResponse(b'x'*5000)
            )

    def test_malformed_json_fails(self):
        with self.assertRaises(TrustedRateUnavailable):
            fetch_trx_only(
                clock=lambda:NOW,
                opener=lambda req,timeout:FakeResponse(b'{')
            )

    def test_same_host_redirected_path_fails(self):
        resp = FakeResponse(
            b'{"tron":{"usd":0.24,"last_updated_at":1800000000}}',
            "https://api.coingecko.com/other/path"
        )
        with self.assertRaises(TrustedRateUnavailable):
            fetch_trx_only(clock=lambda: NOW, opener=lambda req, timeout: resp)

    def test_duplicate_tron_keys_fail(self):
        resp = FakeResponse(
            b'{"tron":{"usd":0.24,"last_updated_at":1800000000},'
            b'"tron":{"usd":0.25,"last_updated_at":1800000000}}'
        )
        with self.assertRaises(TrustedRateUnavailable):
            fetch_trx_only(clock=lambda: NOW, opener=lambda req, timeout: resp)

    def test_duplicate_usd_keys_fail(self):
        resp = FakeResponse(
            b'{"tron":{"usd":0.24,"usd":0.25,"last_updated_at":1800000000}}'
        )
        with self.assertRaises(TrustedRateUnavailable):
            fetch_trx_only(clock=lambda: NOW, opener=lambda req, timeout: resp)

    def test_nonfinite_clock_fails(self):
        resp = FakeResponse(
            b'{"tron":{"usd":0.24,"last_updated_at":1800000000}}'
        )
        with self.assertRaises(TrustedRateUnavailable):
            fetch_trx_only(clock=lambda: float("nan"), opener=lambda req, timeout: resp)

    def test_transport_failure_fails(self):
        def bad(*a,**kw): raise TimeoutError()
        with self.assertRaises(TrustedRateUnavailable):
            fetch_trx_only(clock=lambda:NOW,opener=bad)


if __name__ == '__main__':
    unittest.main()
