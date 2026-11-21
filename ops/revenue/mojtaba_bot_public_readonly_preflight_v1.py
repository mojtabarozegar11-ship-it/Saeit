#!/usr/bin/env python3
"""One bounded public GET to canonical bot domain; NEVER proves bot runtime or payments."""
from __future__ import annotations

import json
import urllib.error
import urllib.request

HOST = "mojtaba.bot.ai"
URL = "https://" + HOST + "/"
TIMEOUT = 10
MAX_BYTES = 131072


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def check(opener=None) -> dict:
    if opener is None:
        opener = urllib.request.build_opener(NoRedirect())
    req = urllib.request.Request(
        URL,
        headers={"Accept": "text/html", "Accept-Encoding": "identity",
                 "User-Agent": "MojtabaBotPublicGETAudit/1.0"},
        method="GET",
    )
    code = None
    html_content_type = False
    bounded_body = False
    issue = "transport_unverified"
    try:
        with opener.open(req, timeout=TIMEOUT) as response:
            code = response.status
            mime = response.headers.get("Content-Type", "").lower()
            html_content_type = "text/html" in mime
            if code == 200 and html_content_type:
                bounded_body = 0 < len(response.read(MAX_BYTES + 1)) <= MAX_BYTES
            issue = "public_http_200_html" if bounded_body else "not_verified_public_html"
    except urllib.error.HTTPError as exc:
        code = exc.code
        issue = "http_non_200_or_redirect"
    except (urllib.error.URLError, OSError, TimeoutError, ValueError):
        issue = "public_transport_unavailable"
    return {
        "scope": "one_public_get_canonical_bot_domain_only",
        "canonical_bot_id": HOST,
        "http_status": code,
        "html_content_type_observed": html_content_type,
        "bounded_nonempty_html_observed": bounded_body,
        "public_html_observed": bool(code == 200 and bounded_body),
        "bot_backend_runtime_verified": False,
        "bot_sales_runtime_verified": False,
        "subscription_billing_verified": False,
        "customer_messages_sent": 0,
        "forms_submitted": 0,
        "authenticated_requests": 0,
        "site_writes": 0,
        "issue": issue,
    }


if __name__ == "__main__":
    print("MOJTABA_PUBLIC_DOMAIN_GET=" + json.dumps(check(), sort_keys=True))
