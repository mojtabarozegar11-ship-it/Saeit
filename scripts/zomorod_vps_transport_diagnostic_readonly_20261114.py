#!/usr/bin/env python3
"""Credential-free, bounded transport-only VPS SSH preflight. Never verifies identity."""
from __future__ import annotations
import json
import socket
import subprocess

HOST = "178.239.147.150"
PORT = 22
KEY_TYPES = frozenset(("rsa", "ed25519"))

def tcp_probe() -> bool:
    try:
        with socket.create_connection((HOST, PORT), timeout=4):
            return True
    except (OSError, TimeoutError):
        return False

def observed_key_types() -> set[str]:
    try:
        p = subprocess.run(
            ["ssh-keyscan", "-T", "6", "-p", str(PORT), "-t", "rsa,ed25519", HOST],
            capture_output=True, text=True, timeout=8, check=False
        )
    except (OSError, subprocess.TimeoutExpired):
        return set()
    result = set()
    for line in p.stdout.splitlines():
        parts = line.split()
        if len(parts) >= 3 and parts[1] == "ssh-rsa":
            result.add("rsa")
        elif len(parts) >= 3 and parts[1] == "ssh-ed25519":
            result.add("ed25519")
    return result & KEY_TYPES

def diagnose(probe=tcp_probe, scan=observed_key_types) -> dict:
    tcp = bool(probe())
    keys = (scan() & KEY_TYPES) if tcp else set()
    if not tcp:
        status = "tcp22_unreachable_or_filtered"
    elif "rsa" in keys:
        status = "tcp22_open_rsa_observed_unverified"
    elif "ed25519" in keys:
        status = "tcp22_open_only_ed25519_observed"
    else:
        status = "tcp22_open_no_host_key_observed"
    return {
        "scope": "fixed_vps_ssh_transport_readonly",
        "status": status,
        "tcp22_open": tcp,
        "rsa_observed": "rsa" in keys,
        "ed25519_observed": "ed25519" in keys,
        "host_fingerprint_verified": False,
        "cpanel_connectivity_verified": False,
        "active_php_verified": False,
        "site_writes": 0,
        "authentication_attempts": 0,
        "secrets_used": False,
    }

if __name__ == "__main__":
    print(json.dumps(diagnose(), sort_keys=True))
