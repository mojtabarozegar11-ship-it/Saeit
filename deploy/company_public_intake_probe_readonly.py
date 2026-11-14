#!/usr/bin/env python3
"""Public, non-authenticated, read-only company intake reachability check.

NEVER sends a form, a POST, a secret, a token, a browser cookie, or a customer
record. Reads at most 96 KiB per fixed public company page, printing only
bounded, structural metadata. GET can prove a response from a CI vantage point,
NOT delivery of a buyer request to the PHP database or successful checkout.
"""
from __future__ import annotations

import json
import re
import socket
import ssl
import urllib.error
import urllib.request

URLS = (
    ("canonical_php", "https://zomorodmelal.ir/ask-master/index.php?service=1"),
    ("company_page", "https://zomorodmelal.ir/company/"),
    ("contact_page", "https://zomorodmelal.ir/contact/"),
)
MAX_BYTES = 96 * 1024
TIMEOUT_SECONDS = 8


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
    # Parse only a bounded public response in memory, never print its content.
    sample = body[:MAX_BYTES].decode("utf-8", errors="replace").casefold()
    output["html_form_seen"] = bool(re.search(r"<form(?:\s|>)", sample))
    output["form_post_seen"] = bool(re.search(
        r"<form\b[^>]*\bmethod\s*=\s*['\"]?post(?:\s|['\"/>])",
        sample,
    ))
    output["email_field_seen"] = bool(re.search(r"name\s*=\s*['\"]?email\b", sample))
    output["consent_field_seen"] = bool(re.search(r"name\s*=\s*['\"]?consent\b", sample))
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
