#!/usr/bin/env python3
"""Bounded synthetic cPanel->VPS pipe throughput diagnostic; no real site files.

Can be run as producer/consumer only on pre-authorized pinned SSH endpoints.
Produces exactly 16MiB of deterministic fake data. Does not open disk data,
cryptographic keys, production tables, site files, or write to disk. Only
consumer prints total bytes, elapsed seconds, checksum comparison and rate.
"""
import hashlib
import json
import sys
import time

CHUNK = (b"MOJPLAYWIN-SYNTHETIC-READONLY-2026" * 32768)[:1024 * 1024]
COUNT = 16
TOTAL = len(CHUNK) * COUNT


def producer():
    out = sys.stdout.buffer
    for _ in range(COUNT):
        out.write(CHUNK)
    out.flush()


def consumer():
    start = time.monotonic()
    sha = hashlib.sha256()
    seen = 0
    while seen < TOTAL:
        block = sys.stdin.buffer.read(min(1024 * 1024, TOTAL - seen))
        if not block:
            break
        seen += len(block)
        sha.update(block)
    overflow = sys.stdin.buffer.read(1)
    expected = hashlib.sha256()
    for _ in range(COUNT):
        expected.update(CHUNK)
    seconds = max(time.monotonic() - start, 0.001)
    passed = seen == TOTAL and not overflow and sha.digest() == expected.digest()
    result = {
        "classification": "SYNTHETIC_SOURCE_TO_VPS_THROUGHPUT",
        "bytes_read": seen, "expected_bytes": TOTAL,
        "checksum_matches": passed,
        "elapsed_seconds": round(seconds, 2),
        "mib_per_second": round(seen / seconds / 1048576, 2),
        "source_customer_data_read": False,
        "backup_written": False,
        "release_permitted": False,
    }
    print(json.dumps(result, sort_keys=True))
    return 0 if passed else 2


if __name__ == "__main__":
    if sys.argv[1:] == ["produce"]:
        producer()
    elif sys.argv[1:] == ["consume"]:
        raise SystemExit(consumer())
    else:
        raise SystemExit(2)
