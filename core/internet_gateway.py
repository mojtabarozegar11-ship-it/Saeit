"""Governed internet egress gateway for Master Agent robots.

All robot web egress should pass through this layer. It enforces public-only
network targets, bounded time/size, redirect re-validation, and emits a
structured audit record without storing credentials.
"""
import ipaddress
import socket
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener


class InternetGateway:
    USER_AGENT = "Saeit-MasterAgent-InternetGateway/1.0"
    MAX_TIMEOUT = 20
    MAX_BYTES = 1_000_000

    @classmethod
    def validate_public_url(cls, url):
        parsed = urlparse(str(url).strip())
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise ValueError("only public http/https URLs are allowed")
        if parsed.username or parsed.password:
            raise ValueError("embedded URL credentials are not allowed")
        try:
            addresses = {item[4][0] for item in socket.getaddrinfo(parsed.hostname, parsed.port, type=socket.SOCK_STREAM)}
        except (socket.gaierror, OSError, ValueError) as exc:
            raise ValueError("unable to resolve URL host") from exc
        for address in addresses:
            ip = ipaddress.ip_address(address)
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast or ip.is_unspecified:
                raise PermissionError("private or local network targets are blocked")
        return parsed

    @classmethod
    def fetch(cls, url, *, timeout=10, max_bytes=200000):
        cls.validate_public_url(url)
        timeout = min(max(int(timeout), 1), cls.MAX_TIMEOUT)
        max_bytes = min(max(int(max_bytes), 1024), cls.MAX_BYTES)

        class SafeRedirectHandler(HTTPRedirectHandler):
            def redirect_request(self, req, fp, code, msg, headers, newurl):
                InternetGateway.validate_public_url(newurl)
                return super().redirect_request(req, fp, code, msg, headers, newurl)

        request = Request(str(url).strip(), headers={"User-Agent": cls.USER_AGENT})
        with build_opener(SafeRedirectHandler()).open(request, timeout=timeout) as response:
            data = response.read(max_bytes + 1)
            truncated = len(data) > max_bytes
            data = data[:max_bytes]
            content_type = response.headers.get("Content-Type", "")
            return {
                "status": "fetched",
                "url": str(url).strip(),
                "final_url": response.geturl(),
                "http_status": response.status,
                "content_type": content_type,
                "bytes": len(data),
                "truncated": truncated,
                "body": data.decode(response.headers.get_content_charset() or "utf-8", errors="replace"),
                "gateway": "internet-gateway-v1",
            }

    @classmethod
    def health_check(cls, url="https://zomorodmelal.ir/"):
        result = cls.fetch(url, timeout=5, max_bytes=4096)
        return {
            "status": "healthy" if 200 <= result["http_status"] < 400 else "degraded",
            "gateway": "internet-gateway-v1",
            "http_status": result["http_status"],
            "final_url": result["final_url"],
            "bytes": result["bytes"],
        }
