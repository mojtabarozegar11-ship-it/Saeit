#!/usr/bin/env python3
"""Independent, read-only MojTrade market observer.

Uses public Coinbase Exchange or Kraken Spot hourly candles, never credentials
or order APIs. Every result records which independent source produced it.
Fails closed on missing/stale/invalid candles and atomically writes a private
research payload compatible with scripts/mojtrade_sign_feed.py.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import stat
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener


PRODUCTS = ("BTC-USD", "ETH-USD")
GRANULARITY = 3600
MIN_CANDLES = 60
MAX_RESPONSE_BYTES = 160_000
MAX_CANDLE_AGE_SECONDS = 3 * GRANULARITY
METHOD = "sma20-sma50-momentum10-v1-closed-1h"
SOURCE = "coinbase-exchange-public-candles"
BINANCE_SOURCE = "binance-public-klines"
BITSTAMP_SOURCE = "bitstamp-public-ohlc"
KRAKEN_SOURCE = "kraken-spot-public-ohlc"
BITFINEX_SOURCE = "bitfinex-public-candles"


class MarketDataError(ValueError):
    """Reject questionable data instead of publishing speculative observations."""


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        raise MarketDataError("Market data redirect blocked")


def _fetch_json(url: str, source: str) -> object:
    request = Request(url, headers={"Accept": "application/json", "User-Agent": "MojTradeResearch/1.0"})
    try:
        with build_opener(NoRedirect()).open(request, timeout=12) as response:
            if response.status != 200:
                raise MarketDataError(f"{source}_http_status_rejected")
            body = response.read(MAX_RESPONSE_BYTES + 1)
            if len(body) > MAX_RESPONSE_BYTES:
                raise MarketDataError(f"{source}_response_too_large")
            return json.loads(body)
    except HTTPError as exc:
        raise MarketDataError(f"{source}_http_{exc.code}") from exc
    except URLError as exc:
        raise MarketDataError(f"{source}_network_{type(exc.reason).__name__}") from exc
    except (TimeoutError, OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise MarketDataError(f"{source}_error_{type(exc).__name__}") from exc


def _fetch_candles(product: str) -> list:
    if product not in PRODUCTS:
        raise MarketDataError("Unsupported market product")
    url = f"https://api.exchange.coinbase.com/products/{product}/candles?granularity={GRANULARITY}"
    result = _fetch_json(url, "coinbase")
    if not isinstance(result, list):
        raise MarketDataError("coinbase_invalid_response")
    return result


def _fetch_bitstamp_candles(product: str) -> list:
    pairs = {"BTC-USD": "btcusd", "ETH-USD": "ethusd"}
    if product not in pairs:
        raise MarketDataError("Unsupported market product")
    result = _fetch_json(
        f"https://www.bitstamp.net/api/v2/ohlc/{pairs[product]}/?step=3600&limit=120&exclude_current_candle=true",
        "bitstamp",
    )
    if not isinstance(result, dict):
        raise MarketDataError("bitstamp_invalid_response")
    data = result.get("data")
    candles = data.get("ohlc") if isinstance(data, dict) else None
    if not isinstance(candles, list):
        raise MarketDataError("bitstamp_missing_ohlc")
    rows = []
    for candle in candles:
        if not isinstance(candle, dict):
            raise MarketDataError("bitstamp_invalid_candle_shape")
        try:
            stamp = int(candle["timestamp"])
        except (KeyError, TypeError, ValueError, OverflowError) as exc:
            raise MarketDataError("bitstamp_invalid_candle_time") from exc
        rows.append([
            stamp,
            candle.get("low"),
            candle.get("high"),
            candle.get("open"),
            candle.get("close"),
            candle.get("volume"),
        ])
    return rows


def _fetch_binance_candles(product: str) -> list:
    symbols = {"BTC-USD": "BTCUSDT", "ETH-USD": "ETHUSDT"}
    if product not in symbols:
        raise MarketDataError("Unsupported market product")
    result = _fetch_json(
        f"https://data-api.binance.vision/api/v3/klines?symbol={symbols[product]}&interval=1h&limit=120",
        "binance",
    )
    if not isinstance(result, list):
        raise MarketDataError("binance_invalid_response")
    rows = []
    for candle in result:
        if not isinstance(candle, list) or len(candle) < 6:
            raise MarketDataError("binance_invalid_candle_shape")
        try:
            stamp_ms = int(candle[0])
        except (TypeError, ValueError, OverflowError) as exc:
            raise MarketDataError("binance_invalid_candle_time") from exc
        if stamp_ms % 1000:
            raise MarketDataError("binance_invalid_candle_time")
        # Binance: open time/open/high/low/close/volume/...;
        # normalized: seconds/low/high/open/close/volume.
        rows.append([stamp_ms // 1000, candle[3], candle[2], candle[1], candle[4], candle[5]])
    return rows


def _fetch_kraken_candles(product: str) -> list:
    pairs = {"BTC-USD": "XBTUSD", "ETH-USD": "ETHUSD"}
    if product not in pairs:
        raise MarketDataError("Unsupported market product")
    result = _fetch_json(f"https://api.kraken.com/0/public/OHLC?pair={pairs[product]}&interval=60", "kraken")
    if not isinstance(result, dict) or result.get("error") != []:
        raise MarketDataError("kraken_invalid_response_or_exchange_error")
    payload = result.get("result")
    if not isinstance(payload, dict):
        raise MarketDataError("kraken_missing_result")
    datasets = [value for key, value in payload.items() if key != "last"]
    if len(datasets) != 1 or not isinstance(datasets[0], list):
        raise MarketDataError("kraken_unexpected_pair_result")
    rows = []
    for candle in datasets[0][-300:]:
        if not isinstance(candle, list) or len(candle) != 8:
            raise MarketDataError("kraken_invalid_candle_shape")
        # Kraken: time/open/high/low/close/vwap/volume/count;
        # normalized: time/low/high/open/close/volume.
        rows.append([candle[0], candle[3], candle[2], candle[1], candle[4], candle[6]])
    return rows


def _fetch_bitfinex_candles(product: str) -> list:
    pairs = {"BTC-USD": "tBTCUSD", "ETH-USD": "tETHUSD"}
    if product not in pairs:
        raise MarketDataError("Unsupported market product")
    result = _fetch_json(
        f"https://api-pub.bitfinex.com/v2/candles/trade:1h:{pairs[product]}/hist?limit=120&sort=-1",
        "bitfinex",
    )
    if not isinstance(result, list):
        raise MarketDataError("bitfinex_invalid_response")
    rows = []
    for candle in result:
        if not isinstance(candle, list) or len(candle) != 6:
            raise MarketDataError("bitfinex_invalid_candle_shape")
        # Bitfinex: milliseconds/open/close/high/low/volume;
        # normalized: seconds/low/high/open/close/volume.
        try:
            stamp_ms = int(candle[0])
        except (TypeError, ValueError, OverflowError) as exc:
            raise MarketDataError("bitfinex_invalid_candle_time") from exc
        if stamp_ms % 1000:
            raise MarketDataError("bitfinex_invalid_candle_time")
        rows.append([stamp_ms // 1000, candle[4], candle[3], candle[1], candle[2], candle[5]])
    return rows


def _validated_closes(rows: list, now: datetime) -> tuple[list[float], datetime]:
    if not isinstance(rows, list) or not MIN_CANDLES <= len(rows) <= 300:
        raise MarketDataError("Insufficient or oversized candle history")
    now_timestamp = int(now.timestamp())
    closed_before = (now_timestamp // GRANULARITY) * GRANULARITY
    candles = {}
    for row in rows:
        if not isinstance(row, list) or len(row) != 6:
            raise MarketDataError("Invalid candle shape")
        stamp = row[0]
        if type(stamp) is not int or stamp % GRANULARITY:
            raise MarketDataError("Invalid candle time")
        try:
            low, high, opened, closed, volume = (float(v) for v in row[1:])
        except (TypeError, ValueError, OverflowError) as exc:
            raise MarketDataError("Non-numeric candle") from exc
        if (not all(math.isfinite(v) for v in (low, high, opened, closed, volume))
                or low <= 0 or volume < 0 or not low <= opened <= high
                or not low <= closed <= high):
            raise MarketDataError("Invalid candle price or volume")
        if stamp in candles:
            raise MarketDataError("Duplicate candle")
        if stamp < closed_before:
            candles[stamp] = closed
    stamps = sorted(candles)
    if len(stamps) < MIN_CANDLES:
        raise MarketDataError("Insufficient closed candles")
    recent = stamps[-MIN_CANDLES:]
    if any(b - a != GRANULARITY for a, b in zip(recent, recent[1:])):
        raise MarketDataError("Candle history has gaps")
    last_close_at = recent[-1] + GRANULARITY
    if now_timestamp - last_close_at > MAX_CANDLE_AGE_SECONDS:
        raise MarketDataError("Stale market observation")
    return [candles[stamp] for stamp in recent], datetime.fromtimestamp(last_close_at, tz=timezone.utc)


def _signal(product: str, rows: list, now: datetime, data_source: str = SOURCE) -> dict:
    closes, observed_at = _validated_closes(rows, now)
    sma20 = sum(closes[-20:]) / 20
    sma50 = sum(closes[-50:]) / 50
    last = closes[-1]
    prev10 = closes[-11]
    if last > sma20 > sma50 and last > prev10:
        stance = "watch_buy"
    elif last < sma20 < sma50 and last < prev10:
        stance = "watch_sell"
    else:
        stance = "neutral"
    signal_id = hashlib.sha256(f"{product}|{observed_at.isoformat()}|{METHOD}|{data_source}".encode()).hexdigest()[:24]
    return {
        "id": signal_id, "market": "crypto", "symbol": product.replace("-", "/"),
        "timeframe": "1h", "stance": stance, "observed_at": observed_at.isoformat(),
        "method": METHOD, "data_source": data_source,
    }


def _observed_signal(product: str, now: datetime) -> dict:
    failures = []
    # These observations are explicitly BTC/USD or ETH/USD. Binance's
    # BTCUSDT/ETHUSDT candles have a USDT, NOT USD, quote and must not
    # silently enter a USD-only report. Its isolated parser remains available
    # for a future explicit USDT-symbol schema; it is not an active fallback.
    for source, fetcher in ((SOURCE, _fetch_candles), (BITSTAMP_SOURCE, _fetch_bitstamp_candles), (KRAKEN_SOURCE, _fetch_kraken_candles), (BITFINEX_SOURCE, _fetch_bitfinex_candles)):
        try:
            return _signal(product, fetcher(product), now, source)
        except MarketDataError as exc:
            failures.append(str(exc))
    raise MarketDataError(f"{product}:no_valid_source:" + ";".join(failures))


def observe(now: datetime | None = None, fetcher=None) -> dict:
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("UTC-aware time required")
    now = now.astimezone(timezone.utc).replace(microsecond=0)
    signals = (
        [_signal(product, fetcher(product), now) for product in PRODUCTS]
        if fetcher is not None else [_observed_signal(product, now) for product in PRODUCTS]
    )
    return {
        "schema_version": 1, "generated_at": now.isoformat(),
        "expires_at": (now + timedelta(minutes=90)).isoformat(),
        "source": "mojtrade-vps", "signals": signals,
    }


def write_private(payload: dict, destination: Path) -> None:
    if not destination.is_absolute() or destination.is_symlink():
        raise ValueError("Destination must be absolute and not a symlink")
    if any(segment in {"public_html", "www", "htdocs", "static", "media"} for segment in destination.parts):
        raise ValueError("Public document-root path is prohibited")
    parent = destination.parent
    if not parent.is_dir() or parent.is_symlink() or stat.S_IMODE(parent.stat().st_mode) & 0o077:
        raise ValueError("Destination directory must exist and be private (0700)")
    data = (json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n").encode()
    if len(data) > 96_000:
        raise ValueError("Research payload too large")
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=parent, prefix=".mojtrade-observe-", delete=False) as handle:
            temporary = Path(handle.name)
            os.chmod(temporary, 0o600)
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, destination)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Observe live market data; never place orders")
    parser.add_argument("--output", required=True, type=Path, help="Absolute private payload file")
    args = parser.parse_args()
    try:
        payload = observe()
        write_private(payload, args.output)
    except (MarketDataError, ValueError, OSError) as exc:
        parser.exit(2, f"MOJTRADE_OBSERVATION_REJECTED: {exc}\n")
    print("MOJTRADE_OBSERVATION_WRITTEN: " + ",".join(s["data_source"] for s in payload["signals"]) + "; zero trades")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
