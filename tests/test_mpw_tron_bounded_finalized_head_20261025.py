"""Regression: huge chunked TRON blocks must not stall finalized-head verification."""
import io
import json
import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from services.mpw_trx_commercial_chain import (
    PINNED, _NoRedirect, _bounded_solidified_head, read_only_independent_pair,
)
from scripts.mpw_tron_public_dual_probe_readonly_20261023 import head_height_and_age


class Headers:
    def get_content_type(self):
        return "application/json"


class FakeResponse:
    status = 200
    headers = Headers()
    def __init__(self, body):
        self.body = io.BytesIO(body)
        self.bytes_requested = []
    def __enter__(self):
        return self
    def __exit__(self, *exc):
        self.body.close()
    def read(self, size):
        self.bytes_requested.append(size)
        if size > 4096:
            raise AssertionError("A whole-block read is forbidden for head-only proof")
        return self.body.read(size)


class FakeOpener:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.calls = []
    def open(self, request, timeout):
        self.calls.append((request.full_url, request.get_method(), timeout))
        return next(self.responses)


def head_body(padding=2_000_000):
    header = {
        "blockID": "a"*64,
        "block_header": {"raw_data": {
            "number": 90000000,
            "timestamp": int(datetime.now(timezone.utc).timestamp()*1000),
            "witness_address": "00",
        }},
        "transactions": [{"unimportant": "x"*padding}],
    }
    return json.dumps(header, separators=(",", ":")).encode("ascii")


class BoundedHeadTests(unittest.TestCase):
    def test_huge_chunked_block_consumes_only_prefix(self):
        provider = PINNED[0]
        response = FakeResponse(head_body())
        opener = FakeOpener([response])
        with patch("services.mpw_trx_commercial_chain.urllib.request.build_opener", return_value=opener):
            result = _bounded_solidified_head(provider)
        self.assertEqual(result["block_header"]["raw_data"]["number"], 90000000)
        self.assertEqual(response.bytes_requested, [4096])
        self.assertEqual(opener.calls[0][0], provider[1]+"/walletsolidity/getnowblock")
        self.assertEqual(opener.calls[0][1], "GET")
        head_height_and_age(result, datetime.now(timezone.utc))

    def test_dual_provider_independence_preserved(self):
        left, right = FakeResponse(head_body()), FakeResponse(head_body())
        opener = FakeOpener([left,right])
        with patch("services.mpw_trx_commercial_chain.urllib.request.build_opener", return_value=opener):
            pair = read_only_independent_pair()
        self.assertNotEqual(pair.identifier_a, pair.identifier_b)
        self.assertEqual(len(opener.calls), 2)
        self.assertEqual([c[0] for c in opener.calls],
                         [p[1]+"/walletsolidity/getnowblock" for p in PINNED])

    def test_unapproved_operator_rejected_before_network(self):
        with self.assertRaises(ValueError):
            _bounded_solidified_head(("unapproved", "https://example.invalid"))
        self.assertIsNone(_NoRedirect().redirect_request(None,None,None,None,None,None))

    def test_truncated_head_fails_closed(self):
        response=FakeResponse(b'{"block_header":{"raw_data":')
        with patch("services.mpw_trx_commercial_chain.urllib.request.build_opener",
                   return_value=FakeOpener([response])):
            with self.assertRaises(ValueError):
                _bounded_solidified_head(PINNED[0])

    def test_invalid_json_fails_closed(self):
        response=FakeResponse(b'{"block_header":{"raw_data":{"number":abc}}}')
        with patch("services.mpw_trx_commercial_chain.urllib.request.build_opener",
                   return_value=FakeOpener([response])):
            with self.assertRaises(ValueError):
                _bounded_solidified_head(PINNED[0])


if __name__ == "__main__":
    unittest.main()
