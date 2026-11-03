#!/usr/bin/env python3
"""Refuse a Zomorod Melal deployment if the proposed app differs from the live baseline.

Read-only verification. This script NEVER writes to production. It requires the
current production file, a source mirror and optionally a proposed deployment.
Exit 0 on equivalent bytes, 2 on semantic drift, 3 for missing/unsafe inputs.
"""
from __future__ import annotations

import argparse
import hashlib
import os
from pathlib import Path


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load(path: Path) -> bytes:
    if path.is_symlink() or not path.is_file():
        raise ValueError("missing source or symlink: " + str(path))
    if path.stat().st_size < 10_000 or path.stat().st_size > 2_000_000:
        raise ValueError("unexpected PHP file size: " + str(path))
    content = path.read_bytes()
    if not content.startswith(b"<?php"):
        raise ValueError("not a complete PHP source: " + str(path))
    return content


def equivalent(reference: bytes, candidate: bytes) -> tuple[bool, str]:
    if candidate == reference:
        return True, "byte-identical"
    # The GitHub snapshot may have exactly one harmless final newline added
    # by the file-content exporter. No other whitespace is ignored.
    if candidate == reference + b"\n" or reference == candidate + b"\n":
        return True, "one-final-newline-only"
    return False, "content-drift"


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--live", required=True, type=Path)
    p.add_argument("--reference", required=True, type=Path)
    p.add_argument("--candidate", type=Path, help="the app.php intended for deployment")
    p.add_argument("--expected-live-sha256", default="")
    args = p.parse_args()
    try:
        live = load(args.live)
        reference = load(args.reference)
        if args.expected_live_sha256 and digest(live) != args.expected_live_sha256:
            print("BLOCK: live production changed from verified baseline")
            return 2
        matched, why = equivalent(live, reference)
        print("LIVE_SHA256", digest(live))
        print("MIRROR_SHA256", digest(reference))
        print("MIRROR_RESULT", why)
        if not matched:
            print("BLOCK: snapshot is stale; update it through reviewed reconciliation")
            return 2
        if args.candidate is not None:
            candidate = load(args.candidate)
            matched, why = equivalent(live, candidate)
            print("CANDIDATE_SHA256", digest(candidate))
            print("CANDIDATE_RESULT", why)
            if not matched:
                print("BLOCK: candidate is not production-equivalent; review all diffs first")
                return 2
        print("PASS: source mirror equals current production")
        return 0
    except (ValueError, OSError) as exc:
        print("BLOCK: validation could not complete:", type(exc).__name__)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
