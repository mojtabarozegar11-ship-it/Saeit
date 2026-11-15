"""Read-only public USD rate adapter for guarded checkout.

No key, wallet, account, payment, or order is touched. Failure is fail-closed;
the caller must not substitute a browser-provided quote.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from datetime import datetime, timezone
import json
import urllib.error
import urllib.request


RATE_URL = (
    "https://api.coingecko.com/api/v3/simple/price"
    "?ids=tron,ethereum&vs_currencies=usd"
)
_MAX_BYTES = 64_000


class RateFeedUnavailable(RuntimeError):
    pass


@dataclass(frozen=True)
class RateSnapshotItem:
    usd_per_asset: Decimal
    provider: str
    observed_at_epoch: int


def fetch_fresh_rates(*, transport=None, now=None):
    """Fetch one bounded read-only snapshot; no fallback to stale data."""
    if transport is None:
        def transport(url):
            request = urllib.request.Request(
                url,
                headers={"Accept": "application/json",
                         "User-Agent": "MojPlayWin-Rate-Readonly/1.0"},
                method="GET",
            )
            try:
                with urllib.request.urlopen(request, timeout=8) as response:
                    if response.status != 200:
                        raise OSError("Rate provider status")
                    raw = response.read(_MAX_BYTES + 1)
            except (OSError, urllib.error.URLError, TimeoutError) as exc:
                raise RateFeedUnavailable("Rate provider unavailable") from exc
            if len(raw) > _MAX_BYTES:
                raise RateFeedUnavailable("Rate response too large")
            return raw
    try:
        raw = transport(RATE_URL)
        data = json.loads(raw.decode("utf-8") if isinstance(raw, bytes) else raw)
        trx = Decimal(str(data["tron"]["usd"]))
        eth = Decimal(str(data["ethereum"]["usd"]))
        if (not trx.is_finite() or trx <= 0 or
                not eth.is_finite() or eth <= 0):
            raise ValueError("Non-positive rate")
    except (RateFeedUnavailable, OSError, KeyError, TypeError, ValueError,
            InvalidOperation, UnicodeDecodeError) as exc:
        if isinstance(exc, RateFeedUnavailable):
            raise
        raise RateFeedUnavailable("Trusted rate snapshot invalid") from exc
    observed = now
    if observed is None:
        observed = datetime.now(timezone.utc)
    if not isinstance(observed, datetime) or observed.tzinfo is None:
        raise RateFeedUnavailable("Trusted rate clock unavailable")
    epoch = int(observed.timestamp())
    return {
        "TRX": RateSnapshotItem(trx, "coingecko", epoch),
        "ETH": RateSnapshotItem(eth, "coingecko", epoch),
    }
