#!/usr/bin/env python3
"""Public GET ONLY: verify existing Moj Prop mainline unpaid inquiry surface.

No POST, no CRM writes, no buyer data, cookies, login, payments or broker calls.
A structurally valid form is NOT proof that POST persistence or email delivery
works. This check intentionally distinguishes mainline /moj-prop-intake/ from
the unrelated future /moj-prop-interest/form/ (currently public HTTP 404).
"""
from __future__ import annotations

from html.parser import HTMLParser
import json
import socket
import ssl
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener

ENDPOINTS = (
    ("prelaunch_moj_prop_01",
     "https://mojplaywin.com/moj-prop-intake/?format=html&service=blueprint&package=moj-prop-01"),
    ("manual_review_status",
     "https://mojplaywin.com/moj-prop-status/?format=html"),
)
MAX_BYTES = 64000


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        return None


class _Html(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.forms = []
        self.active = None
        self.inputs = []
        self.selects = []
        self.textareas = []
        self.has_submit = False
        self.text_parts = []
        self.script_count = 0
        self.invalid = False

    def handle_starttag(self, tag, pairs):
        attrs = dict(pairs)
        if tag == "script" or tag in ("iframe", "object", "embed"):
            self.script_count += 1
        if tag == "form":
            if self.active is not None:
                self.invalid = True
            self.active = attrs
            self.forms.append(attrs)
        if self.active is not None:
            if tag == "input":
                self.inputs.append(attrs)
            elif tag == "select":
                self.selects.append(attrs)
            elif tag == "textarea":
                self.textareas.append(attrs)
            elif tag == "button" and attrs.get("type", "submit") == "submit":
                self.has_submit = True

    def handle_endtag(self, tag):
        if tag == "form":
            if self.active is None:
                self.invalid = True
            self.active = None

    def handle_data(self, text):
        self.text_parts.append(text)


def classify(*, status: int, raw: bytes, route: str) -> dict:
    flags = {
        "route": route,
        "http_status": status,
        "nonpayable_form_get_valid": False,
        "csrf_present": False,
        "receipt_proof_present": False,
        "moj_prop_01_interest_prefill_present": False,
        "submitted": False,
        "payment_created": False,
    }
    if status != 200 or type(raw) is not bytes or not 100 < len(raw) <= MAX_BYTES:
        return flags
    try:
        doc = _Html()
        doc.feed(raw.decode("utf-8"))
        doc.close()
        if doc.invalid or doc.active is not None or doc.script_count or len(doc.forms) != 1:
            return flags
        form = doc.forms[0]
        if form.get("method", "").lower() != "post":
            return flags
        values = {i.get("name"): i for i in doc.inputs}
        if (len(values) != len(doc.inputs) or
                not values.get("csrfmiddlewaretoken", {}).get("value")):
            return flags
        flags["csrf_present"] = True
        text = " ".join(doc.text_parts)
        if route == "prelaunch_moj_prop_01":
            needed = {"name","email","consent","idempotency_key",
                      "website","csrfmiddlewaretoken"}
            if (set(values) != needed or
                    form.get("action") != "/moj-prop-intake/?format=html" or
                    not values["idempotency_key"].get("value") or
                    values["email"].get("type") != "email" or
                    "required" not in values["consent"] or
                    len(doc.textareas) != 1 or len(doc.selects) != 2
                    or not doc.has_submit):
                return flags
            flags["moj_prop_01_interest_prefill_present"] = (
                "Prelaunch interest only: MOJ-PROP-01" in text
                and "30 TRX" in text and "not payable" in text.lower()
            )
            flags["nonpayable_form_get_valid"] = flags[
                "moj_prop_01_interest_prefill_present"]
        elif route == "manual_review_status":
            if (form.get("action") != "/moj-prop-status/?format=html" or
                    set(values) != {"csrfmiddlewaretoken", "receipt_token"} or
                    not doc.has_submit):
                return flags
            flags["receipt_proof_present"] = True
            flags["nonpayable_form_get_valid"] = True
        return flags
    except (ValueError, UnicodeError, AssertionError):
        return flags


def probe_one(opener, key, url):
    request = Request(url, method="GET", headers={
        "User-Agent": "MOJPROP-owner-public-unpaid-readonly/1.0",
        "Accept": "text/html",
        "Cache-Control": "no-store",
    })
    try:
        with opener.open(request, timeout=10) as response:
            return classify(status=response.status, raw=response.read(MAX_BYTES+1),
                            route=key)
    except HTTPError as err:
        code=err.code
        err.close()
        return classify(status=code,raw=b"",route=key)
    except (URLError,TimeoutError,OSError):
        return classify(status=0,raw=b"",route=key)


def main():
    opener=build_opener(_NoRedirect)
    probes=[probe_one(opener,key,url) for key,url in ENDPOINTS]
    ready=all(x["nonpayable_form_get_valid"] for x in probes)
    payload={
        "classification":"MOJPROP_MAINLINE_UNPAID_INQUIRY_PUBLIC_GET_ONLY",
        "mainline_public_form_get_verified": ready,
        "results":probes,
        "post_submitted":False,
        "crm_persistence_proven":False,
        "customer_lead_created":False,
        "email_delivery_proven":False,
        "contract_or_kyc_completed":False,
        "paid_challenge_authorized":False,
        "native_trx_collected":False,
    }
    print("MOJPROP_UNPAID_MAINLINE_GET="+json.dumps(payload,sort_keys=True))
    return 0 if ready else 2


if __name__ == "__main__":
    raise SystemExit(main())
