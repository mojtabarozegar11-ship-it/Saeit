"""S-01: bounded, privacy-safe classification of SSH failure diagnostics.

Only predefined status codes leave the ephemeral CI runner. Raw SSH logs,
addresses, account names, keys, environment and paths are never returned.
"""
import sys
from pathlib import Path

MAX_BYTES = 32768

def classify(stderr: str) -> str:
    text = stderr.lower()
    if not text.strip():
        return "EMPTY_STDERR"
    # Most specific failures first; never emit matching substrings.
    rules = (
        ("HOST_KEY_REJECTED", ("host key verification failed", "remote host identification has changed", "no matching host key type found")),
        ("AUTH_REJECTED", ("permission denied", "authentication failed", "too many authentication failures", "no more authentication methods to try")),
        ("PROXY_CHANNEL_REJECTED", ("administratively prohibited", "channel 0: open failed", "stdio forwarding failed", "proxyjump failed")),
        ("CONTROL_SOCKET_FAILURE", ("mux_client", "control socket connect", "master is not running", "controlmaster")),
        ("TRANSPORT_UNREACHABLE", ("connection refused", "connection timed out", "operation timed out", "no route to host", "network is unreachable")),
        ("BANNER_OR_KEX_FAILED", ("kex_exchange_identification", "banner exchange", "no matching key exchange method", "unable to negotiate")),
        ("TRANSPORT_RESET_OR_CLOSED", ("connection reset by peer", "connection closed by unknown port", "connection closed by remote host", "broken pipe", "connection to port 22: connection closed")),
        ("DNS_RESOLUTION_FAILED", ("could not resolve hostname", "name or service not known", "temporary failure in name resolution")),
    )
    for category, markers in rules:
        if any(marker in text for marker in markers):
            return category
    # -v SSH debug is retained only in a local runner file; a rejected remote
    # identity check is distinguishable from a failed SSH handshake.
    if "sending command:" in text and ("exit status 1" in text or "exit status 2" in text):
        return "REMOTE_IDENTITY_CHECK_REJECTED"
    if "authenticated to " in text and "exit status 0" in text:
        return "REMOTE_COMMAND_SUCCEEDED"
    # ProxyJump can authenticate the VPS while cPanel never opens a session.
    # Never mistake a successful intermediate hop for the target login.
    if "authenticated to " in text and "sending command:" not in text and "exit status " not in text:
        return "INTERMEDIATE_HOP_AUTHENTICATED_ONLY"
    return "UNKNOWN_SAFE_FAILURE"

def phase(stderr: str) -> str:
    """Return only the last observed SSH stage, never a log fragment."""
    t = stderr.lower()
    if not t.strip():
        return "NO_DIAGNOSTIC_BYTES"
    stages = (
        ("REMOTE_EXIT_OBSERVED", ("exit status ",)),
        ("REMOTE_COMMAND_SENT", ("sending command:",)),
        ("SSH_AUTHENTICATED", ("authenticated to ",)),
        ("SSH_AUTH_ATTEMPTED", ("authentications that can continue:", "offering public key:")),
        ("SSH_TRANSPORT_ESTABLISHED", ("connection established",)),
        ("SSH_CONNECT_ATTEMPTED", ("connecting to ",)),
        ("SSH_PROXY_CONFIGURED", ("setting implicit proxycommand", "executing proxy command")),
    )
    for name, markers in stages:
        if any(marker in t for marker in markers):
            return name
    return "NO_RECOGNIZED_SSH_STAGE"


def main() -> int:
    if len(sys.argv) not in (2, 3) or (len(sys.argv) == 3 and sys.argv[1] != "--phase"):
        return 2
    try:
        with Path(sys.argv[-1]).open("rb") as handle:
            raw = handle.read(MAX_BYTES)
    except OSError:
        print("DIAGNOSTIC_UNAVAILABLE")
        return 0
    text = raw.decode("utf-8", errors="replace")
    print(phase(text) if len(sys.argv) == 3 else classify(text))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
