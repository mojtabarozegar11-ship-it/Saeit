"""Single signal-subscription catalog for 17 financial brand routes.

A shared catalog avoids 17 separate paid robots. This module exposes NO live
signals, subscriptions, investment promises, checkout or trading instructions.
mojtaba.bot.ai remains the only automation brand.
"""
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
import re

_SIGNAL_PRICE = re.compile(r"[0-9]{1,18}(?:\.[0-9]{1,8})?\Z")

from .financial_brand_pages import BRANDS

SUPPORTED_LOCALES = ("en", "fa", "ar")
SIGNAL_BRANDS = tuple(brand[0] for brand in BRANDS)
CANONICAL_AGENT = "mojtaba.bot.ai"


@dataclass(frozen=True)
class SignalOffer:
    brand: str
    locale: str
    title: str
    landing_path: str
    signal_history_verified: bool
    performance_metrics_available: bool
    jurisdiction_approved: bool
    subscriber_delivery_verified: bool
    price_usd: None
    checkout_enabled: bool
    agent_identity: str


def offer(brand, locale):
    if brand not in SIGNAL_BRANDS:
        raise ValueError("Unregistered signal brand")
    if locale not in SUPPORTED_LOCALES:
        raise ValueError("Unsupported signal language")
    titles = {
        "en": "Market Signals — availability and independent verification",
        "fa": "سیگنال‌های بازار — وضعیت عرضه و راستی‌آزمایی مستقل",
        "ar": "إشارات السوق — حالة الخدمة والتحقق المستقل",
    }
    # All 51 brand/locale offerings need uniquely addressable routes.
    # Default host-language route still serves the existing English/Persian
    # pages; the explicit /fa/ and /ar/ paths work on either owned website.
    prefix = "" if locale == "en" else locale + "/"
    return SignalOffer(
        brand=brand,
        locale=locale,
        title=titles[locale],
        landing_path=f"/{prefix}{brand}/market-signals/",
        signal_history_verified=False,
        performance_metrics_available=False,
        jurisdiction_approved=False,
        subscriber_delivery_verified=False,
        price_usd=None,
        checkout_enabled=False,
        agent_identity=CANONICAL_AGENT,
    )


def catalog():
    return tuple(offer(brand, locale) for brand in SIGNAL_BRANDS for locale in SUPPORTED_LOCALES)


def inspect_signal_record(record):
    """Validate an externally supplied signal's audit shape; NOT signal generation.

    A syntactically valid row still is not independently verified or sellable.
    """
    if not isinstance(record, dict) or set(record) != {
        "event_id", "symbol", "side", "created_at",
        "entry", "stop_loss", "take_profit", "verified_source",
    }:
        return False
    if (not isinstance(record["event_id"], str) or not record["event_id"].isascii()
            or not 1 <= len(record["event_id"]) <= 100
            or not all(x.isalnum() or x in "._:-" for x in record["event_id"])):
        return False
    symbol = record["symbol"]
    if not isinstance(symbol, str) or not symbol.isascii() or not 1 <= len(symbol) <= 24:
        return False
    if not all(ch.isalnum() or ch in "._-/" for ch in symbol):
        return False
    if record["side"] not in ("buy", "sell"):
        return False
    if record["verified_source"] is not True:
        return False
    created = record["created_at"]
    if not isinstance(created, datetime) or created.tzinfo is None:
        return False
    if created.utcoffset() != timezone.utc.utcoffset(created):
        return False
    try:
        nums = []
        for field in ("entry", "stop_loss", "take_profit"):
            value = record[field]
            if type(value) is not str or _SIGNAL_PRICE.fullmatch(value) is None:
                return False
            num = Decimal(value)
            if not num.is_finite() or num <= 0:
                return False
            nums.append(num)
        entry, stop, target = nums
    except (ValueError, ArithmeticError):
        return False
    if record["side"] == "buy" and not (stop < entry < target):
        return False
    if record["side"] == "sell" and not (target < entry < stop):
        return False
    return True
