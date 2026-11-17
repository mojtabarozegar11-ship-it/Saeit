"""One validated 20-language catalogue for MOJ PROP v1.4.1 enquiries.

All language codes are inherited from the existing complete 20-language
Moj Prop public landing. The locale content is informational, not signed
buyer terms, a KYC instruction or an authorization to collect 30 TRX.
"""
from functools import lru_cache
import json
from pathlib import Path

from .moj_prop_page import SUPPORTED_CODES

_FIELDS = frozenset((
    "name", "dir", "title", "warning", "intro", "email",
    "consent", "button", "privacy", "back", "received", "language",
))
_RTL = frozenset(("fa", "ar", "ur"))


@lru_cache(maxsize=1)
def interest_catalog():
    path = Path(__file__).with_name("mojprop_v141_interest_locales.json")
    source = json.loads(path.read_text("utf-8"))
    if source.get("schema") != "mojprop.v141.interest.locale.v1":
        raise ValueError("Unexpected Plan 1 interest locale schema")
    if tuple(source.get("codes", ())) != SUPPORTED_CODES:
        raise ValueError("Plan 1 locale order differs from canonical 20-language site")
    loc = source.get("locales")
    if type(loc) is not dict or set(loc) != set(SUPPORTED_CODES):
        raise ValueError("Plan 1 requires all 20 language entries")
    for code in SUPPORTED_CODES:
        entry = loc[code]
        if type(entry) is not dict or set(entry) != _FIELDS:
            raise ValueError(f"Incomplete language copy: {code}")
        if any(type(v) is not str or not v.strip() for v in entry.values()):
            raise ValueError(f"Empty translated text: {code}")
        if entry["dir"] != ("rtl" if code in _RTL else "ltr"):
            raise ValueError(f"Invalid text direction: {code}")
    return loc


def interest_context(code):
    if code not in SUPPORTED_CODES:
        raise ValueError("Unsupported language")
    catalog = interest_catalog()
    return {
        "language": code,
        "direction": catalog[code]["dir"],
        "copy": catalog[code],
        "language_options": [
            {"code": lang, "name": catalog[lang]["name"],
             "active": lang == code}
            for lang in SUPPORTED_CODES
        ],
    }
