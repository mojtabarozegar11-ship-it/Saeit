#!/usr/bin/env python3
"""GET-only public lead-route audit. Never submits forms, authenticates or sends data."""
from __future__ import annotations
from dataclasses import dataclass
from html.parser import HTMLParser
import json
import urllib.error
import urllib.parse
import urllib.request

HOST = "zomorodmelal.ir"
ORIGIN = "https://" + HOST
STORE = "/store/"
FORM = "/ask-master/index.php?service=1"
CONTACT = "/contact/"
PATHS = (STORE, FORM, CONTACT)
MAX_BYTES = 262144
TIMEOUT_SECONDS = 12


@dataclass(frozen=True)
class Observation:
    status: int | None
    html: str = ""
    redirect: str = ""
    issue: str = ""


class NeverRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


class PublicHtml(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.hrefs = []
        self.forms = []
        self.current = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "a":
            self.hrefs.append(attrs.get("href", ""))
        if tag == "form":
            form = {
                "method": attrs.get("method", "get").lower(),
                "action": attrs.get("action", ""),
                "has_field": False,
                "has_submit": False,
            }
            self.forms.append(form)
            self.current = form
        if self.current is not None:
            if tag in ("input", "textarea"):
                kind = attrs.get("type", "text").lower()
                if tag == "textarea" or kind in ("text", "email", "tel", "search"):
                    self.current["has_field"] = True
                if tag == "input" and kind == "submit":
                    self.current["has_submit"] = True
            if tag == "button" and attrs.get("type", "submit").lower() == "submit":
                self.current["has_submit"] = True

    def handle_endtag(self, tag):
        if tag == "form":
            self.current = None


def expected_location(location: str) -> bool:
    url = urllib.parse.urlsplit(urllib.parse.urljoin(ORIGIN + CONTACT, location))
    return (url.scheme == "https" and url.hostname == HOST and
            url.port in (None, 443) and url.username is None and
            url.path == "/ask-master/index.php" and url.query == "service=1")


def safe_form_action(action: str) -> bool:
    url = urllib.parse.urlsplit(urllib.parse.urljoin(ORIGIN + FORM, action))
    return (url.scheme == "https" and url.hostname == HOST and
            url.port in (None, 443) and url.username is None)


def fetch_public(path: str, opener=None) -> Observation:
    if path not in PATHS:
        raise ValueError("outside fixed public audit paths")
    if opener is None:
        opener = urllib.request.build_opener(NeverRedirect())
    request = urllib.request.Request(
        ORIGIN + path,
        headers={"Accept": "text/html", "Accept-Encoding": "identity",
                 "User-Agent": "ZomorodLeadGETAudit/1.0"},
        method="GET",
    )
    try:
        with opener.open(request, timeout=TIMEOUT_SECONDS) as response:
            status = response.status
            mime = response.headers.get("Content-Type", "").lower()
            if status != 200:
                return Observation(status=status, issue="unexpected_status")
            if "text/html" not in mime:
                return Observation(status=status, issue="unexpected_content_type")
            raw = response.read(MAX_BYTES + 1)
            if len(raw) > MAX_BYTES:
                return Observation(status=status, issue="html_too_large")
            return Observation(status=status, html=raw.decode("utf-8", "replace"))
    except urllib.error.HTTPError as error:
        location = error.headers.get("Location", "")
        return Observation(status=error.code, redirect=location)
    except (urllib.error.URLError, TimeoutError, OSError, ValueError):
        return Observation(status=None, issue="transport_error")


def diagnose(fetcher=fetch_public) -> dict:
    store = fetcher(STORE)
    form = fetcher(FORM)
    contact = fetcher(CONTACT)
    store_tags = PublicHtml()
    form_tags = PublicHtml()
    if store.status == 200 and store.html:
        store_tags.feed(store.html)
    if form.status == 200 and form.html:
        form_tags.feed(form.html)
    store_inquiry = FORM in store_tags.hrefs
    phone_present = "tel:+989022048691" in store_tags.hrefs
    usable_form = any(
        x["method"] == "post" and x["has_field"] and x["has_submit"] and
        safe_form_action(x["action"]) for x in form_tags.forms
    )
    contact_ok = (
        contact.status == 200 and bool(contact.html)
    ) or (
        contact.status in (301, 302, 303, 307, 308) and
        expected_location(contact.redirect)
    )
    qualified = bool(store.status == 200 and form.status == 200
                     and store_inquiry and phone_present and usable_form and contact_ok)
    return {
        "scope": "existing_zomorod_public_lead_route_get_only",
        "store_http_status": store.status,
        "form_http_status": form.status,
        "contact_http_status": contact.status,
        "store_inquiry_link_observed": store_inquiry,
        "store_official_phone_observed": phone_present,
        "form_post_fields_and_submit_observed": usable_form,
        "contact_route_usable_or_redirects_to_form": contact_ok,
        "lead_get_route_qualified": qualified,
        "result": "public_lead_route_observed" if qualified else "blocked_or_unverified",
        "customer_leads_received_verified": False,
        "payment_received_verified": False,
        "http_get_requests": len(PATHS),
        "lead_submissions_sent": 0,
        "forms_submitted": 0,
        "remote_writes": 0,
        "credentials_used": False,
    }


if __name__ == "__main__":
    print("ZM_LIVE_LEAD_ROUTE=" + json.dumps(diagnose(), sort_keys=True))
