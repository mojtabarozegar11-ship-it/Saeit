"""MOJ PROP Plan 1 public-only DNS/HTTP funnel diagnostic, no customer traffic.

GET-only to 3 allowlisted PUBLIC HTTPS URLs. No POST, payment, contact,
authentication, private customer logs or third-party hosts. Successful CI
means execution completed, not that the website is reachable or paid.
"""
from __future__ import annotations
import json
import socket
import ssl
from datetime import datetime, timezone
from html.parser import HTMLParser
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

HOSTS = ("mojplaywin.com", "www.mojplaywin.com")
TARGETS = {
    "plan1": "https://mojplaywin.com/moj-prop/",
    "intake": "https://mojplaywin.com/moj-prop-intake/",
    "www_plan1": "https://www.mojplaywin.com/moj-prop/",
}
MAX_BYTES = 120_000
TIMEOUT = 9


class FormCounter(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.forms = 0
        self.post_forms = 0
        self.buttons = 0

    def handle_starttag(self, tag, attrs):
        if tag == "form":
            self.forms += 1
            if dict(attrs).get("method", "get").lower() == "post":
                self.post_forms += 1
        if tag == "button":
            self.buttons += 1


def verify_target(url: str) -> None:
    p = urlparse(url)
    if (p.scheme != "https" or p.hostname not in HOSTS or p.port is not None
            or p.username is not None or p.password is not None
            or p.query or p.fragment or p.path not in
            {"/moj-prop/", "/moj-prop-intake/"}):
        raise ValueError("public first-party GET targets only")


def safe_result(status, content_type, raw=b"", final_url=""):
    if final_url:
        verify_target(final_url)
    output = {
        "http_status": status,
        "html": content_type == "text/html",
        "response_truncated": len(raw) > MAX_BYTES,
    }
    if status == 200 and content_type == "text/html":
        html = raw[:MAX_BYTES].decode("utf-8", errors="replace").lower()
        scan = FormCounter()
        scan.feed(html)
        output.update(
            sku_moj_prop_01="moj-prop-01" in html,
            starter30_seen="mojprop-starter30" in html,
            simulated_visible="simulat" in html,
            native_30_trx_visible=("30 trx" in html or "30 native trx" in html),
            conditional_funding_visible="conditional" in html and "100" in html,
            verified_payment_clock_visible="28" in html,
            closed_position_rule_visible="50" in html,
            six_days_rule_visible="6" in html,
            consent_word_visible="consent" in html,
            public_form_count=scan.forms,
            public_post_form_count=scan.post_forms,
            public_button_count=scan.buttons,
        )
    return output


def dns(host: str):
    if host not in HOSTS:
        raise ValueError("allowlisted host required")
    try:
        found = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
        return {"resolves": bool(found), "address_count": len({x[4][0] for x in found})}
    except OSError as exc:
        return {"resolves": False, "address_count": 0,
                "error_type": type(exc).__name__}


def public_get(url: str):
    verify_target(url)
    req = Request(url, headers={
        "User-Agent": "MojProp-OwnPublicFunnelAudit/1.0",
        "Accept": "text/html,application/xhtml+xml",
    }, method="GET")
    try:
        with urlopen(req, timeout=TIMEOUT, context=ssl.create_default_context()) as res:
            final = res.geturl()
            code = res.status
            mime = res.headers.get_content_type()
            data = res.read(MAX_BYTES + 1)
    except HTTPError as exc:
        final = exc.geturl()
        code = exc.code
        mime = exc.headers.get_content_type() if exc.headers else "unknown"
        data = b""
    except (OSError, URLError, TimeoutError) as exc:
        return {"reachable": False, "error_type": type(exc).__name__}
    try:
        result = safe_result(code, mime, data, final)
    except ValueError:
        return {"reachable": False, "unexpected_external_redirect": True,
                "http_status": code}
    return {"reachable": True, **result}


def audit():
    dns_results = {h: dns(h) for h in HOSTS}
    paths = {k: public_get(v) for k, v in TARGETS.items()}
    home = paths["plan1"]
    intake = paths["intake"]
    page_visible = (
        home.get("reachable") is True and home.get("http_status") == 200
        and home.get("sku_moj_prop_01") is True
        and home.get("simulated_visible") is True
    )
    route_found = intake.get("reachable") is True and intake.get("http_status") not in {
        404, 500, 502, 503, 504,
    }
    return {
        "checked_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "PUBLIC_GET_ONLY_NO_FORMS_SUBMITTED_NO_PAYMENT",
        "dns": dns_results,
        "pages": paths,
        "canonical_plan1_disclosure_visible": bool(page_visible),
        "intake_route_present": bool(route_found),
        "customer_submission_proven": False,
        "real_sale_or_revenue_proven": False,
        "verdict": "PUBLIC_SITE_READABLE" if page_visible else "PUBLIC_SITE_NOT_CONFIRMED",
    }


if __name__ == "__main__":
    print(json.dumps(audit(), sort_keys=True))
