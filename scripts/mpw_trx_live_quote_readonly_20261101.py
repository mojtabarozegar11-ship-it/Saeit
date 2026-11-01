#!/usr/bin/env python3
"""Read-only live cPanel TRX quote reachability and freshness check.

Uses no buyer/order/database/wallet state. Never prints rate, address, secrets,
HTTP body, or exception detail. Fails closed if source freshness is unavailable.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
import json
import time
from urllib.request import Request, urlopen

URL = (
    "https://api.coingecko.com/api/v3/simple/price"
    "?ids=tron&vs_currencies=usd&include_last_updated_at=true"
)
MAX_BODY = 2048
MAX_AGE = 90


def _unique_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON field")
        result[key] = value
    return result


def quote_ready(*, fetch=urlopen, now=None):
    if now is None:
        now = int(time.time())
    if type(now) is not int or now <= 0:
        return False
    try:
        req = Request(
            URL,
            headers={"Accept": "application/json",
                     "User-Agent": "MojPlayWinQuoteReadOnly/1"},
            method="GET",
        )
        with fetch(req, timeout=9) as response:
            if response.status != 200 or response.geturl() != URL:
                return False
            body = response.read(MAX_BODY + 1)
        if not body or len(body) > MAX_BODY:
            return False
        doc = json.loads(body.decode("utf8"), object_pairs_hook=_unique_keys)
        if type(doc) is not dict or type(doc.get("tron")) is not dict:
            return False
        observation = doc["tron"]
        raw = observation.get("usd")
        if type(raw) not in (int, float, str):
            return False
        price = Decimal(str(raw))
        timestamp = observation.get("last_updated_at")
        if not price.is_finite() or not Decimal("0.001") <= price <= Decimal("100"):
            return False
        if type(timestamp) is not int or timestamp <= 0:
            return False
        return 0 <= now - timestamp <= MAX_AGE
    except (OSError, TimeoutError, ValueError, TypeError, UnicodeError,
            InvalidOperation, json.JSONDecodeError):
        return False


def main():
    result = {
        "tron_quote_endpoint_reachable_and_fresh": quote_ready(),
        "customer_data_read": False,
        "database_accessed": False,
        "orders_created": False,
        "payments_created": False,
        "quote_value_exported": False,
        "release_permitted": False,
    }
    print("MPW_TRX_LIVE_QUOTE_PREFLIGHT=" + json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
