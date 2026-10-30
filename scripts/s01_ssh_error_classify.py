"""S-01 safe SSH failure classification: never emit raw stderr or credentials."""
import re
import sys
from pathlib import Path


def classify(stderr: str) -> str:
    text = stderr.lower()
    rules = (
        ("HOST_KEY_REJECTED", ("host key verification failed", "remote host identification has changed")),
        ("AUTH_REJECTED", ("permission denied", "authentication failed", "too many authentication failures")),
        ("TRANSPORT_UNREACHABLE", ("connection refused", "connection timed out", "operation timed out", "no route to host", "network is unreachable")),
        ("BANNER_OR_KEX_FAILED", ("kex_exchange_identification", "banner exchange", "connection closed by remote host")),
        ("DNS_RESOLUTION_FAILED", ("could not resolve hostname", "name or service not known")),
    )
    for category, markers in rules:
        if any(marker in text for marker in markers):
            return category
    return "UNKNOWN_SAFE_FAILURE"


def main() -> int:
    if len(sys.argv) != 2:
        return 2
    path = Path(sys.argv[1])
    # Bounded local-only read. Never print or upload the underlying stderr.
    try:
        with path.open("rb") as handle:
            raw = handle.read(32768)
    except OSError:
        print("UNKNOWN_SAFE_FAILURE")
        return 0
    print(classify(raw.decode("utf-8", errors="replace")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
