"""Regression coverage for the observed full-block response size."""
from datetime import datetime, timezone
import json
from unittest import TestCase
from unittest.mock import patch, MagicMock

from services.mpw_tron_independent_solidified_rpc import RpcProvider, solidified_head_height, _post
from services.mpw_trx_walletless_core import PaymentHold


class FinalizedHeadResponseLimitTests(TestCase):
    provider = RpcProvider("test-a", "operator-a", "https://example.com")
    now = datetime(2026, 11, 19, tzinfo=timezone.utc)

    def response(self, payload):
        response = MagicMock()
        response.status = 200
        response.headers = {"Content-Type": "application/json; charset=utf-8"}
        response.read.side_effect = lambda n: payload[:n]
        opener = MagicMock()
        opener.open.return_value.__enter__.return_value = response
        return opener

    def test_realistic_large_head_accepted(self):
        payload = json.dumps({"block_header": {"raw_data": {
            "number": 88140047, "timestamp": int(self.now.timestamp()*1000)-54000,
        }}, "transactions": ["x"*200000]}).encode()
        with patch("urllib.request.build_opener", return_value=self.response(payload)):
            self.assertEqual(solidified_head_height(self.provider, self.now), 88140047)

    def test_transaction_proof_limit_not_relaxed(self):
        payload = b"x"*150001
        with patch("urllib.request.build_opener", return_value=self.response(payload)):
            with self.assertRaises(PaymentHold):
                _post(self.provider, "/walletsolidity/gettransactionbyid", "a"*64)

    def test_large_head_still_bounded(self):
        payload = b"x"*2000001
        with patch("urllib.request.build_opener", return_value=self.response(payload)):
            with self.assertRaises(PaymentHold):
                solidified_head_height(self.provider, self.now)
