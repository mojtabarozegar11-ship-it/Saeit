"""C128: pin down why published Moj Prop contact differs from audited source.

Pure, read-only inspection of already downloaded PUBLIC contact HTML plus the
reviewed GitHub template. No network, app imports, cookies, emails, CSRF,
buyer data, wallet, POST, disk writes or deployment. Output has ONLY fixed
boolean keys (no URLs, HTML, hashes, customer fields or excerpts).
"""
from __future__ import annotations

from pathlib import Path
import sys

from scripts.mojprop_public_official_contact_contract_c127 import (
    _ContactDocument, _GENERAL_MAILTO, _PLAN1_MAILTO, _SUPPORT,
    _MAX_HTML_BYTES, classify_contact, _safe_contact_href,
)

_CHECKS = (
    "html_document",
    "script_free",
    "form_free",
    "plan1_title",
    "official_support_visible",
    "plan1_subject_mailto",
    "general_support_mailto",
    "all_links_first_party",
    "legacy_generic_form_absent",
    "prelaunch_warning_visible",
    "no_payment_credentials_warning",
    "support_is_not_crm_lead",
    "no_auto_email_notice",
    "exact_reviewed_template_bytes",
    "complete_contact_contract",
)


def checks(raw: bytes | None, reviewed: bytes | None) -> dict[str, bool]:
    """Return a *fixed* boolean matrix. No untrusted content in keys or values."""
    result = {key: False for key in _CHECKS}
    if type(raw) is not bytes or not 1 <= len(raw) <= _MAX_HTML_BYTES:
        return result
    try:
        page = _ContactDocument()
        page.feed(raw.decode("utf-8"))
        page.close()
    except (UnicodeError, ValueError):
        return result
    words = " ".join(" ".join(page.words).lower().split())
    result.update({
        "html_document": bool(page.has_html),
        "script_free": page.scripts == 0,
        "form_free": page.forms == 0,
        "plan1_title": "moj prop plan 1" in page.title.lower(),
        "official_support_visible": _SUPPORT in words,
        "plan1_subject_mailto": _PLAN1_MAILTO in page.links,
        "general_support_mailto": _GENERAL_MAILTO in page.links,
        "all_links_first_party": all(_safe_contact_href(h) for h in page.links),
        "legacy_generic_form_absent": "/moj-prop/#request" not in page.links,
        "prelaunch_warning_visible": "prelaunch only" in words,
        "no_payment_credentials_warning": "no payment details or private credentials" in words,
        "support_is_not_crm_lead": "not a verified plan 1 lead" in words,
        "no_auto_email_notice": "nothing is sent automatically" in words,
        "exact_reviewed_template_bytes": (
            type(reviewed) is bytes
            and 0 < len(reviewed) <= _MAX_HTML_BYTES
            and raw == reviewed
        ),
        "complete_contact_contract": classify_contact(raw),
    })
    return result


def safe_read(path: Path) -> bytes | None:
    try:
        if path.is_symlink() or not path.is_file() or not 0 < path.stat().st_size <= _MAX_HTML_BYTES:
            return None
        with path.open("rb") as reader:
            body = reader.read(_MAX_HTML_BYTES + 1)
        return body if 0 < len(body) <= _MAX_HTML_BYTES else None
    except OSError:
        return None


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        raise SystemExit("usage: c128.py PUBLIC_CONTACT_HTML REVIEWED_SOURCE_TEMPLATE")
    findings = checks(safe_read(Path(argv[1])), safe_read(Path(argv[2])))
    for key in _CHECKS:
        print("MOJPROP_C128_" + key.upper() + "=" + str(findings[key]).lower())
    print("MOJPROP_C128_LIVE_RUNTIME_SOURCE_PROVEN=false")
    print("MOJPROP_C128_CUSTOMER_POST=false")
    print("MOJPROP_C128_PAYMENT_OR_EMAIL=false")
    return 0  # detailed evidence is not a restore or deployment permission


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
