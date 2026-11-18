"""Human-readable localized nonpayable MOJ PROP v1.4.1 information.

Not signed legal terms: every locale explicitly discloses pending review.
The historic EN/FA fixed snapshot remains untouched at the root without
a ?lang parameter. The 20 localized query variants are read-only.
"""
from functools import lru_cache
import json
from pathlib import Path

from .moj_prop_page import SUPPORTED_CODES
from .mojprop_v141_interest_i18n import interest_context

_FIELDS = frozenset(("heading", "overview", "risk", "social", "funding", "legal"))


@lru_cache(maxsize=1)
def info_catalog():
    source = json.loads(
        Path(__file__).with_name("mojprop_v141_info_locales.json").read_text("utf-8")
    )
    if source.get("schema") != "mojprop.v141.public-info.locale.v1":
        raise ValueError("Unexpected v1.4.1 info catalogue")
    if tuple(source.get("codes", ())) != SUPPORTED_CODES:
        raise ValueError("Info catalogue must match canonical 20-language site")
    locales = source.get("locales")
    if type(locales) is not dict or set(locales) != set(SUPPORTED_CODES):
        raise ValueError("Info catalogue missing supported locales")
    for code, entry in locales.items():
        if type(entry) is not dict or set(entry) != _FIELDS:
            raise ValueError(f"Incomplete buyer information for {code}")
        if any(type(text) is not str or not text.strip() for text in entry.values()):
            raise ValueError(f"Empty buyer information for {code}")
    return locales


def info_context(code):
    if code not in SUPPORTED_CODES:
        raise ValueError("Unsupported locale")
    return {**interest_context(code), "details": info_catalog()[code]}
