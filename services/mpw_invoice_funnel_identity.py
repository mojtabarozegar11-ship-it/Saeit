"""Strictly classify a local, newly-created invoice redirect for funnel telemetry.

Pure/offline: no HTTP, database, payments, invoice creation or side effects.
This is evidence for analytics only, NEVER evidence of settled TRX or revenue.
"""
from __future__ import annotations

import re
from urllib.parse import urlsplit

_INVOICE_PATH = re.compile(r"/commerce/trx-easy/invoice/[1-9][0-9]*/")
_MAX_LOCATION = 256


def created_invoice_product_id(response, args, kwargs):
    """Return original positive product ID only for an exact local 302/303 invoice redirect.

    Django's URL dispatcher may supply product_id as a positional argument or
    in kwargs. Both forms are legitimate. Ambiguous/malformed paths fail shut.
    """
    status = getattr(response, "status_code", None)
    if type(status) is not int or status not in (302, 303):
        return None
    try:
        location = response.get("Location", "")
    except (AttributeError, TypeError, ValueError):
        return None
    if type(location) is not str or not 0 < len(location) <= _MAX_LOCATION:
        return None
    # urlsplit silently strips leading C0 controls/spaces and removes TAB/CR/LF.
    # A telemetry success must reflect the literal Location header, not a
    # normalized or potentially header-injected redirect.
    if any(ord(ch) <= 32 or ord(ch) == 127 for ch in location):
        return None
    try:
        redirect = urlsplit(location)
    except ValueError:
        return None
    if (redirect.scheme or redirect.netloc or redirect.query or redirect.fragment
            or _INVOICE_PATH.fullmatch(redirect.path) is None):
        return None
    if not isinstance(args, tuple) or not isinstance(kwargs, dict):
        return None
    if kwargs:
        if args or set(kwargs) != {"product_id"}:
            return None
        product_id = kwargs["product_id"]
    else:
        if len(args) != 1:
            return None
        product_id = args[0]
    return product_id if type(product_id) is int and product_id > 0 else None
