#!/usr/bin/env python3
"""Public, non-authenticated, read-only company intake reachability check.

NEVER sends a form, a POST, a secret, a token, a browser cookie, or a customer
record. Reads at most 96 KiB per fixed public company page, printing only
bounded, structural metadata. GET can prove a response from a CI vantage point,
NOT delivery of a buyer request to the PHP database or successful checkout.
"""
from __future__ import annotations

import json
import socket
import ssl
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit
import urllib.error
import urllib.request

URLS = (
    ("canonical_php", "https://zomorodmelal.ir/ask-master/index.php?service=1"),
    ("company_page", "https://zomorodmelal.ir/company/"),
    ("contact_page", "https://zomorodmelal.ir/contact/"),
)
MAX_BYTES = 96 * 1024
TIMEOUT_SECONDS = 8
MAX_FORMS = 12

# These are structural hints, not proof of statutory consent or server-side
# validation. Do not print any field values, form target URL or HTML content.
CONSENT_NAMES = frozenset({
    "consent", "privacy_consent", "agree", "agreement",
    "terms", "accept_terms", "gdpr_consent",
})
CSRF_NAMES = frozenset({
    "csrf_token", "csrfmiddlewaretoken", "_csrf", "_token",
    "form_token", "nonce",
})
CAPTCHA_NAMES = frozenset({
    "g-recaptcha-response", "h-captcha-response", "cf-turnstile-response",
})


def _target_class(action, page_url):
    if not action:
        return "same_origin_default"
    try:
        target = urlsplit(urljoin(page_url, action))
        origin = urlsplit(page_url)
        if target.scheme != "https" or target.username or target.password:
            return "unsafe_or_non_https"
        if target.hostname == origin.hostname and target.port in (None, 443):
            return "same_origin_https"
        return "external_https"
    except (TypeError, ValueError):
        return "invalid_action"


class _FormStructure(HTMLParser):
    """Record capped boolean form properties only; no raw HTML retained."""

    def __init__(self, page_url):
        super().__init__(convert_charrefs=True)
        self.page_url = page_url
        self.forms = []
        self.active = None
        self.overflow = False

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "form":
            if len(self.forms) >= MAX_FORMS:
                self.overflow = True
                self.active = None
                return
            method = str(attrs.get("method") or "get").strip().casefold()
            self.active = {
                "post": method == "post",
                "email": False,
                "consent_named": False,
                "consent_checkbox_required": False,
                "csrf_named_hidden": False,
                "captcha_named": False,
                "submit": False,
                "post_target_class": _target_class(attrs.get("action"), self.page_url),
            }
            self.forms.append(self.active)
            return
        if self.active is None:
            return
        if tag == "input":
            typ = str(attrs.get("type") or "text").strip().casefold()
            name = str(attrs.get("name") or "").strip().casefold()
            if typ == "email" or name == "email":
                self.active["email"] = True
            if name in CONSENT_NAMES:
                self.active["consent_named"] = True
                if typ == "checkbox" and "required" in attrs:
                    self.active["consent_checkbox_required"] = True
            if typ == "hidden" and name in CSRF_NAMES:
                self.active["csrf_named_hidden"] = True
            if name in CAPTCHA_NAMES:
                self.active["captcha_named"] = True
            if typ == "submit":
                self.active["submit"] = True
        if tag == "button" and str(attrs.get("type") or "submit").casefold() == "submit":
            self.active["submit"] = True

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)

    def handle_endtag(self, tag):
        if tag == "form":
            self.active = None


def _public_structure(html, page_url):
    parser = _FormStructure(page_url)
    parser.feed(html)
    forms = parser.forms
    # For classification, use only a single form that is BOTH POST and email,
    # not fields arbitrarily scattered across independent page forms.
    candidates = [f for f in forms if f["post"] and f["email"]]
    selected = candidates[0] if candidates else None
    return {
        "form_count_capped": len(forms),
        "form_limit_reached": parser.overflow,
        "candidate_post_email_form_count_capped": len(candidates),
        "submission_target_class": selected["post_target_class"] if selected else None,
        "consent_named_in_candidate": selected["consent_named"] if selected else None,
        "required_named_consent_checkbox_seen": (
            selected["consent_checkbox_required"] if selected else None
        ),
        "csrf_named_hidden_in_candidate": (
            selected["csrf_named_hidden"] if selected else None
        ),
        "captcha_named_field_in_candidate": selected["captcha_named"] if selected else None,
        "submit_control_in_candidate": selected["submit"] if selected else None,
    }


class NoExternalRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, file_pointer, code, message, headers, url):
        return None


def _classify_error(exc):
    if isinstance(exc, urllib.error.HTTPError):
        return "http_error"
    if isinstance(exc, (TimeoutError, socket.timeout)):
        return "timeout"
    if isinstance(exc, ssl.SSLError):
        return "tls_error"
    if isinstance(exc, (ConnectionError, urllib.error.URLError, OSError)):
        return "network_or_dns"
    return "unknown_error"


def _safe_probe(name, url, opener):
    output = {
        "target": name,
        "observation": "unknown",
        "http_status": None,
        "html_form_seen": None,
        "form_post_seen": None,
        "email_field_seen": None,
        "consent_field_seen": None,
        "body_truncated": None,
        "structural_evidence_complete": None,
        "form_count_capped": None,
        "form_limit_reached": None,
        "candidate_post_email_form_count_capped": None,
        "submission_target_class": None,
        "consent_named_in_candidate": None,
        "required_named_consent_checkbox_seen": None,
        "csrf_named_hidden_in_candidate": None,
        "captcha_named_field_in_candidate": None,
        "submit_control_in_candidate": None,
        "reason_code": None,
        "customer_intake_written": None,
        "php_database_connected": None,
        "purchase_delivered": None,
        "payment_received": None,
    }
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "ZomorodMelal-ReadOnly-Intake-Audit/1.0",
            "Accept": "text/html",
        },
        method="GET",
    )
    try:
        with opener.open(request, timeout=TIMEOUT_SECONDS) as result:
            code = result.status
            typ = result.headers.get_content_type()
            body = result.read(MAX_BYTES + 1)
    except urllib.error.HTTPError as exc:
        output["http_status"] = exc.code
        output["observation"] = "http_response_not_success"
        output["reason_code"] = "http_error_or_redirect"
        return output
    except Exception as exc:
        output["reason_code"] = _classify_error(exc)
        return output

    output["http_status"] = code
    if code != 200 or typ != "text/html":
        output["observation"] = "non_html_or_non_200_response"
        return output
    output["body_truncated"] = len(body) > MAX_BYTES
    sample = body[:MAX_BYTES].decode("utf-8", errors="replace")
    structure = _public_structure(sample, url)
    output.update(structure)
    # Parsing a truncated response cannot prove a form is absent.
    complete = not output["body_truncated"] and not structure["form_limit_reached"]
    output["structural_evidence_complete"] = complete
    output["html_form_seen"] = bool(structure["form_count_capped"])
    output["form_post_seen"] = structure["candidate_post_email_form_count_capped"] > 0
    output["email_field_seen"] = structure["candidate_post_email_form_count_capped"] > 0
    output["consent_field_seen"] = structure["consent_named_in_candidate"]
    if not complete and not output["form_post_seen"]:
        output["form_post_seen"] = None
        output["email_field_seen"] = None
        output["consent_field_seen"] = None
    output["observation"] = "public_html_observed"
    output["reason_code"] = None
    return output


def main():
    opener = urllib.request.build_opener(
        NoExternalRedirect(), urllib.request.HTTPSHandler(context=ssl.create_default_context())
    )
    results = [_safe_probe(name, url, opener) for name, url in URLS]
    result = {
        "mode": "public_readonly_get_no_credentials",
        "site": "zomorodmelal.ir",
        "backend_storage_verified": False,
        "buyer_order_verified": False,
        "external_payment_verified": False,
        "results": results,
    }
    print("ZM_PUBLIC_INTAKE_READONLY=" + json.dumps(result, sort_keys=True))
    return 0  # An inaccessible host must be UNKNOWN, not fake 'passing' health.


if __name__ == "__main__":
    raise SystemExit(main())
