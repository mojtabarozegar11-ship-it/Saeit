#!/usr/bin/env python3
"""Bounded unauthenticated TCP connectivity diagnosis from GitHub Actions.

No SSH secrets, no SSH protocol handshake, no remote commands, HTTP requests,
wallet operations, email, production file access or source writes.
A TCP connection only tests network reachability from this one runner.
It does not establish host identity, SSH authentication or cPanel access.
"""
from __future__ import annotations
import json
import socket
import sys
import time

TARGETS = (
    ("vps_ssh_22", "178.239.147.150", 22),
    ("cpanel_direct_ssh_1396", "zohal.pws-dns.net", 1396),
    ("store_https", "mojplaywin.com", 443),
    ("company_https", "zomorodmelal.ir", 443),
    ("sole_bot_https", "mojtaba.bot.ai", 443),
)
TIMEOUT_SECONDS = 3.0

def probe(name, host, port):
    t0 = time.monotonic()
    try:
        with socket.create_connection((host,port),timeout=TIMEOUT_SECONDS):
            status = "tcp_connected"
    except socket.gaierror:
        status = "dns_failed"
    except (socket.timeout, TimeoutError):
        status = "tcp_timeout"
    except ConnectionRefusedError:
        status = "tcp_refused"
    except (OSError, ValueError):
        status = "tcp_network_or_socket_error"
    elapsed_ms = max(0,round((time.monotonic()-t0)*1000))
    return {"target":name,"status":status,"probe_ms":elapsed_ms,
            "ssh_authenticated":False,"production_files_read":False,
            "account_verified":False,"payment_confirmed":False}

def run(targets=TARGETS):
    if type(targets) is not tuple or len(targets)>5:
        raise ValueError("Probe allowlist exceeded")
    return {"method":"unauthenticated_tcp_connect_only",
            "environment":"github_actions_ephemeral_runner",
            "tests":[probe(name,host,port) for name,host,port in targets],
            "interpretation":"Reachability from runner, NOT validated host identity, paid fulfillment or cPanel access.",
            "files_modified":False,"money_spent":False,"messages_sent":False}

if __name__=="__main__":
    print("MPW_READONLY_RUNNER_TCP_REACHABILITY="+json.dumps(run(),sort_keys=True))
    sys.exit(0)
