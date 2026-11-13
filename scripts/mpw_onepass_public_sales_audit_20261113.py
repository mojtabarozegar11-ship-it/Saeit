#!/usr/bin/env python3
"""One-pass public MojPlayWin buyer journey audit, GET only.

Safe for unprivileged observers. Never makes a POST, invoice, order, blockchain
transfer, recovery attempt, user login, or read of customer/merchant secrets.
A successful public page is not evidence of a paid commercial sale.
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from html.parser import HTMLParser

HOST = "mojplaywin.com"
SKUS = (72, 225, 879)
MAX_BODY = 512_000
UA = "MojPlayWin-readonly-sales-evidence/20261113"


class PageParser(HTMLParser):
    """Associate hidden security inputs with their enclosing form only."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.forms = []
        self.links = []
        self._active_form = None

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if tag == "form":
            # HTML does not permit nested forms. A malformed nested form
            # invalidates the outer one rather than borrowing its CSRF field.
            if self._active_form is not None:
                self._active_form["malformed"] = True
            form = {"action": values.get("action") or "",
                    "method": (values.get("method") or "get").lower(),
                    "inputs": [], "malformed": self._active_form is not None}
            self.forms.append(form)
            self._active_form = form
        elif tag == "input" and self._active_form is not None:
            self._active_form["inputs"].append(
                (values.get("name") or "", values.get("value") or "",
                 (values.get("type") or "text").lower()))
        elif tag == "a":
            self.links.append(values.get("href") or "")

    def handle_endtag(self, tag):
        if tag == "form":
            self._active_form = None


def _local_path(value: str) -> str:
    if not isinstance(value, str) or not value.strip():
        return ""
    item = urllib.parse.urlsplit(value)
    if item.scheme or item.netloc or item.fragment:
        return ""
    return item.path


def classify_html(kind: str, sku: int | None, html: str) -> str:
    """Categorize evidence only; never return page content or customer data."""
    if not isinstance(html, str) or len(html) < 150:
        return "unexpected_short_page"
    if "MojPlayWin" not in html and "mojplaywin" not in html.lower():
        return "brand_not_found"
    parser = PageParser()
    parser.feed(html)
    if kind == "store":
        if "MPW_STATIC_STORE_FALLBACK_V1" in html:
            return "static_fallback_not_dynamic"
        required = ("/store/product/72/checkout/",
                    "/store/product/225/checkout/",
                    "/store/product/879/")
        # A URL mentioned only in a comment, CSS, or script is not a
        # clickable customer CTA; require a real anchor for each SKU.
        if not all(any(_local_path(h) == route for h in parser.links)
                   for route in required):
            return "catalog_ctas_unverified"
        return "store_public_get_ok_not_sale"
    if sku not in SKUS:
        return "invalid_sku"
    if kind == "detail":
        # Literal numbers in CSS or templates are not proof that the
        # product is individually actionable. Check the product-specific CTA.
        checkout_paths = {f"/store/product/{sku}/checkout/",
                          f"/commerce/book/{sku}/"}
        return ("detail_public_get_ok_not_sale"
                if any(_local_path(h) in checkout_paths for h in parser.links)
                else "detail_product_identity_unverified")
    if kind == "checkout":
        action = f"/commerce/trx-easy/start/{sku}/"
        forms = [form for form in parser.forms
                 if not form["malformed"] and form["method"] == "post"
                 and _local_path(form["action"]) == action]
        if not forms:
            return "checkout_post_action_unverified"
        valid = any(any(name == "csrfmiddlewaretoken" and bool(value)
                            and type_ == "hidden"
                            for name, value, type_ in form["inputs"])
                    for form in forms)
        if not valid:
            return "checkout_csrf_unverified"
        emails = any(name.lower() in {"email", "buyer_email", "customer_email",
                                      "purchase_email", "purchaser_email"}
                     or type_ == "email"
                     for form in forms for name, _, type_ in form["inputs"])
        return ("legacy_email_requested" if emails
                else "no_email_checkout_get_ok_not_paid")
    return "unknown_route_kind"



def checkout_header_status(headers) -> str:
    """Fail closed if security/cache headers fail the public GET contract.

    The checkout HTML contains a CSRF form and should not be stored by an
    intermediary. Do not emit header values, cookies, or any sensitive data.
    """
    policy = (headers.get("Content-Security-Policy", "") or "").lower()
    rules = [d.strip().split() for d in policy.split(";") if d.strip()]
    expected = {"script-src": ["'none'"], "form-action": ["'self'"],
                "frame-ancestors": ["'none'"]}
    # Reject duplicate/mixed CSP directives; a separate permissive script-src
    # must not make the security gate appear green.
    for directive, permitted_sources in expected.items():
        actual = [rule[1:] for rule in rules if rule and rule[0] == directive]
        if actual != [permitted_sources]:
            return "checkout_security_headers_unverified"
    cache = (headers.get("Cache-Control", "") or "").lower()
    controls = {token.strip().split("=", 1)[0] for token in cache.split(",")}
    if "no-store" not in controls:
        return "checkout_cache_policy_unverified"
    return "checkout_headers_pass"


class RejectRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        return None


def observe(path: str, kind: str, sku: int | None, timeout: int, opener):
    url = "https://" + HOST + path
    req = urllib.request.Request(
        url, headers={"User-Agent": UA, "Cache-Control": "no-cache",
                      "Accept": "text/html"}, method="GET")
    try:
        with opener.open(req, timeout=timeout) as response:
            final = urllib.parse.urlsplit(response.geturl())
            if final.scheme != "https" or final.hostname != HOST:
                return "unexpected_destination"
            code = response.status
            if code != 200:
                return "http_other"
            data = response.read(MAX_BODY + 1)
            if len(data) > MAX_BODY:
                return "body_over_limit"
            content_type = response.headers.get("Content-Type", "").lower()
            if "text/html" not in content_type:
                return "unexpected_content_type"
            # Only classify checkout content after verifying its own response
            # security headers. The observer never prints token or headers.
            if kind == "checkout":
                headers_status = checkout_header_status(response.headers)
                if headers_status != "checkout_headers_pass":
                    return headers_status
            return classify_html(kind, sku, data.decode("utf-8", "replace"))
    except urllib.error.HTTPError as exc:
        if 300 <= exc.code < 400:
            return "redirect_not_followed"
        return ("http_" + str(exc.code)
                if exc.code in (403, 404, 405, 429, 500, 502, 503, 504)
                else "http_other")
    except (urllib.error.URLError, TimeoutError, OSError, ValueError):
        return "network_unavailable_not_outage_proof"


def audit(timeout: int = 6, opener=None) -> dict:
    if type(timeout) is not int or not 1 <= timeout <= 15:
        raise ValueError("timeout must be a bounded integer")
    if opener is None:
        opener = urllib.request.build_opener(RejectRedirect())
    routes = [("store", None, "/store/")]
    for sku in SKUS:
        routes.extend((
            ("detail", sku, f"/store/product/{sku}/"),
            ("checkout", sku, f"/store/product/{sku}/checkout/"),
            ("checkout", sku, f"/commerce/book/{sku}/"),
        ))
    result = {}
    for kind, sku, path in routes:
        result[path] = observe(path, kind, sku, timeout, opener)
    return {
        "schema": "mpw.public_buyer_journey.readonly.v1",
        "observed_routes": result,
        "pages_checked": len(result),
        "required_skus": list(SKUS),
        "guest_email_policy_expected": "email_not_collected",
        "payment_or_invoice_posts_performed": False,
        "payments_sent": False,
        "customer_data_read": False,
        "independent_chain_finality_verified": False,
        "customer_download_verified": False,
        "commercial_sales_verified": None,
        "notes": "GET/HTML checks only; failures may reflect network limits, not merchant outage.",
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--timeout", type=int, default=6)
    args = parser.parse_args(argv)
    result = audit(args.timeout)
    print("MPW_ONEPASS_PUBLIC_READONLY=" + json.dumps(
        result, sort_keys=True, separators=(",", ":")))
    statuses = tuple(result["observed_routes"].values())
    # Any missing observation, bad form, legacy email gate, timeout or
    # static fallback is an INCOMPLETE public preflight. Do not let network
    # isolation (or an HTTP 200 alone) produce a green commercial gate.
    allowed = {"store_public_get_ok_not_sale", "detail_public_get_ok_not_sale",
               "no_email_checkout_get_ok_not_paid"}
    return 0 if statuses and all(status in allowed for status in statuses) else 2


if __name__ == "__main__":
    sys.exit(main())
