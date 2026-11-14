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


def _read_header(headers, key):
    if headers is None or not hasattr(headers, "get"):
        return None
    value = headers.get(key)
    if not isinstance(value, str) or len(value) > 4096:
        return None
    return value.strip()


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
