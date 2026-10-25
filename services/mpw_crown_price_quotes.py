"""Independent USD/TRX quote readers with bounded response sizes and strict HTTPS.

These are *rate observations*, not payment proof. Independent finality requires
separately authenticated SolidityNode RPC operators.
"""
from datetime import datetime, timezone
from decimal import Decimal
import json
import urllib.request

_CG = "https://api.coingecko.com/api/v3/simple/price?ids=tron&vs_currencies=usd&include_last_updated_at=true"
_KRAKEN = "https://api.kraken.com/0/public/Ticker?pair=TRXUSD"


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        raise ValueError("Price feed redirect blocked")


def _read(origin):
    request = urllib.request.Request(origin, headers={
        "Accept": "application/json", "User-Agent": "MojPlayWin-Crown-PriceVerifier/1.0",
    })
    opener = urllib.request.build_opener(_NoRedirect())
    with opener.open(request, timeout=5) as response:
        if response.status != 200:
            raise ValueError("Price feed HTTP status")
        raw = response.read(8193)
    if len(raw) > 8192:
        raise ValueError("Oversized price feed")
    parsed = json.loads(raw)
    if type(parsed) is not dict:
        raise ValueError("Malformed price response")
    return parsed


def coingecko_usd_per_trx():
    data = _read(_CG)["tron"]
    rate = Decimal(str(data["usd"]))
    updated = data["last_updated_at"]
    if type(updated) is not int or updated <= 0:
        raise ValueError("CoinGecko quote lacks trusted update timestamp")
    when = datetime.fromtimestamp(updated, timezone.utc)
    return rate, when


def kraken_usd_per_trx():
    data = _read(_KRAKEN)
    if data.get("error") != []:
        raise ValueError("Kraken rejected ticker request")
    results = data.get("result")
    if not isinstance(results, dict) or len(results) != 1:
        raise ValueError("Ambiguous Kraken market")
    row = next(iter(results.values()))
    if type(row) is not dict or not isinstance(row.get("a"), list) or not isinstance(row.get("b"), list):
        raise ValueError("Kraken bid/ask missing")
    bid, ask = Decimal(str(row["b"][0])), Decimal(str(row["a"][0]))
    if bid <= 0 or ask <= 0 or bid > ask or (ask - bid) / bid > Decimal("0.02"):
        raise ValueError("Invalid or illiquid TRX market")
    return (bid + ask) / Decimal(2), datetime.now(timezone.utc)
