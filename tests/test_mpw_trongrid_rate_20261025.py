"""Offline controls for production TronGrid HTTP429 and coordinated pacing."""
import io
import json
import os
import stat
import tempfile
import time
import unittest
import urllib.error
from email.message import Message
from pathlib import Path
from unittest.mock import patch

from services import mpw_tron_readonly_deposit_candidates as indexer
from services.mpw_trx_walletless_core import PaymentHold

URL = "https://api.trongrid.io/v1/accounts/ABCDEF/transactions"


class FakeResponse:
    status = 200
    headers = Message()
    headers["Content-Type"] = "application/json"
    def __init__(self, document=b'{"success":true,"data":[]}'):
        self.document = document
    def __enter__(self):
        return self
    def __exit__(self, *args):
        return False
    def read(self, limit):
        return self.document[:limit]


class FakeOpener:
    def __init__(self, results):
        self.results = iter(results)
        self.requests = []
    def open(self, request, timeout):
        self.requests.append(request)
        item = next(self.results)
        if isinstance(item, BaseException):
            raise item
        return item


def http_error(status):
    return urllib.error.HTTPError(URL, status, "sanitized", {}, io.BytesIO(b""))


class IndexerThrottleTests(unittest.TestCase):
    def request_with(self, results, key=""):
        opener = FakeOpener(results)
        with patch.dict(os.environ, {"MPW_TRONGRID_API_KEY": key}), \
             patch.object(indexer, "_paced_slot") as pace, \
             patch.object(indexer.urllib.request, "build_opener", return_value=opener):
            result = indexer.fetch_page(URL)
        return result, pace, opener

    def test_http429_retries_exactly_once_after_safe_pacing(self):
        result, pace, opener = self.request_with([http_error(429), FakeResponse()])
        self.assertEqual(result, {"success":True,"data":[]})
        self.assertEqual(pace.call_count, 2)
        self.assertEqual(len(opener.requests), 2)

    def test_persistent_http429_fails_closed(self):
        with self.assertRaisesRegex(PaymentHold, "rate limited"):
            self.request_with([http_error(429),http_error(429)])

    def test_http403_fails_closed_without_retry(self):
        with self.assertRaisesRegex(PaymentHold, "authorization unavailable"):
            self.request_with([http_error(403)])

    def test_optional_key_only_in_http_header(self):
        result, pace, opener = self.request_with([FakeResponse()],key="A"*24)
        self.assertEqual(result["success"],True)
        self.assertEqual(pace.call_args.args, (True,))
        self.assertEqual(opener.requests[0].get_header("Tron-pro-api-key"),"A"*24)

    def test_invalid_key_blocked(self):
        with patch.dict(os.environ,{"MPW_TRONGRID_API_KEY":"bad\nheader"}), \
             self.assertRaises(PaymentHold):
            indexer.fetch_page(URL)

    def test_private_rate_gate_no_financial_data(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            (root/".local"/"share").mkdir(parents=True)
            with patch.object(indexer.Path,"home",return_value=root):
                indexer._paced_slot(authenticated=False)
            file=root/".local"/"share"/"mpw_trongrid_readonly_rate_gate_v1"
            self.assertTrue(file.is_file())
            self.assertEqual(stat.S_IMODE(file.stat().st_mode),0o600)
            stored=file.read_text("ascii").strip()
            self.assertTrue(0 < float(stored)-time.monotonic() <= 8.5)
            self.assertNotIn("TRON",stored)


if __name__ == "__main__":
    unittest.main()
