"""Server-side CoinGecko USD spot-rate source, staging only.

The response is never trusted without TLS, bounds, age and symbol checks.
This file creates no invoices and initiates no blockchain transfers.
"""
from decimal import Decimal, InvalidOperation
import json
import time
from urllib.request import urlopen

COINGECKO_URL = (
    "https://api.coingecko.com/api/v3/simple/price?"
    "ids=ethereum%2Ctron&vs_currencies=usd&include_last_updated_at=true"
)
MAX_AGE_SECONDS = 90
MAX_BODY_BYTES = 16_384

class RateFeedUnavailable(ValueError):
    pass


def parse_coin_gecko_rates(document, now_epoch):
    from mojplaywin_direct_wallet_invoice import SpotRate

    if type(now_epoch) is not int or now_epoch <= 0:
        raise RateFeedUnavailable("Invalid server clock")
    if not isinstance(document, dict):
        raise RateFeedUnavailable("Invalid market rate payload")
    result = {}
    for symbol, coin_id in (("ETH", "ethereum"), ("TRX", "tron")):
        record = document.get(coin_id)
        if not isinstance(record, dict):
            raise RateFeedUnavailable("Missing exchange rate for " + symbol)
        observed = record.get("last_updated_at")
        if type(observed) is not int or not (now_epoch-MAX_AGE_SECONDS <= observed <= now_epoch):
            raise RateFeedUnavailable("Market rate is stale or future-dated: " + symbol)
        try:
            price = Decimal(str(record["usd"]))
        except (KeyError, InvalidOperation, TypeError, ValueError):
            raise RateFeedUnavailable("Invalid USD rate: " + symbol)
        if not price.is_finite() or price <= 0:
            raise RateFeedUnavailable("Nonpositive USD rate: " + symbol)
        if price < Decimal("0.00000001") or price > Decimal("1000000"):
            raise RateFeedUnavailable("Implausible USD rate: " + symbol)
        result[symbol] = SpotRate(
            asset=symbol, usd_per_asset=str(price), provider="coingecko",
            observed_at_epoch=observed,
        )
    return result


def fetch_fresh_rates(*, fetch=urlopen, now=None):
    if now is None:
        now = int(time.time())
    try:
        response = fetch(COINGECKO_URL, timeout=12)
        with response:
            body = response.read(MAX_BODY_BYTES + 1)
        if len(body) > MAX_BODY_BYTES:
            raise RateFeedUnavailable("Rate payload exceeds size limit")
        doc = json.loads(body.decode("utf-8"))
        return parse_coin_gecko_rates(doc, now)
    except RateFeedUnavailable:
        raise
    except (OSError, TimeoutError, ValueError, UnicodeError, json.JSONDecodeError) as exc:
        raise RateFeedUnavailable("Trusted rate feed unavailable") from exc


if __name__ == "__main__":
    try:
        prices = fetch_fresh_rates()
        for name in ("ETH", "TRX"):
            snap = prices[name]
            print(name, "USD_SPOT_READY", snap.usd_per_asset,
                  "last_update_epoch", snap.observed_at_epoch)
        print("RATE_FEED_READ_ONLY_READY")
    except RateFeedUnavailable as exc:
        print("RATE_FEED_BLOCKED", type(exc).__name__, str(exc))
        raise SystemExit(1)
