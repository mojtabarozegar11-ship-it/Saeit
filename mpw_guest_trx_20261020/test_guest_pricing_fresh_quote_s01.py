"""Offline, deterministic S-01 TRX quote QA; no wallet, DB, order or payment."""
import importlib.util
import json
from decimal import Decimal
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch

MODULE = Path(__file__).with_name("guest_pricing.py")
NOW = 1793470000

commerce = types.ModuleType("mpw_commerce")
commerce.__path__ = []
invoicing = types.ModuleType("mpw_commerce.invoicing")
invoicing.RECEIVERS = {"TRX": ("tron-mainnet", "TMockAddress", 6)}
scripts = types.ModuleType("scripts")
scripts.__path__ = []
verify = types.ModuleType("scripts.mojplaywin_native_chain_verify")
verify.tron_address_to_hex = lambda address: "00"
with patch.dict(sys.modules, {
    "mpw_commerce": commerce, "mpw_commerce.invoicing": invoicing,
    "scripts": scripts, "scripts.mojplaywin_native_chain_verify": verify,
}):
    spec = importlib.util.spec_from_file_location("s01_guest_pricing", MODULE)
    pricing = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(pricing)


class Response:
    def __init__(self, body, *, url=None, status=200):
        self.body = body
        self.url = pricing.TRX_QUOTE_URL if url is None else url
        self.status = status
    def geturl(self):
        return self.url
    def read(self, count):
        return self.body[:count]
    def __enter__(self):
        return self
    def __exit__(self, *_):
        return False


def payload(value="0.285", updated=NOW):
    return json.dumps({"tron": {"usd": value, "last_updated_at": updated}}).encode()


class QuoteTests(unittest.TestCase):
    def invoke(self, body=None, *, url=None, status=200, error=None):
        response = Response(payload() if body is None else body, url=url, status=status)
        with patch("time.time", return_value=NOW), patch.object(
            pricing, "urlopen", side_effect=error, return_value=response
        ) as opened:
            result = pricing.price_usd()
            self.assertEqual(opened.call_args.kwargs["timeout"], 9)
            self.assertEqual(opened.call_args.args[0].full_url, pricing.TRX_QUOTE_URL)
            return result

    def test_fresh_quote_keeps_decimal_contract(self):
        self.assertEqual(self.invoke(), Decimal("0.285"))

    def test_90_second_boundary(self):
        self.assertEqual(self.invoke(payload(updated=NOW-90)), Decimal("0.285"))
        with self.assertRaises(ValueError):
            self.invoke(payload(updated=NOW-91))

    def test_future_quote_refused(self):
        with self.assertRaises(ValueError):
            self.invoke(payload(updated=NOW+1))

    def test_missing_timestamp_refused(self):
        with self.assertRaises(ValueError):
            self.invoke(b'{"tron":{"usd":0.285}}')

    def test_bad_prices_refused(self):
        for value in (0, -1, 101, "NaN", "Infinity", True, [], None):
            with self.subTest(value=value), self.assertRaises((ValueError, TypeError)):
                self.invoke(payload(value=value))

    def test_duplicate_keys_refused(self):
        with self.assertRaises(ValueError):
            self.invoke(b'{"tron":{"usd":0.2,"usd":0.3,"last_updated_at":1793470000}}')

    def test_missing_observation_refused(self):
        with self.assertRaises(ValueError):
            self.invoke(b'{"ethereum":{"usd":0.3}}')

    def test_bad_json_refused(self):
        with self.assertRaises(ValueError):
            self.invoke(b'{"tron":')

    def test_oversized_refused(self):
        with self.assertRaises(ValueError):
            self.invoke(b"X" * 2049)

    def test_redirect_refused(self):
        with self.assertRaises(ValueError):
            self.invoke(url="https://example.org/")

    def test_non_200_refused(self):
        with self.assertRaises(ValueError):
            self.invoke(status=429)

    def test_transport_failure_refused(self):
        with self.assertRaises(TimeoutError):
            self.invoke(error=TimeoutError("offline"))

    def test_receiver_contract_preserved(self):
        self.assertEqual(pricing.receive_wallet(), "TMockAddress")


if __name__ == "__main__":
    unittest.main()
