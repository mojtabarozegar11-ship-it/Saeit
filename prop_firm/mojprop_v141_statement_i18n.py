"""Compose all 20 private simulated statement languages without falsifying data.

The original EN/FA release wording remains exact. Additional languages reuse
existing fully localized dashboard labels and a validated supplemental glossary.
No browser write, payment, trade or legal approval is provided here.
"""
from functools import lru_cache
import json
from pathlib import Path

from .moj_prop_page import SUPPORTED_CODES
from .portal_i18n import labels_for
from .mojprop_v141_info_i18n import info_catalog

_EXTRAS = frozenset((
    "intro", "challenge", "events", "closed", "deadline", "action",
    "side", "quantity", "price", "timestamp", "empty",
))
_ADDITIONAL = set(SUPPORTED_CODES) - {"en", "fa"}


@lru_cache(maxsize=1)
def _additional_catalog():
    data = json.loads(
        Path(__file__).with_name("mojprop_v141_statement_extra.json").read_text("utf-8")
    )
    if data.get("schema") != "mojprop.v141.private-statement.extra.v1":
        raise ValueError("Unexpected statement localization schema")
    locales = data.get("locales")
    if type(locales) is not dict or set(locales) != _ADDITIONAL:
        raise ValueError("Missing languages from private statement catalog")
    for code in _ADDITIONAL:
        part = locales[code]
        if type(part) is not dict or set(part) != _EXTRAS:
            raise ValueError(f"Incomplete statement glossary for {code}")
        if any(type(x) is not str or not x.strip() for x in part.values()):
            raise ValueError(f"Blank translated statement text for {code}")
    return locales


def statement_labels(code, historical):
    if code not in SUPPORTED_CODES:
        raise ValueError("Unsupported statement language")
    if code in ("en", "fa"):
        return historical[code]
    extra = _additional_catalog()[code]
    base = labels_for(code)
    info = info_catalog()[code]
    return {
        "title": "MOJ PROP | " + base[0],
        "demo": base[1] + " — " + base[18],
        "intro": extra["intro"],
        "challenge": extra["challenge"],
        "stage": base[4],
        "events": extra["events"],
        "closed": extra["closed"],
        "realized": base[7] + " (USD)",
        "deadline": extra["deadline"],
        "activity": base[13],
        "number": "#",
        "action": extra["action"],
        "side": extra["side"],
        "quantity": extra["quantity"],
        "price": extra["price"],
        "timestamp": extra["timestamp"],
        "empty": extra["empty"],
        "warning": info["legal"],
        "copyright": base[18],
    }
