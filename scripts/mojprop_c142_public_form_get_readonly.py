#!/usr/bin/env python3
"""Read-only public HTTPS evidence for exactly two MOJ PROP Plan1 GET routes.

No HTTP POST/HEAD follow-up, cookies, credentials, buyer data, emails,
invoice, RPC calls, broker order, deployment or private host access.
A 200 without the actual nonpayable, CSRF-backed form is NOT availability.
"""
from __future__ import annotations

import json
from html.parser import HTMLParser
import socket
import ssl
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener

ENDPOINTS = (
    ("en", "https://mojplaywin.com/moj-prop-interest/form/"),
    ("fa", "https://mojplaywin.com/moj-prop-interest/form/?lang=fa"),
)
MAX_BYTES = 65000

class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        return None


# Exact set: arbitrary extra fields can be a forged checkout or data collection.
EXPECTED_FIELDS = frozenset({
    "csrfmiddlewaretoken", "plan_code", "consent_version",
    "source_language", "email", "contact_consent",
})


class ConsentFormDocument(HTMLParser):
    """Parse structural HTML; string markers inside comments cannot prove a form."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.html_attrs = []
        self.in_head = False
        self.robots = []
        self.forms = []
        self.active = None
        self.bad_markup = False
        self.unsafe_embeds = False

    def handle_starttag(self, tag, pairs):
        attrs = dict(pairs)
        if tag == "html":
            self.html_attrs.append(attrs)
        elif tag == "head":
            self.in_head = True
        elif tag == "meta" and self.in_head and attrs.get("name", "").lower() == "robots":
            self.robots.append(attrs.get("content", ""))
        elif tag in ("script", "iframe", "object", "embed"):
            self.unsafe_embeds = True
        elif tag == "form":
            if self.active is not None:
                self.bad_markup = True
            form = {"attrs": attrs, "inputs": [], "submit": False, "closed": False}
            self.forms.append(form)
            self.active = form
        elif tag == "input" and self.active is not None:
            self.active["inputs"].append(attrs)
        elif tag == "button" and self.active is not None:
            if attrs.get("type", "submit").lower() == "submit":
                self.active["submit"] = True

    def handle_endtag(self, tag):
        if tag == "head":
            self.in_head = False
        elif tag == "form":
            if self.active is None:
                self.bad_markup = True
            else:
                self.active["closed"] = True
                self.active = None


def _has_exact_consent_fields(fields: list[dict], language: str) -> bool:
    if len(fields) != len(EXPECTED_FIELDS):
        return False
    by_name = {item.get("name"): item for item in fields}
    if set(by_name) != EXPECTED_FIELDS:
        return False
    # The CSRF and plan provenance fields must be genuine form inputs,
    # not comments or unrelated text elsewhere in the document.
    for name, value in (
        ("plan_code", "MOJ-PROP-01"),
        ("consent_version", "moj-prop-interest-v1"),
        ("source_language", language),
    ):
        item = by_name[name]
        if item.get("type") != "hidden" or item.get("value") != value:
            return False
    token = by_name["csrfmiddlewaretoken"]
    if token.get("type") != "hidden" or not token.get("value", "").strip():
        return False
    email = by_name["email"]
    if (email.get("type") != "email" or "required" not in email
            or email.get("maxlength") != "254"):
        return False
    consent = by_name["contact_consent"]
    return (consent.get("type") == "checkbox"
            and consent.get("value") == "yes"
            and "required" in consent)


def evaluate_page(*, status: int, body: bytes, language: str) -> str:
    """No live customer proof: verify only a valid, nonpayable GET form structure."""
    if status != 200:
        return "http_" + str(status) if status in (403, 404, 429, 500, 502, 503, 504) else "unexpected_http_status"
    if type(body) is not bytes or len(body) < 350 or len(body) > MAX_BYTES:
        return "invalid_body"
    try:
        page = body.decode("utf-8")
    except UnicodeDecodeError:
        return "invalid_utf8"
    # Block executable payment/credential capture even when outside the form.
    if any(x in page.lower() for x in (
        "tronweb.trx.sendtransaction", "walletconnect", 'name="private_key"'
    )):
        return "forbidden_payment_or_key_field"
    doc = ConsentFormDocument()
    try:
        doc.feed(page)
        doc.close()
    except (ValueError, AssertionError):
        return "200_not_a_real_consent_form"
    if len(doc.html_attrs) != 1 or doc.html_attrs[0].get("lang") != language:
        return "wrong_locale"
    if language == "fa" and doc.html_attrs[0].get("dir") != "rtl":
        return "farsi_not_rtl"
    if not any({"noindex", "nofollow"} <=
               {flag.strip().lower() for flag in policy.split(",")}
               for policy in doc.robots):
        return "200_not_a_real_consent_form"
    if (doc.bad_markup or doc.unsafe_embeds or doc.active is not None
            or len(doc.forms) != 1):
        return "200_not_a_real_consent_form"
    form = doc.forms[0]
    attrs = form["attrs"]
    if (attrs.get("method", "").lower() != "post"
            or attrs.get("action") != "/moj-prop-interest/"
            or not form["closed"] or not form["submit"]
            or not _has_exact_consent_fields(form["inputs"], language)):
        return "200_not_a_real_consent_form"
    return "verified_get_form_no_payment_claim"


def safe_network_state(exc: BaseException) -> str:
    """Classify exceptions WITHOUT returning error strings, addresses or headers."""
    cause = exc.reason if isinstance(exc, URLError) else exc
    if isinstance(cause, (TimeoutError, socket.timeout)):
        return "network_timeout"
    if isinstance(cause, socket.gaierror):
        return "dns_unavailable"
    if isinstance(cause, ssl.SSLError):
        return "tls_failed"
    if isinstance(cause, ConnectionRefusedError):
        return "connection_refused"
    if isinstance(cause, ConnectionResetError):
        return "connection_reset"
    return "network_unavailable"


def probe_one(opener, language: str, url: str) -> dict:
    request = Request(
        url, method="GET",
        headers={
            "User-Agent": "MOJPROP-owner-readonly-Plan1-GET-c142/1.0",
            "Cache-Control": "no-cache, no-store",
            "Pragma": "no-cache",
            "Accept": "text/html",
        },
    )
    try:
        with opener.open(request, timeout=9) as response:
            status = response.status
            body = response.read(MAX_BYTES + 1)
    except HTTPError as exc:
        status = exc.code
        body = b""
        exc.close()
    except (URLError, TimeoutError, OSError) as exc:
        return {"lang": language, "state": safe_network_state(exc), "http_status": None,
                "get_form_verified": False}
    state = evaluate_page(status=status, body=body, language=language)
    return {"lang": language, "state": state, "http_status": status,
            "get_form_verified": state == "verified_get_form_no_payment_claim"}


def main():
    opener = build_opener(NoRedirect)
    results = [probe_one(opener, lang, url) for lang, url in ENDPOINTS]
    verified = all(item["get_form_verified"] for item in results)
    record = {
        "schema": "mojprop.public.plan1.c142.get-only.v1",
        "method": "GET",
        "en_and_fa_get_consent_verified": verified,
        "routes": results,
        "post_submitted": False,
        "customer_lead_created": False,
        "merchant_authorization_proven": False,
        "tron_payment_collected": False,
        "broker_account_funded": False,
        "production_release_authorized": False,
    }
    print("MOJPROP_C142_PUBLIC_GET_READONLY=" + json.dumps(record, sort_keys=True))
    return 0 if verified else 2


if __name__ == "__main__":
    raise SystemExit(main())
