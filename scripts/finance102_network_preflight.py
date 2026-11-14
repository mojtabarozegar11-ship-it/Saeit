#!/usr/bin/env python3
"""Strictly read-only owner-infrastructure TCP reachability snapshot.

Not SSH authentication, not cPanel login, not production source verification.
Only four explicitly allowed host/port pairs; never scans networks or retries.
Does not use credentials or make filesystem/server writes.
"""
import json
import socket
import ssl

TARGETS = (
    ("factory_vps_ssh", "178.239.147.150", 22),
    ("cpanel_private_ssh", "178.239.147.125", 1396),
    ("cpanel_https", "178.239.147.125", 2083),
    ("cpanel_https_standard", "178.239.147.125", 443),
)

def snapshot(dial=socket.create_connection):
    result = {}
    for label, host, port in TARGETS:
        try:
            with dial((host, port), timeout=5):
                result[label] = "TCP_CONNECTED"
        except (OSError, TimeoutError):
            result[label] = "TCP_UNREACHABLE_FROM_RUNNER"
    return {
        "schema": "saeit.finance102.public-network-diagnostic.v1",
        "scope": "read_only_tcp_connectivity_no_authentication",
        "results": result,
        "authentication_proven": False,
        "hosting_file_parity_proven": False,
        "deployment_authorized": False,
        "deployment_performed": False,
    }

def main():
    print("FINANCE102_NETWORK=" + json.dumps(snapshot(), sort_keys=True))
    print("FINANCE102_DIAGNOSTIC_ONLY=YES")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
