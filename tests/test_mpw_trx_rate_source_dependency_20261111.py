"""No-network quote contract for native walletless TRX invoice creation."""
import json
import ast
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from scripts import mojplaywin_direct_wallet_rates as rates


NOW = 1794384000


class Response:
    status = 200
    headers = SimpleNamespace(get_content_type=lambda: 'application/json')

    def __init__(self, body, *, destination=rates.URL):
        self.payload = body
        self.destination = destination

    def geturl(self):
        return self.destination

    def read(self, size):
        return self.payload[:size]

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def sample(**updates):
    values = {
        'ethereum': {'usd': 2000, 'last_updated_at': NOW-18},
        'tron': {'usd': '0.32', 'last_updated_at': NOW-22},
    }
    values.update(updates)
    return json.dumps(values).encode()


def quote(body=None, *, destination=rates.URL, assets=('ETH', 'TRX')):
    return rates.fetch_fresh_rates(
        opener=lambda request, timeout: Response(sample() if body is None else body,
                                                 destination=destination),
        now_epoch=NOW, assets=assets,
    )


class ServerOnlyMarketRatesContract(unittest.TestCase):
    def test_actual_two_asset_quote_contract(self):
        snapshot = quote()
        self.assertEqual(set(snapshot), {'ETH', 'TRX'})
        self.assertEqual(str(snapshot['TRX'].usd_per_asset), '0.32')
        self.assertEqual(snapshot['TRX'].observed_at_epoch, NOW-22)
        self.assertEqual(snapshot['TRX'].provider, 'coingecko')

    def test_trx_checkout_does_not_depend_on_eth_price(self):
        trx_only = sample(ethereum=None)
        self.assertEqual(set(quote(trx_only, assets=('TRX',))), {'TRX'})
        with self.assertRaises(rates.RateFeedUnavailable):
            quote(trx_only)

    def test_asset_selection_cannot_be_widened_or_buyer_defined(self):
        for selection in ((), ('BTC',), ['TRX', 'TRX'], 'TRX', (True,)):
            with self.subTest(selection=selection):
                with self.assertRaises(rates.RateFeedUnavailable):
                    quote(assets=selection)

    def test_stale_or_future_timestamp_rejected(self):
        for delta in (76, -1):
            with self.subTest(delta=delta):
                with self.assertRaises(rates.RateFeedUnavailable):
                    quote(sample(tron={'usd': '0.32', 'last_updated_at': NOW-delta}))

    def test_missing_updated_at_and_bad_price_rejected(self):
        for item in ({'usd': 0.32},
                     {'usd': 'nan', 'last_updated_at': NOW-2},
                     {'usd': -1, 'last_updated_at': NOW-2},
                     {'usd': True, 'last_updated_at': NOW-2}):
            with self.subTest(item=item):
                with self.assertRaises(rates.RateFeedUnavailable):
                    quote(sample(tron=item))

    def test_unexpected_json_and_missing_currency_rejected(self):
        for body in (b'[]', b'{broken', sample(tron=None)):
            with self.subTest(body=body):
                with self.assertRaises(rates.RateFeedUnavailable):
                    quote(body)

    def test_redirect_and_unbounded_response_rejected(self):
        with self.assertRaises(rates.RateFeedUnavailable):
            quote(destination='https://another.example.invalid/rate')
        with self.assertRaises(rates.RateFeedUnavailable):
            quote(b' ' * (rates.MAX_BYTES+1))

    def test_http_error_and_network_failure_rejected(self):
        response = Response(sample())
        response.status = 503
        with self.assertRaises(rates.RateFeedUnavailable):
            rates.fetch_fresh_rates(opener=lambda request, timeout: response, now_epoch=NOW)

        def offline(request, timeout):
            raise TimeoutError('upstream timeout')
        with self.assertRaises(rates.RateFeedUnavailable):
            rates.fetch_fresh_rates(opener=offline, now_epoch=NOW)

    def test_buyer_rate_adapter_requests_only_trx(self):
        source = Path(__file__).resolve().parents[1] / 'mpw_commerce/buyer_wallets.py'
        tree = ast.parse(source.read_text('utf-8'))
        function = next(node for node in tree.body
                        if isinstance(node, ast.FunctionDef)
                        and node.name == 'fetch_server_rate')
        scope = {'RECEIVERS': {'TRX': ('tron-mainnet', 'destination', 6)},
                 'WalletLinkRejected': ValueError,
                 'datetime': datetime, 'utc_timezone': timezone, 'Decimal': Decimal,
                 'TrustedRate': lambda **values: SimpleNamespace(**values)}
        exec(compile(ast.Module(body=[function], type_ignores=[]), str(source), 'exec'), scope)
        with patch.object(rates, 'fetch_fresh_rates', return_value={
                'TRX': rates.FreshRate(Decimal('0.32'), 'coingecko', NOW-22),
        }) as fetch:
            quote = scope['fetch_server_rate']('TRX')
        fetch.assert_called_once_with(assets=('TRX',))
        self.assertEqual(quote.usd_per_asset, Decimal('0.32'))
        self.assertEqual(quote.source, 'coingecko')


if __name__ == '__main__':
    unittest.main()
