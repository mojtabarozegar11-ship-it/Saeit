#!/usr/bin/env python3
"""Validate cPanel read-only UAPI results; status=0 is a failure even if exit=0.

Never echo JSON error text, which may contain sensitive server details.
"""
from __future__ import annotations

import json
import sys

MAX_RESPONSE = 500_000


def check_version_result(raw: bytes) -> dict:
    if not raw or len(raw) > MAX_RESPONSE:
        raise ValueError("bad_response_size")
    try:
        payload = json.loads(raw)
    except (ValueError, UnicodeError):
        raise ValueError("invalid_json") from None
    if not isinstance(payload, dict) or not isinstance(payload.get("result"), dict):
        raise ValueError("invalid_result")
    result = payload["result"]
    if result.get("status") not in (1, True, "1") or result.get("errors") not in (None, []):
        raise ValueError("uapi_rejected")
    return {"uapi": "Version get", "status": "success", "release_authorized": False}


if __name__ == "__main__":
    try:
        outcome = check_version_result(sys.stdin.buffer.read(MAX_RESPONSE + 1))
    except ValueError as e:
        print(json.dumps({"uapi": "Version get", "status": "held",
                          "reason": str(e), "release_authorized": False}))
        raise SystemExit(2) from None
    print(json.dumps(outcome, sort_keys=True))
