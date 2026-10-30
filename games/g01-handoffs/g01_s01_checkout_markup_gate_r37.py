#!/usr/bin/env python3
"""G-01 -> S-01 handoff: read-only offline checkout/invoice markup accessibility gate.
Run: python3 g01_s01_checkout_markup_gate_r37.py path/to/authorized-copy.html
Or: python3 g01_s01_checkout_markup_gate_r37.py --self-test
No network, no site access, no secrets, no payment and no file mutations.
This static gate does not replace actual browser, backend or payment QA.
"""
from __future__ import annotations
from html.parser import HTMLParser
from pathlib import Path
import json
import sys

class Gate(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.ids = set()
        self.labels = set()
        self.controls = []
        self.buttons = []
        self.links = []
        self.stack = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if a.get("id"):
            if a["id"] in self.ids:
                self.controls.append(("DUPLICATE_ID", a["id"]))
            self.ids.add(a["id"])
        if tag == "label" and a.get("for"):
            self.labels.add(a["for"])
        if tag in ("input", "select", "textarea") and a.get("type", "").lower() not in ("hidden", "submit", "button", "reset", "image"):
            self.controls.append(("CONTROL", a.get("id"), a.get("aria-label"), a.get("aria-labelledby")))
        if tag == "button":
            self.buttons.append({"aria": a.get("aria-label") or a.get("aria-labelledby"), "text": ""})
            self.stack.append(len(self.buttons) - 1)
        if tag == "a":
            self.links.append((a.get("href", ""), a.get("target", ""), a.get("rel", "")))

    def handle_data(self, data):
        if self.stack:
            self.buttons[self.stack[-1]]["text"] += data

    def handle_endtag(self, tag):
        if tag == "button" and self.stack:
            self.stack.pop()

    def findings(self):
        result = []
        for item in self.controls:
            if item[0] == "DUPLICATE_ID":
                result.append("DUPLICATE_ID")
            elif item[0] == "CONTROL" and not (item[2] or item[3] or (item[1] and item[1] in self.labels)):
                result.append("UNLABELLED_CONTROL")
        for b in self.buttons:
            if not (b["aria"] or b["text"].strip()):
                result.append("UNNAMED_BUTTON")
        for href, target, rel in self.links:
            if href.strip().lower().startswith("javascript:"):
                result.append("UNSAFE_JS_LINK")
            if target.lower() == "_blank" and "noopener" not in rel.lower().split():
                result.append("MISSING_NOOPENER")
        return sorted(result)

def inspect(text: str) -> list[str]:
    gate = Gate()
    gate.feed(text)
    gate.close()
    return gate.findings()

def main(argv):
    if len(argv) == 2 and argv[1] == "--self-test":
        safe = '<label for="email">Email</label><input id="email"><button>Invoice</button><a href="/invoice.pdf" target="_blank" rel="noopener">PDF</a>'
        unsafe = '<input id="x"><input id="x"><button></button><a href="javascript:alert(1)" target="_blank">Invoice</a>'
        assert inspect(safe) == [], inspect(safe)
        assert set(inspect(unsafe)) == {"DUPLICATE_ID", "UNLABELLED_CONTROL", "UNNAMED_BUTTON", "UNSAFE_JS_LINK", "MISSING_NOOPENER"}
        print("G01_S01_R37_SELF_TEST_PASS")
        return 0
    if len(argv) != 2:
        print("usage: gate.py <authorized-offline-html> | --self-test", file=sys.stderr)
        return 2
    p = Path(argv[1])
    if not p.is_file() or p.is_symlink() or p.stat().st_size > 2_000_000:
        print("BLOCKED: require a regular, <=2 MB authorized offline HTML file", file=sys.stderr)
        return 2
    findings = inspect(p.read_text(encoding="utf-8"))
    print(json.dumps({"status": "PASS" if not findings else "REVIEW_REQUIRED",
                      "finding_codes": findings}, sort_keys=True))
    return 1 if findings else 0

if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
