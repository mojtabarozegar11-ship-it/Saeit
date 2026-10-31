"""S-01 fail-closed TRX-only USD quote candidate; NOT installed in checkout.

Validates only the requested asset. Stale ETH must not block fresh TRX;
stale/future TRX must fail. No side effects on import.
"""
from __future__ import annotations
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
import json
import math
import time
from typing import Callable, Mapping
from urllib.request import Request, urlopen


class TrustedRateUnavailable(ValueError):
    """No independently fresh, valid rate for the requested asset."""


COINGECKO_TRX_ONLY_URL = (
    "https://api.coingecko.com/api/v3/simple/price"
    "?ids=tron&vs_currencies=usd&include_last_updated_at=true"
)
MAX_AGE_SECONDS = 300
MAX_FUTURE_SKEW_SECONDS = 45
MAX_RESPONSE_BYTES = 4096


@dataclass(frozen=True)
class TrustedTrxRate:
    usd_per_trx: Decimal
    observed_at: int
    age_seconds: int
    source: str = "coingecko:tron:usd"


def parse_trx_only(document: Mapping[str, object], *, now: int) -> TrustedTrxRate:
    if type(now) is not int or now <= 0 or not isinstance(document, dict):
        raise TrustedRateUnavailable("Invalid quote envelope")
    trx = document.get("tron")
    if not isinstance(trx, dict):
        raise TrustedRateUnavailable("Missing TRX observation")
    raw_price = trx.get("usd")
    if isinstance(raw_price, bool) or type(raw_price) not in (int, float, str, Decimal):
        raise TrustedRateUnavailable("Invalid TRX price type")
    if isinstance(raw_price, float) and not math.isfinite(raw_price):
        raise TrustedRateUnavailable("Nonfinite TRX price")
    try:
        price = Decimal(str(raw_price))
    except (InvalidOperation, ValueError) as exc:
        raise TrustedRateUnavailable("Invalid TRX price") from exc
    if not price.is_finite() or price <= 0 or price > Decimal("1000000"):
        raise TrustedRateUnavailable("Out-of-range TRX price")
    updated = trx.get("last_updated_at")
    if type(updated) is not int or updated <= 0:
        raise TrustedRateUnavailable("Missing TRX update timestamp")
    age = now - updated
    if age > MAX_AGE_SECONDS or age < -MAX_FUTURE_SKEW_SECONDS:
        raise TrustedRateUnavailable("Stale or future-dated TRX observation")
    return TrustedTrxRate(usd_per_trx=price, observed_at=updated, age_seconds=age)


def fetch_trx_only(*, clock: Callable[[], float] = time.time,
                   opener: Callable = urlopen) -> TrustedTrxRate:
    """Server-only candidate. Integrate only after source/backup/release gates."""
    req = Request(COINGECKO_TRX_ONLY_URL, headers={
        "Accept": "application/json", "User-Agent": "MojPlayWin-RateGate/1.0"
    })
    try:
        with opener(req, timeout=8) as response:
            # Reject redirects, alternate ports, query changes and untrusted origins.
            # A TRX-only quote must come from the exact approved endpoint.
            if response.geturl() != COINGECKO_TRX_ONLY_URL:
                raise TrustedRateUnavailable("Untrusted market-data origin")
            if getattr(response, "status", 200) != 200:
                raise TrustedRateUnavailable("Market-data HTTP error")
            raw = response.read(MAX_RESPONSE_BYTES + 1)
            if not raw or len(raw) > MAX_RESPONSE_BYTES:
                raise TrustedRateUnavailable("Invalid market-data response size")
    except TrustedRateUnavailable:
        raise
    except (OSError, TimeoutError, ValueError) as exc:
        raise TrustedRateUnavailable("TRX rate transport unavailable") from exc
    def reject_duplicate_keys(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise TrustedRateUnavailable("Ambiguous market-data JSON")
            result[key] = value
        return result

    try:
        data = json.loads(raw, object_pairs_hook=reject_duplicate_keys)
    except (ValueError, UnicodeDecodeError) as exc:
        raise TrustedRateUnavailable("Invalid market-data JSON") from exc
    try:
        instant = clock()
        if isinstance(instant, bool) or not isinstance(instant, (int, float)) or not math.isfinite(instant):
            raise TrustedRateUnavailable("Invalid quote clock")
        now = int(instant)
    except (OverflowError, ValueError, TypeError) as exc:
        raise TrustedRateUnavailable("Invalid quote clock") from exc
    return parse_trx_only(data, now=now)
