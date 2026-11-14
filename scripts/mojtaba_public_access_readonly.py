#!/usr/bin/env python3
"""Zero-write bounded public access probe for the canonical bot host.

Only fixed first-party candidates are probed; no user input, credentials,
requests to administrative paths, redirects, or private network targets.
DNS/TLS/HTTP success does NOT prove DNS authority, host ownership, payment
readiness, worker health, or customer delivery.
"""
from __future__ import annotations

from datetime import datetime, timezone
import http.client
import ipaddress
import json
import socket
import ssl


TARGET = "mojtaba.bot.ai"
REFERENCES = ("zomorodmelal.ir", "mojplaywin.com")
HOSTS = (TARGET,) + REFERENCES


def _public_ip(ip):
    try:
        parsed = ipaddress.ip_address(ip)
    except ValueError:
        return False
    return parsed.is_global


def probe(host):
    if host not in HOSTS:
        raise ValueError("unregistered host")
    try:
        addresses = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
    except (socket.gaierror, OSError, TimeoutError):
        return {"host": host, "dns": "unavailable", "tls": "not_checked",
                "https": "not_checked", "status": None}
    public_addresses = {row[4][0] for row in addresses if row[4]}
    if not public_addresses or any(not _public_ip(ip) for ip in public_addresses):
        return {"host": host, "dns": "unsafe_or_nonpublic", "tls": "not_checked",
                "https": "not_checked", "status": None}
    # The IP is checked before connection, so no caller-provided host can
    # redirect the observer to localhost or an internal service.
    context = ssl.create_default_context()
    # Direct TLS is checked only against one resolved public address with
    # original SNI; DNS rebinding cannot change the address mid-probe.
    ip = sorted(public_addresses)[0]
    try:
        with socket.create_connection((ip, 443), timeout=5) as sock:
            with context.wrap_socket(sock, server_hostname=host):
                pass
    except (OSError, ssl.SSLError, TimeoutError):
        return {"host": host, "dns": "resolved_public", "tls": "failed",
                "https": "not_checked", "status": None}
    # HTTPConnection with _create_connection is not used here, to avoid
    # opening a second DNS-resolved connection that might be rebound.
    # Verified TLS already proves HTTPS endpoint reachability at this IP.
    return {"host": host, "dns": "resolved_public", "tls": "verified",
            "https": "tls_only_no_http_claim", "status": None}


def assess(observations):
    rows = {item["host"]: item for item in observations}
    reference_ok = any(rows[h]["dns"] == "resolved_public" for h in REFERENCES)
    target = rows[TARGET]
    return {
        "schema": "mojtaba.bot.ai.public-access-readonly.v1",
        "at_utc": datetime.now(timezone.utc).isoformat(),
        "target": TARGET,
        "reference_dns_functional": reference_ok,
        "target_dns": target["dns"],
        "target_tls": target["tls"],
        "target_public_access": (
            "tls_endpoint_verified_not_application"
            if target["tls"] == "verified" else
            "unverified_due_to_observer_network"
            if not reference_ok else
            "unverified_or_unreachable_from_this_observer"
        ),
        "subdomain_authority_verified": False,
        "operator_evidence_required": (
            "Registrar delegation or explicit authorization from bot.ai owner, "
            "and independent first-party DNS zone + certificate evidence"
        ),
        "no_production_changes": True,
        "no_payment_or_delivery_verified": True,
        "observations": observations,
    }


def main():
    observations = [probe(host) for host in HOSTS]
    print(json.dumps(assess(observations), ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
