"""Read-only public Moj Prop horizon contract: never submit buyer data.

Reads only a locally downloaded public GET HTML body. Emits bounded booleans and
a source-class label; never prints page text, email, cookie, CSRF or form fields.
"""
from __future__ import annotations

import hashlib
import json
import sys
from html.parser import HTMLParser
from pathlib import Path

EXPECTED = ("urgent", "week", "month", "review")
ENDPOINT = "const endpoint='/moj-prop-intake/';"
MAX_HTML_BYTES = 1_048_576


class FormContract(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.in_horizon = False
        self.depth = 0
        self.horizon_values = []
        self.consents = False
        self.has_form = False

    def handle_starttag(self, tag, attributes):
        attrs = dict(attributes)
        if tag == "form" and attrs.get("id") == "request-form":
            self.has_form = True
        if tag == "input" and attrs.get("id") == "consent" and attrs.get("type") == "checkbox":
            self.consents = True
        if tag == "select":
            if self.in_horizon:
                self.depth += 1
            elif attrs.get("id") == "horizon" or attrs.get("name") == "horizon":
                self.in_horizon = True
                self.depth = 1
        elif tag == "option" and self.in_horizon:
            self.horizon_values.append(attrs.get("value"))

    def handle_endtag(self, tag):
        if tag == "select" and self.in_horizon:
            self.depth -= 1
            if self.depth <= 0:
                self.in_horizon = False
                self.depth = 0


def classify(public_html: bytes, sources: dict[str, bytes]) -> dict:
    valid = type(public_html) is bytes and 0 < len(public_html) <= MAX_HTML_BYTES
    data = {
        "schema": "mojprop.public.horizon_contract.readonly.c124.v1",
        "read_only": True,
        "body_available": valid,
        "source_class": "unknown",
        "exact_horizon_choices": False,
        "backend_intake_link_present": False,
        "consent_checkbox_present": False,
        "request_form_present": False,
        "frontend_contract_valid": False,
        "live_backend_post_or_storage_tested": False,
        "commercial_release_authorized": False,
    }
    if not valid:
        return data
    digest = hashlib.sha256(public_html).digest()
    data["source_class"] = next(
        (name for name, value in sources.items()
         if type(value) is bytes and hashlib.sha256(value).digest() == digest),
        "unrecognized_review_required"
    )
    p = FormContract()
    try:
        text = public_html.decode("utf-8", "strict")
        p.feed(text)
        p.close()
    except (UnicodeDecodeError, ValueError):
        return data
    data["exact_horizon_choices"] = tuple(p.horizon_values) == EXPECTED
    data["backend_intake_link_present"] = ENDPOINT in text
    data["consent_checkbox_present"] = p.consents
    data["request_form_present"] = p.has_form
    data["frontend_contract_valid"] = all(
        data[key] for key in ("exact_horizon_choices", "backend_intake_link_present",
                             "consent_checkbox_present", "request_form_present")
    )
    return data


def main(argv: list[str]) -> int:
    if len(argv) != 4:
        print("MOJPROP_LIVE_HORIZON_C124=" + json.dumps(
            classify(b"", {}), sort_keys=True))
        return 2
    try:
        live = Path(argv[1]).read_bytes()
        sources = {
            "current_legacy": Path(argv[2]).read_bytes(),
            "current_v4": Path(argv[3]).read_bytes(),
        }
    except OSError:
        live, sources = b"", {}
    print("MOJPROP_LIVE_HORIZON_C124=" + json.dumps(
        classify(live, sources), sort_keys=True))
    # A site mismatch must not mask a transient HTTP transport diagnosis.
    # Always classify fail-closed, never silently say the site is ready.
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
