"""No live HTTP is used: deterministic fetcher security and handoff tests."""
from unittest.mock import patch
import socket
import pytest
from core.factory_research_v2_fetcher import UnsafeSource, public_addresses, fetch_source


def test_reject_private_or_mixed_dns():
    answers = [
        (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.215.14", 443)),
        (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 443)),
    ]
    with patch("socket.getaddrinfo", return_value=answers):
        with pytest.raises(UnsafeSource):
            public_addresses("example.org")


@pytest.mark.parametrize("url", [
    "http://example.org/", "https://localhost/", "https://host.internal/",
    "https://127.0.0.1/", "https://[::1]/", "https://example.org:8443/",
    "https://user:pass@example.org/", "https://example.org/#fragment",
    "https://example.org/ bad",
])
def test_reject_unsafe_urls_before_dns(url):
    with patch("socket.getaddrinfo", side_effect=AssertionError("DNS must not run")):
        with pytest.raises(UnsafeSource):
            fetch_source(url)


def test_fetch_pins_dns_and_returns_bytes():
    body = b"Evidence " * 20
    class Response:
        status = 200
        def getheader(self, key, default=""):
            return {"Content-Type": "text/html; charset=utf-8",
                    "Content-Length": str(len(body))}.get(key, default)
        def read(self, n):
            assert n == 256001
            return body
    class Connection:
        def __init__(self, host, ip, *, timeout):
            assert (host, ip) == ("example.org", "93.184.215.14")
        def request(self, method, path, headers):
            assert method == "GET" and path == "/guide?q=1"
            assert headers["Host"] == "example.org"
        def getresponse(self):
            return Response()
        def close(self):
            pass
    with patch("core.factory_research_v2_fetcher.public_addresses",
               return_value=["93.184.215.14"]), patch(
                   "core.factory_research_v2_fetcher._PinnedHTTPS", Connection):
        assert fetch_source("https://example.org/guide?q=1") == (body, "text/html")


def test_redirect_rejected():
    class Response:
        status = 302
    class Connection:
        def __init__(self, *args, **kwargs):
            pass
        def request(self, *args, **kwargs):
            pass
        def getresponse(self):
            return Response()
        def close(self):
            pass
    with patch("core.factory_research_v2_fetcher.public_addresses",
               return_value=["93.184.215.14"]), patch(
                   "core.factory_research_v2_fetcher._PinnedHTTPS", Connection):
        with pytest.raises(UnsafeSource):
            fetch_source("https://example.org/redirect")
