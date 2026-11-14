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
    """Parse form boundaries without handling or printing buyer input values."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.forms = []
        self.links = []
        self.base_tag_present = False
        self._active_form = None

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if tag == "form":
            # Duplicate action/method attributes are ambiguous in browsers.
            keys = [name.lower() for name, _ in attrs if name]
            nested = self._active_form is not None
            if nested:
                self._active_form["malformed"] = True
            form = {
                "action": values.get("action") or "",
                "method": (values.get("method") or "get").lower(),
                "inputs": [],
                "submit_controls": 0,
                "email_control": False,
                "email_inputs": [],
                "malformed": nested or keys.count("action") != 1
                             or keys.count("method") != 1,
            }
            self.forms.append(form)
            self._active_form = form
        elif tag == "a":
            self.links.append(values.get("href") or "")
        elif tag == "base":
            # <base> can silently redirect a root-relative checkout POST to
            # another origin. Even CSP cannot be assumed active until checked.
            self.base_tag_present = True

        form = self._active_form
        if form is None:
            return
        if tag in ("input", "textarea", "select"):
            fields = [key.lower() for key, _ in attrs if key]
            if any(fields.count(key) > 1 for key in
                   ("name", "type", "value", "id", "autocomplete")):
                form["malformed"] = True
            name = (values.get("name") or "").lower()
            input_type = (values.get("type") or "text").lower()
            # Security-relevant form fields must not be disabled or spoofed.
            if tag == "input":
                form["inputs"].append(
                    (name, values.get("value") or "", input_type,
                     "disabled" in values))
            looks_like_email = (
                "email" in name or "email" in (values.get("id") or "").lower()
                or input_type == "email"
                or (values.get("autocomplete") or "").lower() == "email"
            )
            form["email_control"] |= looks_like_email
            if looks_like_email:
                # Presence alone is not proof of a required, usable buyer
                # contact. Record only field structure, never its value.
                form["email_inputs"].append((
                    tag, name, input_type, "required" in values,
                    "disabled" in values or "readonly" in values,
                ))
            if (tag == "input" and input_type == "submit"
                    and "disabled" not in values and "hidden" not in values):
                form["submit_controls"] += 1
        elif tag == "button":
            if sum(key.lower() == "type" for key, _ in attrs if key) > 1:
                form["malformed"] = True
            button_type = (values.get("type") or "submit").lower()
            if button_type == "submit" and "disabled" not in values                     and "hidden" not in values:
                form["submit_controls"] += 1

    def handle_endtag(self, tag):
        if tag == "form":
            self._active_form = None


def _local_path(value: str) -> str:
    if not isinstance(value, str) or not value.strip():
        return ""
    item = urllib.parse.urlsplit(value)
    if (item.scheme or item.netloc or item.fragment or item.query
            or not item.path.startswith("/")):
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
    parser.close()
    # A dangling form may absorb later inputs in the browser; do not certify
    # an incompletely closed checkout form as a protected buyer action.
    if parser._active_form is not None:
        parser._active_form["malformed"] = True
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
        if parser.base_tag_present:
            return "checkout_base_href_unverified"
        action = f"/commerce/trx-easy/start/{sku}/"
        forms = [form for form in parser.forms
                 if not form["malformed"] and form["method"] == "post"
                 and _local_path(form["action"]) == action]
        if not forms:
            return "checkout_post_action_unverified"
        # Two competing POST actions can mislead the buyer even when one
        # contains a valid CSRF token. Fail closed rather than selecting one.
        post_forms = [form for form in parser.forms if form["method"] == "post"]
        if len(forms) != 1 or len(post_forms) != 1:
            return "checkout_form_ambiguous"
        # Django renders 32/64-character ASCII alphanumeric CSRF tokens.
        # A hidden, enabled field from the exact invoice POST is required.
        csrf_fields = [
            (name, value, input_type, disabled)
            for name, value, input_type, disabled in forms[0]["inputs"]
            if name == "csrfmiddlewaretoken"
        ]
        if len(csrf_fields) != 1:
            return "checkout_csrf_unverified"
        _, token, token_type, disabled = csrf_fields[0]
        if (token_type != "hidden" or disabled
                or len(token) not in (32, 64) or not token.isascii()
                or not token.isalnum()):
            return "checkout_csrf_unverified"
        if forms[0]["submit_controls"] < 1:
            return "checkout_submit_control_unverified"
        email_inputs = forms[0]["email_inputs"]
        # Owner policy: a guest order must collect a valid buyer email.
        # GET can only attest a usable required field, not server validation,
        # delivery, ownership, or cross-browser recovery.
        email_names = {"email", "buyer_email", "customer_email",
                       "purchase_email", "purchaser_email"}
        if (len(email_inputs) != 1
                or email_inputs[0][0] != "input"
                or email_inputs[0][1] not in email_names
                or email_inputs[0][2] != "email"
                or not email_inputs[0][3] or email_inputs[0][4]):
            return "buyer_email_input_unverified"
        return "buyer_email_input_get_ok_not_paid"
    return "unknown_route_kind"



def script_csp_category(headers) -> str:
    """Expose fixed policy categories, never public CSP source values."""
    policy = (headers.get("Content-Security-Policy", "") or "").lower()
    if not policy.strip():
        return "csp_missing"
    rules = [d.strip().split() for d in policy.split(";") if d.strip()]
    script = [rule[1:] for rule in rules if rule and rule[0] == "script-src"]
    if not script:
        return "script_src_missing"
    if len(script) != 1:
        return "script_src_duplicate"
    tokens = script[0]
    if tokens == ["'none'"]:
        return "script_none"
    if "'unsafe-inline'" in tokens or "'unsafe-eval'" in tokens:
        return "script_unsafe_inline_or_eval"
    if "*" in tokens or any(item.startswith("http:") for item in tokens):
        return "script_wildcard_or_http"
    if tokens == ["'self'"]:
        return "script_self_only"
    if any(item.startswith("'nonce-") or item.startswith("'sha") for item in tokens):
        return "script_nonce_or_hash"
    return "script_other"


class CheckoutMetaCSPInspector(HTMLParser):
    """Read only CSP meta tag structure; never disclose policy tokens."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.policy_count = 0
        self.ambiguous = False
        self.script_category = "csp_missing"

    def handle_starttag(self, tag, attrs):
        if tag != "meta":
            return
        names = [name.lower() for name, _ in attrs if name]
        values = dict(attrs)
        equiv = (values.get("http-equiv") or "").strip().lower()
        if equiv != "content-security-policy":
            return
        self.policy_count += 1
        if (self.policy_count != 1 or names.count("http-equiv") != 1
                or names.count("content") != 1):
            self.ambiguous = True
            return
        content = values.get("content") or ""
        if len(content) > 8192:
            self.ambiguous = True
            return
        self.script_category = script_csp_category(
            {"Content-Security-Policy": content})


def checkout_csp_origin_category(headers, html: str) -> str:
    """Classify header-vs-meta CSP origin, not actual runtime enforcement.

    Meta CSP cannot provide frame-ancestors, and presence is not an approval
    of a script policy. Return fixed categories only; never headers or HTML.
    """
    if not isinstance(html, str) or len(html) > MAX_BODY:
        return "csp_origin_unreadable"
    parser = CheckoutMetaCSPInspector()
    try:
        parser.feed(html)
        parser.close()
    except (ValueError, TypeError):
        return "csp_origin_unreadable"
    if parser.ambiguous:
        return "csp_meta_ambiguous"
    header_category = script_csp_category(headers)
    header_has_script = header_category not in ("csp_missing", "script_src_missing")
    if not parser.policy_count:
        return ("header_script_only" if header_has_script
                else "script_src_absent_in_header_and_meta")
    meta_category = parser.script_category
    if meta_category in ("csp_missing", "script_src_missing"):
        return ("header_script_meta_lacks_script" if header_has_script
                else "meta_and_header_lack_script")
    if meta_category not in ("script_none", "script_self_only", "script_nonce_or_hash"):
        return "meta_script_src_unsafe_or_ambiguous"
    return ("header_and_meta_script" if header_has_script
            else "meta_only_script_not_header_proof")


def checkout_header_status(headers) -> str:
    """Fail closed if security/cache headers fail the public GET contract.

    The checkout HTML contains a CSRF form and should not be stored by an
    intermediary. Do not emit header values, cookies, or any sensitive data.
    """
    policy = (headers.get("Content-Security-Policy", "") or "").lower()
    if not policy.strip():
        return "checkout_csp_missing"
    rules = [d.strip().split() for d in policy.split(";") if d.strip()]
    expected = {"script-src": ["'none'"], "form-action": ["'self'"],
                "frame-ancestors": ["'none'"]}
    categories = {"script-src": "checkout_csp_scripts_unverified",
                  "form-action": "checkout_csp_form_action_unverified",
                  "frame-ancestors": "checkout_csp_frames_unverified"}
    # Emit only fixed categories, NEVER raw headers or security tokens.
    # Duplicate/mixed CSP rules are unsafe and must fail closed.
    for directive, permitted_sources in expected.items():
        actual = [rule[1:] for rule in rules if rule and rule[0] == directive]
        if actual != [permitted_sources]:
            return categories[directive]
    cache = (headers.get("Cache-Control", "") or "").lower()
    controls = {token.strip().split("=", 1)[0] for token in cache.split(",")}
    if "no-store" not in controls:
        return "checkout_cache_policy_unverified"
    return "checkout_headers_pass"


class RejectRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        return None


def observe(path: str, kind: str, sku: int | None, timeout: int, opener,
            checkout_form_observations=None, checkout_script_policies=None,
            checkout_csp_origins=None):
    url = "https://" + HOST + path
    req = urllib.request.Request(
        url, headers={"User-Agent": UA, "Cache-Control": "no-cache",
                      "Accept": "text/html"}, method="GET")
    try:
        with opener.open(req, timeout=timeout) as response:
            final = urllib.parse.urlsplit(response.geturl())
            if (final.scheme != "https" or final.hostname != HOST
                    or final.port not in (None, 443)):
                return "unexpected_destination"
            code = response.status
            if code != 200:
                return "http_other"
            data = response.read(MAX_BODY + 1)
            if len(data) > MAX_BODY:
                return "body_over_limit"
            content_type = response.headers.get("Content-Type", "").lower()
            if content_type.split(";", 1)[0].strip() != "text/html":
                return "unexpected_content_type"
            html = data.decode("utf-8", "replace")
            page_status = classify_html(kind, sku, html)
            if kind == "checkout":
                # Record form status separately from the header safety gate.
                # This avoids masking a legacy email form when CSP is absent.
                if checkout_form_observations is not None:
                    checkout_form_observations[path] = page_status
                if checkout_script_policies is not None:
                    checkout_script_policies[path] = script_csp_category(response.headers)
                if checkout_csp_origins is not None:
                    checkout_csp_origins[path] = checkout_csp_origin_category(response.headers, html)
                headers_status = checkout_header_status(response.headers)
                if headers_status != "checkout_headers_pass":
                    return headers_status
            return page_status
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
    checkout_form_observations = {}
    checkout_script_policies = {}
    checkout_csp_origins = {}
    for kind, sku, path in routes:
        result[path] = observe(path, kind, sku, timeout, opener,
                               checkout_form_observations, checkout_script_policies,
                               checkout_csp_origins)
    return {
        "schema": "mpw.public_buyer_journey.readonly.v1",
        "observed_routes": result,
        "checkout_form_observations": checkout_form_observations,
        "checkout_script_policy_categories": checkout_script_policies,
        "checkout_csp_origin_categories": checkout_csp_origins,
        "pages_checked": len(result),
        "required_skus": list(SKUS),
        "guest_email_policy_expected": "valid_buyer_email_required",
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
    # A missing/optional/disabled/spoofed email field, timeout or static
    # fallback is an INCOMPLETE preflight. Browser GET does not prove that
    # invoice POST validates or stores the email, nor any settled sale.
    allowed = {"store_public_get_ok_not_sale", "detail_public_get_ok_not_sale",
               "buyer_email_input_get_ok_not_paid"}
    return 0 if statuses and all(status in allowed for status in statuses) else 2


if __name__ == "__main__":
    sys.exit(main())
