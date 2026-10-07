"""Bounded HTTPS source fetch with public-IP pinning; no redirects or proxies.

Standalone on purpose: safe to test before the deployed Django model reconciliation.
"""
import http.client
import ipaddress
import socket
import ssl
from urllib.parse import urlsplit


class UnsafeSource(ValueError):
    pass


def public_addresses(host):
    """Resolve once; reject the entire answer set if ANY address is non-global."""
    try:
        answers = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
    except (OSError, UnicodeError) as exc:
        raise UnsafeSource("DNS resolution failed") from exc
    addresses = []
    for answer in answers:
        address = answer[4][0]
        try:
            ip = ipaddress.ip_address(address)
        except ValueError as exc:
            raise UnsafeSource("Invalid DNS answer") from exc
        if not ip.is_global:
            raise UnsafeSource("DNS answer contains non-public address")
        if address not in addresses:
            addresses.append(address)
    if not addresses:
        raise UnsafeSource("No usable DNS answers")
    return addresses


class _PinnedHTTPS(http.client.HTTPSConnection):
    def __init__(self, hostname, ip, *, timeout):
        super().__init__(hostname, port=443, timeout=timeout,
                         context=ssl.create_default_context())
        self._pinned_ip = ip

    def connect(self):
        # socket.create_connection sees ONLY the already validated IP.
        sock = socket.create_connection((self._pinned_ip, 443), self.timeout)
        try:
            self.sock = self._context.wrap_socket(sock, server_hostname=self.host)
        except BaseException:
            sock.close()
            raise


def fetch_source(url, *, timeout=6, byte_limit=256_000):
    """Return (body bytes, MIME) or fail closed; caller persists source-job result."""
    if not isinstance(url, str) or len(url) > 1800 or any(ord(c) <= 32 or ord(c) == 127 for c in url):
        raise UnsafeSource("Malformed URL")
    try:
        parsed = urlsplit(url)
        host = parsed.hostname
        if (parsed.scheme != "https" or not host or parsed.username is not None
                or parsed.password is not None or parsed.fragment
                or parsed.port not in (None, 443) or host.endswith(".")):
            raise UnsafeSource("Only HTTPS public hostnames on port 443 are accepted")
        ipaddress.ip_address(host)
        raise UnsafeSource("IP literals are not accepted")
    except ValueError as exc:
        if isinstance(exc, UnsafeSource):
            raise
        if not host or "." not in host or host.lower().endswith(
            (".localhost", ".local", ".internal", ".test", ".invalid")
        ) or host.lower() in ("localhost", "localhost.localdomain"):
            raise UnsafeSource("Unsafe hostname") from exc
    if not 1 <= timeout <= 20 or not 100 <= byte_limit <= 256_000:
        raise ValueError("Fetch bounds exceeded")
    addresses = public_addresses(host)
    path = parsed.path or "/"
    if parsed.query:
        path += "?" + parsed.query
    connection = _PinnedHTTPS(host, addresses[0], timeout=timeout)
    try:
        connection.request("GET", path, headers={
            "Host": host, "User-Agent": "MojFactoryResearch/2.0",
            "Accept": "text/html,text/plain", "Accept-Encoding": "identity",
            "Connection": "close",
        })
        response = connection.getresponse()
        if response.status != 200:
            raise UnsafeSource("Non-success status or redirect")
        mime = response.getheader("Content-Type", "").split(";", 1)[0].strip().lower()
        if mime not in ("text/html", "text/plain"):
            raise UnsafeSource("Unsupported source MIME")
        declared = response.getheader("Content-Length")
        if declared:
            try:
                if int(declared) > byte_limit:
                    raise UnsafeSource("Source exceeds byte limit")
            except ValueError as exc:
                raise UnsafeSource("Invalid content length") from exc
        body = response.read(byte_limit + 1)
        if len(body) > byte_limit or len(body) < 100:
            raise UnsafeSource("Source outside byte bounds")
        return body, mime
    finally:
        connection.close()
