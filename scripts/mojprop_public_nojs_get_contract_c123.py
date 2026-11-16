"""Classify public Moj Prop native no-JS GET forms without customer writes.

This scanner reads already-downloaded public GET bodies. It NEVER performs a
network request, submits a form, records CSRF/receipt values, or accesses DB.
A diagnostic PASS is not approval to deploy, charge or create a paid account.
"""
from __future__ import annotations

from html.parser import HTMLParser
from pathlib import Path
import sys

_MAX_BYTES = 256 * 1024
_FORM_FIELDS = {
    "intake": {
        "name", "email", "service", "horizon", "notes",
        "consent", "csrfmiddlewaretoken", "idempotency_key",
    },
    "status": {"receipt_token", "csrfmiddlewaretoken"},
}
_ACTIONS = {
    "intake": "/moj-prop-intake/?format=html",
    "status": "/moj-prop-status/?format=html",
}


class FormShape(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.has_html = False
        self.scripts = 0
        self.forms: list[dict] = []
        self.active: dict | None = None

    def handle_starttag(self, tag, attrs):
        if tag == "html":
            self.has_html = True
        if tag == "script":
            self.scripts += 1
        if tag == "form":
            attrs = dict(attrs)
            self.active = {
                "method": attrs.get("method", "").lower(),
                "action": attrs.get("action", ""),
                "fields": set(),
            }
            self.forms.append(self.active)
        elif self.active is not None and tag in {"input", "textarea", "select"}:
            name = dict(attrs).get("name")
            if name:
                self.active["fields"].add(name)

    def handle_endtag(self, tag):
        if tag == "form":
            self.active = None


def classify_document(raw: bytes, kind: str) -> bool:
    """True only for the exact expected HTML POST form, never JSON or 404."""
    if kind not in _FORM_FIELDS or len(raw) > _MAX_BYTES:
        return False
    try:
        source = raw.decode("utf-8")
        document = FormShape()
        document.feed(source)
        document.close()
    except (UnicodeError, ValueError):
        return False
    return bool(document.has_html and document.scripts == 0
                and len(document.forms) == 1
                and document.forms[0]["method"] == "post"
                and document.forms[0]["action"] == _ACTIONS[kind]
                and _FORM_FIELDS[kind] <= document.forms[0]["fields"])


def read_and_classify(path: Path, kind: str) -> bool:
    try:
        if path.is_symlink() or not path.is_file():
            return False
        with path.open("rb") as stream:
            raw = stream.read(_MAX_BYTES + 1)
    except OSError:
        return False
    return classify_document(raw, kind)


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        raise SystemExit("usage: probe.py PUBLIC_INTAKE_GET_BODY PUBLIC_STATUS_GET_BODY")
    results = {
        "intake": read_and_classify(Path(argv[1]), "intake"),
        "status": read_and_classify(Path(argv[2]), "status"),
    }
    for name, valid in results.items():
        print(f"PUBLIC_MOJPROP_{name.upper()}_HTML_CONTRACT=" +
              ("PASS" if valid else "FAIL"))
    print("PUBLIC_MOJPROP_NOJS_BACKEND_GATE=" +
          ("PASS" if all(results.values()) else "DEGRADED"))
    print("PUBLIC_MOJPROP_NOJS_READONLY=true")
    print("PUBLIC_MOJPROP_PAID_CHECKOUT_VERIFIED=false")
    return 0  # Evidence job reports a detected gap, never authorizes a release.


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
