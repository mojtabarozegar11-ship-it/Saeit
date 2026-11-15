"""Stable single-bot, 17-brand pre-sale catalog independent of draft MOJ PROP.

The three packages are INTEREST labels only; never authorize paid subscriptions.
"""
from .financial_brand_pages import BRANDS

CANONICAL_AGENT = "mojtaba.bot.ai"
SIGNAL_BRANDS = tuple(brand[0] for brand in BRANDS)
SUPPORTED_LOCALES = ("en", "fa", "ar")
SIGNAL_PLAN_CODES = (
    "moj-signals-standard",
    "moj-signals-plus",
    "moj-signals-professional",
)
if len(SIGNAL_BRANDS) != 17 or len(set(SIGNAL_BRANDS)) != 17:
    raise RuntimeError("Signals must have the 17 individually registered public brands")
