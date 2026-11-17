#!/usr/bin/env python3
"""C155: read-only public GET of 2 exact static Moj Prop pages.

Compares response bytes to exact *reviewed* source snapshots. It never
posts, sends email, touches a database, retrieves private data, authorizes
deployment, logs live HTML, or claims that HTTP 200 proves CRM readiness.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1] / "templates/moj-prop-v4"
MAX_HTML = 196608
TIMEOUT = 15
URLS = (
    ("home", "https://mojplaywin.com/moj-prop/"),
    ("contact", "https://mojplaywin.com/moj-prop/contact/"),
)
GIT_HOME_BLOB = "30b7fe4400f88252f3b71a581f96a796ca853b6c"
GIT_CONTACT_BLOB = "7f715ed5297c4682f6907475e6dcbe816b2e1e40"


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _read_pinned(relative: str, expected_blob: str) -> bytes:
    file = ROOT / relative
    if file.is_symlink() or not file.is_file():
        raise ValueError("reviewed static source unavailable")
    value = file.read_bytes()
    if len(value) < 100 or len(value) > MAX_HTML:
        raise ValueError("reviewed source size invalid")
    blob = b"blob " + str(len(value)).encode("ascii") + b"\0" + value
    if hashlib.sha1(blob).hexdigest() != expected_blob:
        raise ValueError("reviewed source has changed since baseline attestation")
    return value


def allowed_snapshots() -> dict[str, dict[str, bytes]]:
    old_home = _read_pinned(
        "baselines/index-main-before-plan1-c153.html", GIT_HOME_BLOB
    )
    old_contact = _read_pinned(
        "baselines/contact-index-pre-plan1.html", GIT_CONTACT_BLOB
    )
    historical = (ROOT / "baselines/index-v4.html").read_bytes()
    approved_home = (ROOT / "index.html").read_bytes()
    approved_contact = (ROOT / "contact/index.html").read_bytes()
    if any(len(value) > MAX_HTML for value in (
        historical, approved_home, approved_contact
    )):
        raise ValueError("unexpectedly large source static page")
    return {
        "home": {
            "known_legacy_v4": historical,
            "known_legacy_v4_markerless": historical.replace(
                b"<!-- MOJ_PROP_CATALOG_RELEASE_V4 -->\n", b"", 1
            ),
            "known_current_main": old_home,
            "approved_plan1_source": approved_home,
        },
        "contact": {
            "known_current_main": old_contact,
            "approved_plan1_source": approved_contact,
        },
    }


def classify(raw: bytes, snapshots: dict[str, bytes]) -> str:
    # No fuzzy text searches, substring matches, or mere HTTP200 checks.
    if not raw or len(raw) > MAX_HTML:
        return "unreviewed_or_unavailable"
    for name, known in snapshots.items():
        if raw == known:
            return name
    return "unreviewed_or_unavailable"


def _get(url: str) -> tuple[int, bytes]:
    # Fixed HTTPS origin and paths; never follow redirects to new hosts.
    if url not in (item[1] for item in URLS):
        raise ValueError("unapproved external URL")
    opener = urllib.request.build_opener(_NoRedirect)
    req = urllib.request.Request(
        url, headers={"User-Agent": "MOJPROP-C155-readonly/1.0",
                      "Accept-Encoding": "identity", "Accept": "text/html"},
        method="GET",
    )
    try:
        with opener.open(req, timeout=TIMEOUT) as response:
            code = response.getcode()
            if code != 200 or response.geturl() != url:
                return code, b""
            length = response.headers.get("Content-Length")
            if length is not None and (
                not length.isascii() or not length.isdecimal()
                or int(length) > MAX_HTML
            ):
                return code, b""
            content = response.read(MAX_HTML + 1)
            return code, content if len(content) <= MAX_HTML else b""
    except urllib.error.HTTPError as exc:
        # Status code is public metadata. Never expose body or response headers.
        return int(exc.code), b""
    except (urllib.error.URLError, TimeoutError, OSError, ValueError):
        return 0, b""


def inspect(getter=_get, snapshots=None) -> dict:
    snapshots = allowed_snapshots() if snapshots is None else snapshots
    pages = {}
    for name, url in URLS:
        try:
            status, raw = getter(url)
        except (OSError, TimeoutError, ValueError):
            status, raw = 0, b""
        kind = classify(raw, snapshots[name]) if status == 200 else "unreviewed_or_unavailable"
        pages[name] = {"status": int(status), "source_class": kind}
    known = all(p["source_class"] != "unreviewed_or_unavailable"
                for p in pages.values())
    return {
        "schema": "mojprop.public.static.source.readonly.c155.v1",
        "pages": pages,
        "both_live_pages_exact_known_source": known,
        "no_redirect": True,
        "no_post_no_customer_data_no_payment_no_release": True,
        "source_only_not_db_restore": True,
        "paid_challenge_available": False,
        "live_consent_or_receipt_verified": False,
    }


def main():
    report = inspect()
    print("MOJPROP_C155_PUBLIC_STATIC_SOURCE_READONLY=" +
          json.dumps(report, sort_keys=True, separators=(",", ":")))
    if not report["both_live_pages_exact_known_source"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
