#!/usr/bin/env python3
"""Public same-venue bid/ask evidence; strictly no private or order endpoints.

Only Coinbase Exchange level-1 product book and Kraken Spot public Ticker have
verified response contracts here. No unsupported provider can supply spread.
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone

import mojtrade_observe_market as observer


SCHEMA = "mojtrade.public-quote-evidence.v1"
SUPPORTED = frozenset((observer.SOURCE, observer.KRAKEN_SOURCE))
MAX_QUOTE_SPREAD_BPS = 500.0
MAX_BOOK_AGE_SECONDS = 60
MAX_REQUEST_ELAPSED_SECONDS = 16


class QuoteReject(ValueError):
    """Source, clock or inside-market quote is unfit for research."""


def _utc(value):
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise QuoteReject("aware_quote_clock_required")
    return value.astimezone(timezone.utc)


def _number(value):
    if isinstance(value, bool) or not isinstance(value, (float, int, str)):
        raise QuoteReject("quote_number_type_invalid")
    if isinstance(value, str) and not 1 <= len(value) <= 32:
        raise QuoteReject("quote_number_size_invalid")
    try:
        number = float(value)
    except (ValueError, OverflowError) as exc:
        raise QuoteReject("quote_number_invalid") from exc
    if not math.isfinite(number) or number <= 0:
        raise QuoteReject("quote_number_nonpositive_or_nonfinite")
    return number


def _book_time(value):
    if not isinstance(value, str) or len(value) > 40:
        raise QuoteReject("book_timestamp_invalid")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise QuoteReject("book_timestamp_invalid") from exc
    if parsed.tzinfo is None or parsed.utcoffset() != timedelta(0):
        raise QuoteReject("book_timestamp_not_utc")
    return parsed.astimezone(timezone.utc)


def _coinbase_quote(payload, received):
    if (not isinstance(payload, dict) or type(payload.get("sequence")) is not int
            or payload["sequence"] < 0 or not isinstance(payload.get("bids"), list)
            or not isinstance(payload.get("asks"), list)
            or len(payload["bids"]) != 1 or len(payload["asks"]) != 1):
        raise QuoteReject("coinbase_book_shape_invalid")
    # Coinbase can expose indicative best bid/ask prices during auction mode.
    # They are not executable inside-market quotes even when non-crossed.
    # Legacy responses may omit the optional flag, but malformed flags fail closed.
    if "auction_mode" in payload and (type(payload["auction_mode"]) is not bool
                                      or payload["auction_mode"]):
        raise QuoteReject("coinbase_indicative_auction_quote_forbidden")
    bid_row, ask_row = payload["bids"][0], payload["asks"][0]
    if (not isinstance(bid_row, list) or not isinstance(ask_row, list)
            or len(bid_row) != 3 or len(ask_row) != 3
            or type(bid_row[2]) is not int or type(ask_row[2]) is not int
            or min(bid_row[2], ask_row[2]) < 1):
        raise QuoteReject("coinbase_book_level_invalid")
    bid, ask = _number(bid_row[0]), _number(ask_row[0])
    _number(bid_row[1]); _number(ask_row[1])
    book_at = _book_time(payload.get("time"))
    seconds = (received - book_at).total_seconds()
    if not -2 <= seconds <= MAX_BOOK_AGE_SECONDS:
        raise QuoteReject("coinbase_book_stale_or_future")
    return bid, ask, book_at.isoformat(), payload["sequence"]


def _kraken_quote(payload, product):
    if (not isinstance(payload, dict) or payload.get("error") != []
            or not isinstance(payload.get("result"), dict)
            or len(payload["result"]) != 1):
        raise QuoteReject("kraken_ticker_shape_invalid")
    key = next(iter(payload["result"]))
    allowed_keys = {"BTC-USD": {"XXBTZUSD", "XBTUSD", "BTCUSD"},
                    "ETH-USD": {"XETHZUSD", "ETHUSD"}}[product]
    if key not in allowed_keys:
        raise QuoteReject("kraken_ticker_product_mismatch")
    ticker = next(iter(payload["result"].values()))
    if (not isinstance(ticker, dict) or not isinstance(ticker.get("a"), list)
            or not isinstance(ticker.get("b"), list)
            or len(ticker["a"]) < 2 or len(ticker["b"]) < 2):
        raise QuoteReject("kraken_bid_ask_missing")
    ask, bid = _number(ticker["a"][0]), _number(ticker["b"][0])
    _number(ticker["a"][1]); _number(ticker["b"][1])
    return bid, ask, None, None


def fetch_public_quote(product, venue, *, fetch_json=None, clock=None):
    """Measure immediately after HTTPS response; no timestamp backdating."""
    if product not in observer.PRODUCTS or venue not in SUPPORTED:
        raise QuoteReject("unsupported_product_or_venue")
    get_json = observer._fetch_json if fetch_json is None else fetch_json
    read_clock = (lambda: datetime.now(timezone.utc)) if clock is None else clock
    before = _utc(read_clock())
    if venue == observer.SOURCE:
        endpoint = f"https://api.exchange.coinbase.com/products/{product}/book?level=1"
        source_label = "coinbase_book"
    else:
        pair = {"BTC-USD": "XBTUSD", "ETH-USD": "ETHUSD"}[product]
        endpoint = f"https://api.kraken.com/0/public/Ticker?pair={pair}"
        source_label = "kraken_ticker"
    try:
        raw = get_json(endpoint, source_label)
    except observer.MarketDataError as exc:
        raise QuoteReject("public_quote_fetch_failed") from exc
    after = _utc(read_clock())
    elapsed = (after - before).total_seconds()
    if not 0 <= elapsed <= MAX_REQUEST_ELAPSED_SECONDS:
        raise QuoteReject("quote_fetch_clock_or_latency_invalid")
    if venue == observer.SOURCE:
        bid, ask, book_at, sequence = _coinbase_quote(raw, after)
    else:
        bid, ask, book_at, sequence = _kraken_quote(raw, product)
    if ask < bid:
        raise QuoteReject("crossed_bid_ask_rejected")
    spread = (ask - bid) / ((ask + bid) / 2) * 10000
    if spread > MAX_QUOTE_SPREAD_BPS:
        raise QuoteReject("excessive_quote_spread_rejected")
    return {
        "schema": SCHEMA,
        "venue_claim": venue,
        "symbol": product.replace("-", "/"),
        "quote_received_at_utc": after.isoformat(),
        "book_source_timestamp_utc": book_at,
        "book_sequence": sequence,
        "bid": bid, "ask": ask,
        "spread_bps": spread,
        "venue_authenticity_independently_verified": False,
        "execution": "disabled",
        "publication": "disabled",
        "real_orders": 0,
    }
