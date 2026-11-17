#!/usr/bin/env python3
"""C135 public HTTPS GET-only diagnosis of MOJ-PROP-01 dedicated consent.

No customer POST, email, buyer data, CRMs, authentication, key, token logging,
payment, account creation, SSH, deployment or production-write operation.
Even a valid form GET does not verify CSRF POST or persistent opt-in.
"""
from __future__ import annotations

from dataclasses import dataclass
from html.parser import HTMLParser
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener
import re
import sys

HOST = "https://mojplaywin.com"
ENDPOINTS = {
    "EN": HOST + "/moj-prop-interest/form/",
    "FA": HOST + "/moj-prop-interest/form/?lang=fa",
}
MAX_HTML = 256 * 1024
USER_AGENT = "MojProp-C135-ReadOnly-Source-Check/1.0"


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class PublicForm(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.lang = ""
        self.direction = ""
        self.forms = []
        self.inputs = []

    def handle_starttag(self, tag, attrs):
        data = dict(attrs)
        if tag == "html":
            self.lang, self.direction = data.get("lang", ""), data.get("dir", "")
        if tag == "form":
            self.forms.append(data)
        if tag == "input":
            self.inputs.append(data)


@dataclass(frozen=True)
class FormGetEvidence:
    status: int
    no_redirect: bool
    typed_html: bool
    no_store: bool
    denied_frame: bool
    csrf_and_consent_form: bool
    localized: bool

    @property
    def valid_public_get(self) -> bool:
        return (self.status == 200 and self.no_redirect and self.typed_html
                and self.no_store and self.denied_frame
                and self.csrf_and_consent_form and self.localized)


def assess(*, status: int, final_url: str, requested_url: str,
           headers: dict[str, str], body: bytes, lang: str) -> FormGetEvidence:
    if lang not in ("en", "fa") or requested_url not in ENDPOINTS.values():
        raise ValueError("only exact fixed Moj Prop public GET routes permitted")
    # Content-type/headers are untrusted, never echoed back to logs.
    normalized = {str(k).lower(): str(v).lower() for k, v in headers.items()}
    typed = normalized.get("content-type", "").startswith("text/html")
    store = "no-store" in normalized.get("cache-control", "")
    xfo = normalized.get("x-frame-options", "") == "deny"
    csp = normalized.get("content-security-policy", "")
    safe_headers = xfo and "form-action 'self'" in csp and "frame-ancestors 'none'" in csp
    form_ok, localized = False, False
    if (status == 200 and typed and isinstance(body, bytes)
            and len(body) <= MAX_HTML):
        try:
            html = body.decode("utf-8", "strict")
            parser = PublicForm()
            parser.feed(html)
            parser.close()
            options = {(p.get("name"), p.get("value"), p.get("type"))
                       for p in parser.inputs}
            fields = {p.get("name") for p in parser.inputs}
            form_ok = (
                len(parser.forms) == 1
                and parser.forms[0].get("method", "").lower() == "post"
                and parser.forms[0].get("action") == "/moj-prop-interest/"
                and ("plan_code", "MOJ-PROP-01", "hidden") in options
                and ("consent_version", "moj-prop-interest-v1", "hidden") in options
                and ("source_language", lang, "hidden") in options
                and ("contact_consent", "yes", "checkbox") in options
                and "email" in fields and "csrfmiddlewaretoken" in fields
                and "wallet" not in fields and "password" not in fields
            )
            localized = (parser.lang == lang
                         and (lang != "fa" or parser.direction == "rtl"))
        except (UnicodeError, ValueError, TypeError):
            pass
    return FormGetEvidence(
        status=int(status), no_redirect=final_url == requested_url,
        typed_html=typed, no_store=store, denied_frame=safe_headers,
        csrf_and_consent_form=form_ok, localized=localized,
    )


def observe(label: str) -> FormGetEvidence:
    if label not in ENDPOINTS:
        raise ValueError("invalid fixed language")
    url = ENDPOINTS[label]
    request = Request(url, method="GET", headers={
        "Accept": "text/html",
        "User-Agent": USER_AGENT,
        "Cache-Control": "no-store",
    })
    headers: dict[str, str] = {}
    body = b""
    status = 0
    final = ""
    try:
        with build_opener(NoRedirect).open(request, timeout=15) as response:
            status = response.status
            final = response.geturl()
            headers = dict(response.info().items())
            if status == 200:
                body = response.read(MAX_HTML + 1)
    except HTTPError as err:
        # 404/redirect are evidence of NOT ready; do not follow the new URL.
        status = err.code
        final = url if err.code not in (301, 302, 303, 307, 308) else ""
        headers = dict(err.headers.items()) if err.headers else {}
        err.close()
    except (URLError, TimeoutError, OSError, ValueError):
        # An unavailable transport is not silently converted into HTTP 200.
        status = 0
    return assess(status=status, final_url=final, requested_url=url,
                  headers=headers, body=body, lang=label.lower())


def main(argv: list[str]) -> int:
    if len(argv) != 1:
        raise SystemExit("usage: python scripts/mojprop_live_plan1_optin_get_readonly_c135.py")
    results = {label: observe(label) for label in ("EN", "FA")}
    for label, data in results.items():
        prefix = "MOJPROP_C135_" + label + "_"
        print(prefix + "HTTP=" + str(data.status))
        print(prefix + "NO_REDIRECT=" + str(data.no_redirect).lower())
        print(prefix + "TYPED_HTML=" + str(data.typed_html).lower())
        print(prefix + "NO_STORE=" + str(data.no_store).lower())
        print(prefix + "FRAMING_DENIED=" + str(data.denied_frame).lower())
        print(prefix + "CSRF_CONSENT_FORM=" + str(data.csrf_and_consent_form).lower())
        print(prefix + "LANGUAGE_CORRECT=" + str(data.localized).lower())
        print(prefix + "PUBLIC_GET_CONTRACT=" + str(data.valid_public_get).lower())
    print("MOJPROP_C135_PUBLIC_GET_BOTH_VALID=" +
          str(all(data.valid_public_get for data in results.values())).lower())
    print("MOJPROP_C135_REAL_BUYER_POST_VERIFIED=false")
    print("MOJPROP_C135_PAYMENT_OR_ENROLLMENT=false")
    print("MOJPROP_C135_LIVE_RELEASE_AUTHORIZED=false")
    return 0  # diagnostic success != public release readiness


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
