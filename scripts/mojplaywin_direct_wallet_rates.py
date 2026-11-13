"""Server-only fresh ETH/TRX USD reference quotes for MojPlayWin invoices.

Never read a browser-supplied rate, never sign, transfer or authorize money.
Reject unavailable, stale, redirected, malformed or unbounded feed responses.
The external market-data feed is an operational prerequisite, not a release
authorization or independent evidence that the merchant owns a wallet.
"""
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
import json
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


URL = ("https://api.coingecko.com/api/v3/simple/price?"
       "ids=ethereum%2Ctron&vs_currencies=usd&include_last_updated_at=true")
MAX_BYTES = 4096
MAX_PRICE_AGE = 75  # Leave headroom under the 90-second invoice kernel threshold.


class RateFeedUnavailable(ValueError):
    """Do not issue a payable invoice if the trusted quote cannot be verified."""


@dataclass(frozen=True)
class FreshRate:
    usd_per_asset: Decimal
    provider: str
    observed_at_epoch: int


def fetch_fresh_rates(*, assets=("ETH", "TRX"), opener=urlopen, now_epoch=None):
    """Return a bounded snapshot for requested assets; avoid cross-asset outages.

    `opener` is injectable for offline verification, never from buyer input.
    """
    if (type(assets) not in (tuple, list) or not assets or len(assets) > 2
            or any(type(asset) is not str or asset not in ("ETH", "TRX")
                   for asset in assets)
            or len(set(assets)) != len(assets)):
        raise RateFeedUnavailable("Unsupported trusted quote asset")
    request = Request(URL, headers={
        "Accept": "application/json", "User-Agent": "MojPlayWinTRX/1",
    }, method="GET")
    try:
        with opener(request, timeout=8) as response:
            if (response.status != 200
                    or response.geturl() != URL
                    or response.headers.get_content_type() != "application/json"):
                raise RateFeedUnavailable("Untrusted quote HTTP response")
            raw = response.read(MAX_BYTES + 1)
        if len(raw) > MAX_BYTES:
            raise RateFeedUnavailable("Market quote response too large")
        data = json.loads(raw)
        now = time.time() if now_epoch is None else now_epoch
        if type(data) is not dict or type(now) not in (float, int):
            raise RateFeedUnavailable("Malformed market quote envelope")
        rates = {}
        for coin, ticker in (("ethereum", "ETH"), ("tron", "TRX")):
            if ticker not in assets:
                continue
            record = data.get(coin)
            if type(record) is not dict:
                raise RateFeedUnavailable("Missing independently supplied market quote")
            updated = record.get("last_updated_at")
            price = record.get("usd")
            if type(updated) is not int or type(price) not in (float, int, str):
                raise RateFeedUnavailable("Malformed quote value or timestamp")
            value = Decimal(str(price))
            if (not value.is_finite() or not Decimal("0") < value <= Decimal("1000000000")
                    or not 0 <= now - updated <= MAX_PRICE_AGE):
                raise RateFeedUnavailable("Stale or implausible market quote")
            rates[ticker] = FreshRate(value, "coingecko", updated)
        return rates
    except RateFeedUnavailable:
        raise
    except (HTTPError, URLError, OSError, TimeoutError, TypeError, ValueError,
            OverflowError, InvalidOperation, UnicodeError) as exc:
        raise RateFeedUnavailable("Fresh market quote unavailable") from exc
