#!/usr/bin/env python3
"""Privacy-minimal, GET-only public checkout audit, not a commercial sale test.

No POST, login, TRX transaction, purchase, cPanel, DB, cookie persistence,
secrets or deployment. A green diagnostic execution is NOT a green sale gate.
"""
from __future__ import annotations

import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from html.parser import HTMLParser

ORIGIN = "https://mojplaywin.com"
SKUS = (72, 225, 879)
MAX_BODY = 500_000


class CheckoutParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.form_count = 0
        self.email_inputs = 0
        self.required_email_inputs = 0
        self.submit_buttons = 0
        self.text_parts: list[str] = []
        self.inside_button = False
        self.button_texts: list[str] = []
        self._button_fragments: list[str] = []

    def handle_starttag(self, tag, attrs):
        attrs = {str(k).lower(): ("" if v is None else str(v)) for k, v in attrs}
        if tag == "form":
            self.form_count += 1
        if tag in ("input", "textarea", "select"):
            name = attrs.get("name", "").lower()
            t = attrs.get("type", "").lower()
            if "email" in name or t == "email":
                self.email_inputs += 1
                if "required" in attrs:
                    self.required_email_inputs += 1
            if tag == "input" and t == "submit":
                self.submit_buttons += 1
        if tag == "button":
            self.inside_button = True
            self._button_fragments = []
            if attrs.get("type", "submit").lower() == "submit":
                self.submit_buttons += 1

    def handle_endtag(self, tag):
        if tag == "button" and self.inside_button:
            self.inside_button = False
            self.button_texts.append(" ".join(" ".join(self._button_fragments).split())[:100])

    def handle_data(self, value):
        if self.inside_button:
            self._button_fragments.append(value)
        # Only boolean checks consume this text; raw values are never returned.
        self.text_parts.append(value)

    def summary(self):
        normalized = " ".join(" ".join(self.text_parts).split()).lower()
        return {
            "form_count": self.form_count,
            "named_email_inputs": self.email_inputs,
            "required_email_inputs": self.required_email_inputs,
            "email_label_present": "email address for your order" in normalized,
            "trx_invoice_cta_present": any("trx payment invoice" in x.lower() for x in self.button_texts),
            "submit_button_count": self.submit_buttons,
        }


class SameOriginRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        target = urllib.parse.urlsplit(newurl)
        if (target.scheme != "https" or target.hostname != "mojplaywin.com"
                or target.port not in (None, 443) or target.username or target.password
                or target.query or target.fragment or not target.path.startswith("/")):
            raise ValueError("UNSAFE_REDIRECT")
        if target.path != urllib.parse.urlsplit(req.full_url).path:
            raise ValueError("ROUTE_REDIRECTED")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def parse_checkout(raw: str) -> dict:
    parser = CheckoutParser()
    parser.feed(raw)
    return parser.summary()


def fetch(path: str) -> tuple[int, str]:
    approved = {"/store/"} | {f"/store/product/{p}/checkout/" for p in SKUS}
    if path not in approved:
        raise ValueError("OUT_OF_SCOPE")
    opener = urllib.request.build_opener(SameOriginRedirect())
    req = urllib.request.Request(ORIGIN + path, method="GET", headers={
        "User-Agent": "MojPlayWin-GitHub-GET-Only-Form-Audit/20261112",
        "Accept": "text/html",
        "Cache-Control": "no-cache",
    })
    with opener.open(req, timeout=12) as response:
        content = response.read(MAX_BODY + 1)
        if len(content) > MAX_BODY:
            raise ValueError("BODY_TOO_LARGE")
        content_type = response.headers.get("Content-Type", "").lower()
        if "text/html" not in content_type:
            raise ValueError("NOT_HTML")
        return response.status, content.decode("utf-8", "replace")


def live() -> int:
    report: dict = {"mode": "read_only_public_get", "customer_data_collected": False,
                    "post_requests": 0, "payments": 0, "production_writes": 0,
                    "status": "BLOCKED_OR_UNVERIFIED", "products": {}}
    store_status = "UNKNOWN"
    try:
        code, html = fetch("/store/")
        store_status = "STATIC_FALLBACK" if "MPW_STATIC_STORE_FALLBACK_V1" in html else "OTHER"
        report["store_http_200"] = code == 200
    except (OSError, ValueError, urllib.error.HTTPError) as exc:
        report["store_error_type"] = type(exc).__name__
        report["store_http_200"] = False
    report["store_mode"] = store_status
    for sku in SKUS:
        path = f"/store/product/{sku}/checkout/"
        try:
            status, html = fetch(path)
            parsed = parse_checkout(html)
            parsed["http_200"] = status == 200
            parsed["email_free_form_evidence"] = (
                status == 200 and parsed["form_count"] >= 1
                and parsed["named_email_inputs"] == 0
                and not parsed["email_label_present"]
                and parsed["trx_invoice_cta_present"]
            )
            report["products"][str(sku)] = parsed
        except (OSError, ValueError, urllib.error.HTTPError) as exc:
            report["products"][str(sku)] = {
                "email_free_form_evidence": False, "error_type": type(exc).__name__}
    report["all_email_free_forms"] = all(
        record.get("email_free_form_evidence") is True
        for record in report["products"].values()
    ) and len(report["products"]) == len(SKUS)
    # Even email-free pages do not establish payment finality and paid delivery.
    report["sale_proven"] = False
    print("MPW_3SKU_LIVE_FORM_READONLY=" + json.dumps(report, sort_keys=True))
    return 0  # Diagnostic success does NOT mean the store is commercially ready.


if __name__ == "__main__":
    if sys.argv[1:] != ["--live"]:
        raise SystemExit("usage: python -B mpw_three_sku_public_form_evidence_20261112.py --live")
    raise SystemExit(live())
