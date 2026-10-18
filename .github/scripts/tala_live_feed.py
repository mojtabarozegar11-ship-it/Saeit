#!/usr/bin/env python3
"""Tala-only audited live public market feed; no invented market prices or secrets.

Prices for precious metals and cryptocurrencies are original USD market quotes.
FX reference is a central/provider reference, never the Iranian free-market rate.
"""
import argparse
import datetime as dt
import json
import math
import pathlib
import time
import urllib.request

OZ_GRAMS = 31.1034768
GOLD_ENDPOINT = "https://api.gold-api.com/price/"
FOREX_URL = "https://open.er-api.com/v6/latest/USD"
CRYPTO_URL = ("https://api.coingecko.com/api/v3/simple/price?"
              "ids=bitcoin,ethereum,tether,tron,binancecoin,solana"
              "&vs_currencies=usd&include_last_updated_at=true")
CRYPTO_IDS = {"btc": "bitcoin", "eth": "ethereum", "usdt": "tether",
              "trx": "tron", "bnb": "binancecoin", "sol": "solana"}
FX_SYMBOLS = {"usd": "USD", "eur": "EUR", "gbp": "GBP", "aed": "AED",
              "try": "TRY", "cad": "CAD"}

def request_json(url):
    # Exactly fixed, trusted HTTPS endpoints. No user-controlled URL input.
    req = urllib.request.Request(
        url, headers={"User-Agent": "Zomorod-Tala-PriceBoard/1.0 (public data)",
                      "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=18) as response:
        if response.status != 200:
            raise ValueError("HTTP feed failure")
        body = response.read(65000)
    return json.loads(body)

def positive(value, label, maximum=1000000000000):
    if isinstance(value, bool) or not isinstance(value, (float, int)):
        raise ValueError(label + " not a numeric quote")
    num = float(value)
    if not math.isfinite(num) or not (0 < num <= maximum):
        raise ValueError(label + " unreasonable quote")
    return num

def stamp(value):
    parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("unqualified timestamp")
    return parsed.astimezone(dt.timezone.utc)

def now_utc():
    return dt.datetime.now(dt.timezone.utc)

def utc_iso(value):
    return value.isoformat(timespec="seconds").replace("+00:00", "Z")

def age_guard(value, maximum_seconds, clock):
    if value > clock + dt.timedelta(minutes=3):
        raise ValueError("feed timestamp is in the future")
    if clock - value > dt.timedelta(seconds=maximum_seconds):
        raise ValueError("feed value too old")

def build(get=request_json, clock=None):
    clock = clock or now_utc()
    fx = get(FOREX_URL)
    if fx.get("result") != "success" or fx.get("base_code") != "USD":
        raise ValueError("USD reference currency unavailable")
    fx_time = dt.datetime.fromtimestamp(int(fx["time_last_update_unix"]), dt.timezone.utc)
    age_guard(fx_time, 172800, clock)
    usd_irr = positive(fx["rates"]["IRR"], "IRR/USD", 1e8)
    pairs = {}
    for key, code in FX_SYMBOLS.items():
        r = 1.0 if key == "usd" else positive(fx["rates"][code], code, 1e6)
        pairs[key] = {"usd": round(1.0 / r, 8), "unit": "one_currency_unit",
                      "source": "ExchangeRate-API reference FX",
                      "observed_at": utc_iso(fx_time), "group": "forex"}
    metals = {}
    for code in ("XAU", "XAG", "XPT", "XPD"):
        payload = get(GOLD_ENDPOINT + code)
        if payload.get("symbol") != code or payload.get("currency") != "USD":
            raise ValueError("unexpected metal feed " + code)
        metal_time = stamp(payload["updatedAt"])
        age_guard(metal_time, 3600, clock)
        metals[code] = (positive(payload["price"], code), metal_time)
    gold_usd = metals["XAU"][0] / OZ_GRAMS
    silver_usd = metals["XAG"][0] / OZ_GRAMS
    metal_defs = {
        "gold18": ("XAU", gold_usd * 0.75),
        "gold24": ("XAU", gold_usd),
        "silver999": ("XAG", silver_usd * 0.999),
        "silver925": ("XAG", silver_usd * 0.925),
        "platinum": ("XPT", metals["XPT"][0] / OZ_GRAMS),
        "palladium": ("XPD", metals["XPD"][0] / OZ_GRAMS)
    }
    for key, (code, price) in metal_defs.items():
        pairs[key] = {"usd": round(price, 8), "unit": "gram", "group": "metals",
                      "source": "gold-api.com " + code + " global spot indicative",
                      "observed_at": utc_iso(metals[code][1])}
    cryptos = get(CRYPTO_URL)
    for key, provider_id in CRYPTO_IDS.items():
        item = cryptos.get(provider_id)
        if not isinstance(item, dict):
            raise ValueError("missing CoinGecko id " + provider_id)
        quote_time = dt.datetime.fromtimestamp(int(item["last_updated_at"]),
                                               dt.timezone.utc)
        age_guard(quote_time, 1200, clock)
        pairs[key] = {"usd": round(positive(item["usd"], key, 1e9), 8),
                      "unit": "one_crypto_asset", "group": "crypto",
                      "source": "CoinGecko aggregated USD quote",
                      "observed_at": utc_iso(quote_time)}
    if len(pairs) != 18:
        raise ValueError("incomplete fixed quote set")
    return {
        "schema": 1, "scope": "tala", "currency": "USD",
        "collected_at": utc_iso(clock),
        "fx_reference": {
            "usd_irr": usd_irr, "source": "ExchangeRate-API USD/IRR reference",
            "observed_at": utc_iso(fx_time),
            "is_iran_free_market": False,
            "disclaimer": "Reference FX only; not an executable Iran free-market IRR quote"
        },
        "quotes": pairs,
        "providers": ["gold-api.com", "CoinGecko", "ExchangeRate-API"],
        "auto": True
    }

def selftest():
    clock = dt.datetime(2026, 10, 18, 12, 0, tzinfo=dt.timezone.utc)
    fx_rates = {"IRR": 42000.0, "EUR": 0.90, "GBP": 0.75, "AED": 3.67,
                "TRY": 40.0, "CAD": 1.4}
    metals = {"XAU": 4000.0, "XAG": 50.0, "XPT": 1700.0, "XPD": 1200.0}
    crypto = {pid: {"usd": 100.0, "last_updated_at": int(clock.timestamp())}
              for pid in CRYPTO_IDS.values()}
    def mocked(url):
        if url == FOREX_URL:
            return {"result": "success", "base_code": "USD", "rates": fx_rates,
                    "time_last_update_unix": int(clock.timestamp())}
        if url == CRYPTO_URL:
            return crypto
        code = url.rsplit("/", 1)[-1]
        return {"symbol": code, "currency": "USD", "price": metals[code],
                "updatedAt": utc_iso(clock)}
    report = build(mocked, clock)
    assert len(report["quotes"]) == 18
    assert report["quotes"]["silver999"]["usd"] > report["quotes"]["silver925"]["usd"]
    assert round(report["quotes"]["gold24"]["usd"] * 0.75, 7) == round(report["quotes"]["gold18"]["usd"], 7)
    assert report["fx_reference"]["is_iran_free_market"] is False
    assert report["quotes"]["eur"]["usd"] > 1
    assert report["quotes"]["btc"]["source"].startswith("CoinGecko")
    fx_rates["IRR"] = -2
    try:
        build(mocked, clock)
        raise AssertionError("invalid FX must fail")
    except ValueError:
        pass
    print("TALA_LIVE_SOURCE_SELFTEST=passed")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("build", "selftest"))
    parser.add_argument("--out")
    args = parser.parse_args()
    if args.mode == "selftest":
        selftest()
        return
    if not args.out:
        parser.error("--out required")
    report = build()
    output = pathlib.Path(args.out)
    if output.exists() or output.is_symlink():
        raise ValueError("never overwrite an existing local quote file")
    output.write_text(json.dumps(report, ensure_ascii=False, separators=(",", ":")),
                      encoding="utf-8")
    print("TALA_LIVE_FEED=validated")
    print("TALA_LIVE_SYMBOLS=" + str(len(report["quotes"])))
    print("TALA_USD_IRR_TYPE=reference_not_free_market")

if __name__ == "__main__":
    main()
