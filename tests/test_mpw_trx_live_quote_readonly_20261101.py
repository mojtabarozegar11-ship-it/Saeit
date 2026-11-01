"""No-network TRX market quote preflight regression."""
import json
import unittest

from scripts.mpw_trx_live_quote_readonly_20261101 import URL, quote_ready

NOW = 1800000000


class Response:
    status = 200

    def __init__(self, payload, *, url=URL, status=200):
        self.payload = payload
        self.url = url
        self.status = status

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def geturl(self):
        return self.url

    def read(self, limit):
        return self.payload[:limit]


def quote(*, age=5, usd="0.25", url=URL, status=200):
    body = json.dumps(
        {"tron": {"usd": usd, "last_updated_at": NOW - age}}
    ).encode()
    return lambda req, timeout: Response(body, url=url, status=status)


class QuotePreflightTests(unittest.TestCase):
    def test_fresh_native_trx_is_accepted_without_real_network(self):
        self.assertTrue(quote_ready(fetch=quote(age=2), now=NOW))

    def test_stale_future_redirect_and_http_errors_block(self):
        for f in (
            quote(age=91), quote(age=-1), quote(usd="NaN"),
            quote(url="https://wrong.example/"), quote(status=500),
            quote(usd="0"), quote(usd="1000"),
        ):
            with self.subTest(case=str(f)):
                self.assertFalse(quote_ready(fetch=f, now=NOW))

    def test_duplicate_json_fields_are_rejected(self):
        raw = b'{"tron":{"usd":"0.25","usd":"0.30","last_updated_at":1800000000}}'
        self.assertFalse(quote_ready(fetch=lambda req, timeout: Response(raw),
                                      now=NOW))

    def test_network_error_is_fail_closed(self):
        def unavailable(req, timeout):
            raise TimeoutError("synthetic no network")
        self.assertFalse(quote_ready(fetch=unavailable, now=NOW))


if __name__ == "__main__":
    unittest.main()
