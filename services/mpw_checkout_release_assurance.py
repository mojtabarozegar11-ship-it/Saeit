"""Pure source-level browser GET release assurance for one Mojtaba.bot.ai store.

Enforces the *same mandatory buyer email* on the public source cutover path
as the reviewed Django guest checkout. Never sends HTTP, creates invoices,
sends email, reads credentials or declares an actual payment. Source-only
positive is expressly NOT permission for production release.
"""
from __future__ import annotations

from types import SimpleNamespace

from services.mpw_checkout_render_contract import checkout_markup_category

CHECKOUT_BODY_OK = "buyer_email_checkout_get_formed_and_headers_ok_not_paid"
FORM_NOT_PROVEN = "buyer_email_checkout_form_unverified"
BODY_NOT_PROVEN = "checkout_get_unusable_body"
CONTENT_TYPE_NOT_PROVEN = "checkout_content_type_unverified"
CSP_MISSING = "checkout_csp_missing"
CSP_DUPLICATE = "checkout_csp_ambiguous"
CSP_SCRIPT = "checkout_script_policy_unverified"
CSP_FORM = "checkout_form_action_policy_unverified"
CSP_FRAME = "checkout_frame_policy_unverified"
CSP_BASE = "checkout_base_policy_unverified"
CACHE_NOT_PROVEN = "checkout_no_store_unverified"
HEADER_AMBIGUOUS = "checkout_response_headers_ambiguous"
BODY_OVERSIZE = "checkout_response_exceeds_bound"
LENGTH_INVALID = "checkout_response_length_invalid"
LENGTH_MISMATCH = "checkout_response_length_mismatch"
MAX_ROUTE_BODY_BYTES = 250_000


def _read_header(headers, key):
    if headers is None or not hasattr(headers, "get"):
        return None
    try:
        # HTTPMessage.get() exposes one header and hides a conflicting second
        # instance. A duplicate CSP, cache policy or length is never proof.
        if hasattr(headers, "get_all"):
            values = headers.get_all(key)
            if values is not None and (
                    not isinstance(values, list) or len(values) != 1
                    or not isinstance(values[0], str)):
                return None
        value = headers.get(key)
    except (TypeError, ValueError, AttributeError):
        return None
    if (not isinstance(value, str) or not 0 < len(value) <= 4096
            or any(ord(ch) < 32 or ord(ch) == 127 for ch in value)):
        return None
    return value.strip()


def _ambiguous_headers(headers):
    if headers is None or not hasattr(headers, "get_all"):
        return False
    for key in ("Content-Type", "Content-Security-Policy", "Cache-Control",
                "Content-Length", "Transfer-Encoding"):
        try:
            values = headers.get_all(key)
        except (AttributeError, ValueError, TypeError):
            return True
        if values is not None and (
                not isinstance(values, list) or len(values) != 1):
            return True
    return False


def read_bounded_response(reply, max_bytes=MAX_ROUTE_BODY_BYTES):
    """Read at most max+1 bytes. Never attest an HTML prefix as a full page.

    Returns (bytes, None) or (None, safe_category). No raw HTML/header logs.
    Header-declared length, if provided, must agree exactly with bytes read.
    """
    if type(max_bytes) is not int or not 0 < max_bytes <= MAX_ROUTE_BODY_BYTES:
        return None, LENGTH_INVALID
    headers = getattr(reply, "headers", None)
    if _ambiguous_headers(headers):
        return None, HEADER_AMBIGUOUS
    length = _read_header(headers, "Content-Length")
    if headers is not None and hasattr(headers, "get") and headers.get("Content-Length") is not None:
        if length is None or not length.isascii() or not length.isdecimal():
            return None, LENGTH_INVALID
        declared = int(length)
        if declared > max_bytes:
            return None, BODY_OVERSIZE
    else:
        declared = None
    try:
        body = reply.read(max_bytes + 1)
    except (OSError, ValueError, TypeError, OverflowError):
        return None, BODY_NOT_PROVEN
    if type(body) is not bytes:
        return None, BODY_NOT_PROVEN
    if len(body) > max_bytes:
        return None, BODY_OVERSIZE
    if declared is not None and declared != len(body):
        return None, LENGTH_MISMATCH
    return body, None


def _csp(policy):
    if not policy:
        return CSP_MISSING
    parts = [x.split() for x in policy.casefold().split(";") if x.strip()]
    directives = {}
    for part in parts:
        if not part:
            continue
        label, *values = part
        if label in directives:
            return CSP_DUPLICATE
        directives[label] = values
    if directives.get("script-src") != ["'none'"]:
        return CSP_SCRIPT
    if directives.get("form-action") != ["'self'"]:
        return CSP_FORM
    if directives.get("frame-ancestors") != ["'none'"]:
        return CSP_FRAME
    if directives.get("base-uri") not in (["'self'"], ["'none'"]):
        return CSP_BASE
    return None


def checkout_release_get_category(body, headers, product_id):
    """Coarse non-sensitive classification; never return body, email or token."""
    if type(product_id) is not int or product_id <= 0:
        return BODY_NOT_PROVEN
    if type(body) is not bytes:
        return BODY_NOT_PROVEN
    response = SimpleNamespace(content=body, status_code=200, streaming=False)
    if checkout_markup_category(response, product_id) != "rendered_form_structurally_valid_not_paid":
        return FORM_NOT_PROVEN
    if _ambiguous_headers(headers):
        return HEADER_AMBIGUOUS
    content_type = _read_header(headers, "Content-Type")
    if (not content_type or
            content_type.split(";", 1)[0].strip().casefold() != "text/html"):
        return CONTENT_TYPE_NOT_PROVEN
    category = _csp(_read_header(headers, "Content-Security-Policy"))
    if category:
        return category
    control = _read_header(headers, "Cache-Control")
    tokens = {item.strip().casefold() for item in control.split(",")} if control else set()
    if "no-store" not in tokens:
        return CACHE_NOT_PROVEN
    return CHECKOUT_BODY_OK


def checkout_release_get_valid(body, headers, product_id):
    return checkout_release_get_category(body, headers, product_id) == CHECKOUT_BODY_OK
