"""Classify Moj Prop first-party support fallback from GET-only public evidence.

Read-only: already downloaded HTML plus three sanitized transport facts only.
Never sends mail, posts customer data, reads CSRF or receipt secrets, or
claims a paid/registered buyer. A support link is NOT proven deliverable.
"""
from __future__ import annotations

from html.parser import HTMLParser
from pathlib import Path
import re
import sys

_MAX_HTML_BYTES = 256 * 1024
_MAX_TRANSPORT_BYTES = 512
_SUPPORT = "support@mojplaywin.com"
_PLAN1_MAILTO = (
    "mailto:support@mojplaywin.com?subject="
    "MOJ-PROP-01%20Prelaunch%20Information%20Request"
)
_GENERAL_MAILTO = (
    "mailto:support@mojplaywin.com?subject="
    "Moj%20Prop%20Manual%20Service%20Enquiry"
)
_TRANSPORT_KEYS = (
    "GET_ONLY_mojprop_contact_HTTP",
    "GET_ONLY_mojprop_contact_CURL_EXIT",
    "GET_ONLY_mojprop_contact_REDIRECTS",
)


class _ContactDocument(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.has_html = False
        self.scripts = 0
        self.forms = 0
        self.links: list[str] = []
        self.title_open = False
        self.title = ""
        self.words: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag == "html":
            self.has_html = True
        if tag == "script":
            self.scripts += 1
        if tag == "form":
            self.forms += 1
        if tag == "title":
            self.title_open = True
        if tag == "a":
            self.links.append(dict(attrs).get("href", ""))

    def handle_endtag(self, tag):
        if tag == "title":
            self.title_open = False

    def handle_data(self, data):
        self.words.append(data)
        if self.title_open:
            self.title += data


def classify_contact(raw: bytes) -> bool:
    """Require actual manual Plan1 support terms and no misleading buyer form.

    Checks are intentionally strict, to fail closed on stale generic pages
    rather than infer contact readiness from HTTP 200 or arbitrary mailto.
    """
    if len(raw) > _MAX_HTML_BYTES:
        return False
    try:
        parsed = _ContactDocument()
        parsed.feed(raw.decode("utf-8"))
        parsed.close()
    except (UnicodeError, ValueError):
        return False
    all_text = " ".join(parsed.words).lower()
    safe_links = all(
        href.startswith(("/", "#"))
        or href in (_PLAN1_MAILTO, _GENERAL_MAILTO)
        for href in parsed.links
    )
    return bool(
        parsed.has_html
        and parsed.scripts == 0
        and parsed.forms == 0
        and "moj prop plan 1" in parsed.title.lower()
        and safe_links
        and _PLAN1_MAILTO in parsed.links
        and _GENERAL_MAILTO in parsed.links
        and "/moj-prop/" in parsed.links
        and "/moj-prop/#request" not in parsed.links
        and _SUPPORT in all_text
        and "moj-prop-01" in all_text
        and "prelaunch only" in all_text
        and "no payment details or private credentials" in all_text
        and "not a verified plan 1 lead" in all_text
        and "nothing is sent automatically" in all_text
    )


def parse_transport(source: str) -> dict[str, str] | None:
    """Three non-secret fixed-key network decisions; no body or user data."""
    if len(source.encode("utf-8")) > _MAX_TRANSPORT_BYTES:
        return None
    values = {}
    for line in source.splitlines():
        if "=" not in line:
            return None
        key, val = line.split("=", 1)
        if key not in _TRANSPORT_KEYS or key in values:
            return None
        if key.endswith("_HTTP"):
            valid = bool(re.fullmatch(r"(?:000|[1-5][0-9]{2})", val))
        else:
            valid = val == "unknown" or bool(re.fullmatch(r"(?:0|[1-9][0-9]{0,2})", val))
        if not valid:
            return None
        values[key] = val
    return values if set(values) == set(_TRANSPORT_KEYS) else None


def classify_transport(evidence: dict[str, str] | None) -> bool:
    return bool(
        evidence
        and evidence[_TRANSPORT_KEYS[0]] == "200"
        and evidence[_TRANSPORT_KEYS[1]] == "0"
        and evidence[_TRANSPORT_KEYS[2]] == "0"
    )


def read_strict(path: Path, size: int) -> bytes | None:
    try:
        if path.is_symlink() or not path.is_file() or path.stat().st_size > size:
            return None
        return path.read_bytes()
    except OSError:
        return None


def main(argv: list[str]) -> int:
    if len(argv) != 4:
        raise SystemExit("usage: contact_c127.py PUBLIC_CONTACT_HTML SANITIZED_TRANSPORT GITHUB_STEP_SUMMARY")
    body = read_strict(Path(argv[1]), _MAX_HTML_BYTES)
    evidence = read_strict(Path(argv[2]), _MAX_TRANSPORT_BYTES)
    html_ok = bool(body is not None and classify_contact(body))
    transport = parse_transport(evidence.decode("utf-8")) if evidence is not None else None
    transport_ok = classify_transport(transport)
    gate = "GET_ONLY_SUPPORT_PAGE_PRESENT_NOT_DELIVERY" if html_ok and transport_ok else "BLOCKED"
    print("PUBLIC_MOJPROP_OFFICIAL_CONTACT_HTML_CONTRACT=" + ("PASS" if html_ok else "FAIL"))
    print("PUBLIC_MOJPROP_OFFICIAL_CONTACT_TRANSPORT_CONTRACT=" + ("PASS" if transport_ok else "FAIL"))
    print("PUBLIC_MOJPROP_OFFICIAL_CONTACT_GATE=" + gate)
    print("PUBLIC_MOJPROP_OFFICIAL_CONTACT_MESSAGE_SENT=false")
    print("PUBLIC_MOJPROP_OFFICIAL_CONTACT_VERIFIED_LEAD=false")
    target = Path(argv[3])
    if target.is_symlink():
        raise SystemExit("GitHub step summary path must not be a symlink")
    with target.open("a", encoding="utf-8") as out:
        out.write(
            "\n### MOJ PROP official manual-contact fallback: " + gate + "\n"
            + "- Contact page HTML: " + ("PASS" if html_ok else "FAIL") + "\n"
            + "- Contact direct HTTPS GET: " + ("PASS" if transport_ok else "FAIL") + "\n"
            + "- Mail delivery / consented CRM lead / paid order: NOT VERIFIED\n"
            + "- A prefilled mail-app link is not an email sent or buyer acquired.\n"
        )
    return 0  # diagnostic evidence success is never permission to launch


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
