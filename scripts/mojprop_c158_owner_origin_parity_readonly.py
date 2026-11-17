#!/usr/bin/env python3
"""C158: independently compare two public GET responses to two exact on-disk files.

Run ONLY on owner cPanel over pinned SSH. No POST, cookies, redirects, writes,
secret access, raw HTML output, digest output, customer data or release grants.
Classification of public content is diagnostic, never a source approval.
"""
from __future__ import annotations

from html.parser import HTMLParser
import hmac
import json
import os
from pathlib import Path
import stat
import urllib.error
import urllib.request

ROOT = Path("/home/zomorod2/mojplaywin.com/moj-prop")
FILES = {
    "home": ("index.html", "https://mojplaywin.com/moj-prop/"),
    "contact": ("contact/index.html", "https://mojplaywin.com/moj-prop/contact/"),
}
MAX_BYTES = 196608
TIMEOUT = 12


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class Links(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.hrefs = []
        self.actions = []

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if tag == "a" and values.get("href"):
            self.hrefs.append(values["href"].strip())
        elif tag == "form":
            self.actions.append((values.get("action") or "").strip())


def _trusted_dir(p: Path, uid: int) -> bool:
    try:
        st = p.lstat()
        return (stat.S_ISDIR(st.st_mode) and not stat.S_ISLNK(st.st_mode)
                and st.st_uid == uid and not st.st_mode & 0o002)
    except OSError:
        return False


def disk_bytes(root: Path, name: str, uid: int | None = None) -> tuple[str, bytes]:
    if name not in FILES:
        raise ValueError("unknown page")
    uid = os.geteuid() if uid is None else uid
    if (not root.is_absolute() or not _trusted_dir(root, uid)
            or not _trusted_dir(root.parent, uid)):
        return "unsafe_root", b""
    rel = Path(FILES[name][0])
    path = root / rel
    if not _trusted_dir(path.parent, uid):
        return "unsafe_parent", b""
    try:
        before = path.lstat()
        if not (stat.S_ISREG(before.st_mode) and before.st_uid == uid
                and before.st_nlink == 1 and not before.st_mode & 0o022
                and 0 < before.st_size <= MAX_BYTES):
            return "unsafe_file", b""
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
        try:
            initial = os.fstat(fd)
            if (initial.st_dev, initial.st_ino, initial.st_size, initial.st_mtime_ns) != (
                    before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns):
                return "concurrent_change", b""
            with os.fdopen(fd, "rb", closefd=False) as f:
                data = f.read(MAX_BYTES + 1)
            after = os.fstat(fd)
            if (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns) != (
                    before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns):
                return "concurrent_change", b""
            if len(data) != before.st_size:
                return "concurrent_change", b""
            return "readable", data
        finally:
            os.close(fd)
    except FileNotFoundError:
        return "missing", b""
    except (OSError, ValueError):
        return "unreadable_or_race", b""


def public_get(url: str) -> tuple[int, bytes]:
    if url not in (v[1] for v in FILES.values()):
        raise ValueError("unapproved url")
    opener = urllib.request.build_opener(NoRedirect)
    req = urllib.request.Request(
        url, method="GET",
        headers={"User-Agent": "MOJPROP-C158-readonly/1",
                 "Accept-Encoding": "identity", "Accept": "text/html"}
    )
    try:
        with opener.open(req, timeout=TIMEOUT) as response:
            code = response.getcode()
            if code != 200 or response.geturl() != url:
                return int(code), b""
            length = response.headers.get("Content-Length")
            if length is not None and (not length.isascii()
                                       or not length.isdecimal()
                                       or int(length) > MAX_BYTES):
                return code, b""
            raw = response.read(MAX_BYTES + 1)
            return code, raw if len(raw) <= MAX_BYTES else b""
    except urllib.error.HTTPError as e:
        return int(e.code), b""
    except (urllib.error.URLError, TimeoutError, OSError, ValueError):
        return 0, b""


def semantic_flags(raw: bytes) -> dict[str, bool]:
    # Hardcoded booleans; no invented availability, receipt or legal validity.
    text = raw.decode("utf-8", "replace")
    parser = Links()
    parser.feed(text)
    return {
        "funded_plan1_sku_marked": "MOJ-PROP-01" in text,
        "educational_starter30_sku_marked": "MOJPROP-STARTER30" in text,
        "prelaunch_word_present": "prelaunch" in text.lower(),
        "known_unavailable_consent_link": any(
            url.startswith("/moj-prop-interest/form/") for url in parser.hrefs
        ),
        "official_support_mailto_present": any(
            url.lower().startswith("mailto:support@mojplaywin.com")
            for url in parser.hrefs
        ),
        "generic_service_form_action": any(
            url.startswith("/moj-prop-intake/") for url in parser.actions
        ),
        "checkout_link_present": any(
            url.startswith("/checkout/") or url.startswith("/moj-prop/pay/")
            for url in parser.hrefs
        ),
    }


class Shape(HTMLParser):
    """Fixed counters only. Never emit element attributes, text, URL or title."""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tags = {}
        self.skip_depth = 0
        self.visible_char_count = 0
        self.external_script = False
        self.meta_refresh = False

    def handle_starttag(self, tag, attrs):
        self.tags[tag] = self.tags.get(tag, 0) + 1
        values = dict(attrs)
        if tag in ("script", "style"):
            self.skip_depth += 1
            if tag == "script" and values.get("src"):
                self.external_script = True
        if tag == "meta" and (values.get("http-equiv") or "").lower() == "refresh":
            self.meta_refresh = True

    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            self.skip_depth = max(0, self.skip_depth - 1)

    def handle_data(self, data):
        if self.skip_depth == 0:
            self.visible_char_count += len(data.strip())


def _band(value: int) -> str:
    if value == 0:
        return "none"
    if value < 2048:
        return "tiny"
    if value < 8192:
        return "small"
    if value < 32768:
        return "medium"
    if value < 98304:
        return "large"
    return "very_large"


def structural_flags(raw: bytes) -> dict:
    """Privacy-preserving indicator of a real content page versus loader shell.

    These are structural hints only, not content approval or legal compliance.
    """
    text = raw.decode("utf-8", "replace")
    parser = Shape()
    parser.feed(text)
    lower = text.lower()
    return {
        "byte_band": _band(len(raw)),
        "visible_text_band": _band(parser.visible_char_count),
        "doctype_html": raw.lstrip().lower().startswith(b"<!doctype html"),
        "html_element": bool(parser.tags.get("html")),
        "body_element": bool(parser.tags.get("body")),
        "title_element": bool(parser.tags.get("title")),
        "script_element": bool(parser.tags.get("script")),
        "external_script": parser.external_script,
        "iframe_element": bool(parser.tags.get("iframe")),
        "form_element": bool(parser.tags.get("form")),
        "anchor_element": bool(parser.tags.get("a")),
        "meta_refresh": parser.meta_refresh,
        "javascript_location_navigation": (
            "location.href" in lower or "location.replace" in lower
            or "location.assign" in lower
        ),
    }


def inspect(root: Path = ROOT, getter=public_get, uid: int | None = None) -> dict:
    pages = {}
    for name, (_, url) in FILES.items():
        state, disk = disk_bytes(root, name, uid)
        try:
            code, external = getter(url)
        except (OSError, ValueError, TimeoutError):
            code, external = 0, b""
        parity = "unavailable"
        if state == "readable" and code == 200 and 0 < len(external) <= MAX_BYTES:
            parity = ("exact_match" if hmac.compare_digest(disk, external)
                      else "different_bytes")
        pages[name] = {
            "disk_status": state,
            "http_status": int(code),
            "http_vs_disk": parity,
            "disk_flags": semantic_flags(disk) if state == "readable" else None,
            "disk_shape": structural_flags(disk) if state == "readable" else None,
        }
    return {
        "schema": "mojprop.cpanel.public_origin_parity.readonly.c158.v1",
        "pages": pages,
        "all_public_pages_exact_disk": all(
            page["http_vs_disk"] == "exact_match" for page in pages.values()
        ),
        "read_only": True,
        "no_customer_data_or_credentials_read": True,
        "no_raw_html_paths_or_hashes_logged": True,
        "no_post_no_payment_no_email_no_release": True,
        "not_full_db_app_media_restore_proof": True,
        "commercial_readiness_verified": False,
    }


def main():
    report = inspect()
    print("MOJPROP_C158_OWNER_ORIGIN_PARITY_READONLY=" +
          json.dumps(report, sort_keys=True, separators=(",", ":")))


if __name__ == "__main__":
    main()
