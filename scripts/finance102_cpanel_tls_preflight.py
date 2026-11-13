#!/usr/bin/env python3
"""Finite, unauthenticated TLS identity preflight for the existing cPanel.

This is *not* authorization to log in or deploy. Strict CA+hostname TLS,
a fixed expected account IP, no tokens, cookies, HTTP calls, server writes,
DNS edits, SSH, credential output or automatic retries.
"""
import json
import socket
import ssl

HOST = "zohal.pws-dns.net"
EXPECTED_IPV4 = "178.239.147.125"
PORT = 2083


def check(resolver=socket.getaddrinfo, dial=socket.create_connection, context=None):
    result = {
        "target": "cpanel_https_2083",
        "dns_exact_expected_ipv4": False,
        "tls_hostname_and_ca_verified": False,
        "authenticated": False,
        "filesystem_inspected": False,
        "deployment_performed": False,
    }
    try:
        answers = resolver(HOST, PORT, socket.AF_INET, socket.SOCK_STREAM)
        addresses = {row[4][0] for row in answers}
        result["dns_exact_expected_ipv4"] = addresses == {EXPECTED_IPV4}
    except (OSError, IndexError, TypeError):
        return result
    if not result["dns_exact_expected_ipv4"]:
        return result
    try:
        tls_context = context if context is not None else ssl.create_default_context()
        # SNI is HOST even though the remote IP is pinned to EXPECTED_IPV4.
        with dial((EXPECTED_IPV4, PORT), timeout=8) as sock:
            with tls_context.wrap_socket(sock, server_hostname=HOST) as tls_sock:
                result["tls_hostname_and_ca_verified"] = tls_sock.version() is not None
    except (OSError, TimeoutError, ssl.SSLError, ValueError):
        pass
    return result


def main():
    result = check()
    print("FINANCE102_CPANEL_TLS=" + json.dumps(result, sort_keys=True))
    return 0 if result["tls_hostname_and_ca_verified"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
