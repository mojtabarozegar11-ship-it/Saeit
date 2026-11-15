"""Localized private trader presentation; 20 locales, no balance mutations."""
import json
from functools import lru_cache
from pathlib import Path

from .moj_prop_page import SUPPORTED_CODES


@lru_cache(maxsize=1)
def labels_for(code):
    if code not in SUPPORTED_CODES:
        raise ValueError("Unknown language")
    path = Path(__file__).with_name("portal_locales.json")
    source = json.loads(path.read_text(encoding="utf-8"))
    if source.get("schema") != "moj-prop.portal-i18n.v1":
        raise ValueError("Unexpected portal translation schema")
    labels = source.get("labels", {})
    if set(labels) != set(SUPPORTED_CODES):
        raise ValueError("Incomplete portal locale catalog")
    if any(len(items) != 20 or any(not text.strip() for text in items)
           for items in labels.values()):
        raise ValueError("Every portal locale must have 20 nonempty strings")
    return labels[code]
