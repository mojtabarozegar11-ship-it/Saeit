#!/usr/bin/env python3
"""Read-only public HTTPS evidence for exactly two MOJ PROP Plan1 GET routes.

No HTTP POST/HEAD follow-up, cookies, credentials, buyer data, emails,
invoice, RPC calls, broker order, deployment or private host access.
A 200 without the actual nonpayable, CSRF-backed form is NOT availability.
"""
from __future__ import annotations

import json
import re
import socket
import ssl
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener

ENDPOINTS = (
    ("en", "https://mojplaywin.com/moj-prop-interest/form/"),
    ("fa", "https://mojplaywin.com/moj-prop-interest/form/?lang=fa"),
)
MAX_BYTES = 65000
REQUIRED = (
    'action="/moj-prop-interest/"',
    'method="post"',
    'name="contact_consent"',
    'name="email"',
    'name="plan_code" value="MOJ-PROP-01"',
    'name="csrfmiddlewaretoken"',
    'noindex,nofollow',
)


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        return None


def evaluate_page(*, status: int, body: bytes, language: str) -> str:
    """Classify only source shape; never return or print raw page or CSRF token."""
    if status != 200:
        return "http_" + str(status) if status in (403, 404, 429, 500, 502, 503, 504) else "unexpected_http_status"
    if type(body) is not bytes or len(body) < 350 or len(body) > MAX_BYTES:
        return "invalid_body"
    try:
        page = body.decode("utf-8")
    except UnicodeDecodeError:
        return "invalid_utf8"
    if any(marker not in page for marker in REQUIRED):
        return "200_not_a_real_consent_form"
    if re.search(r'<html\b[^>]*\blang="' + re.escape(language) + r'"', page) is None:
        return "wrong_locale"
    if language == "fa" and re.search(r'<html\b[^>]*\bdir="rtl"', page) is None:
        return "farsi_not_rtl"
    if any(x in page.lower() for x in ('tronweb.trx.sendtransaction', 'walletconnect', 'name="private_key"')):
        return "forbidden_payment_or_key_field"
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
