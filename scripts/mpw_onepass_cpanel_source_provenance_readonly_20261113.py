#!/usr/bin/env python3
"""Bounded, source-only cPanel release provenance. NEVER edits or imports the app.

Run via the *existing authorized cPanel read-only SSH route*, using Python -B.
This script does not query SQL, render Django, access orders, or contact payment
networks. Its result CANNOT certify commercial readiness or a live template
origin: it only identifies source-drift and safe next reconciliation steps.
"""
from __future__ import annotations

import hashlib
import json
import os
import pwd
import re
import stat
from html.parser import HTMLParser
from pathlib import Path

HOME = Path("/home/zomorod2")
APP = HOME / "Saeit-staging"
PUBLIC = HOME / "mojplaywin.com"
APPROVED_GUEST_SHA256 = "38765d8d248f4520242f4e1ead5a44c939795ca2e35b05aa3899971a152fe543"
REVIEWED_LEGACY_SHA256 = frozenset({
    "ef74a3ed84686e0c171f628932c2015338328ef93213e106834c2add7cdb1b2e",
    "6258de790fa95c774d847a6f3bf0cb170e69ebeccf1130a4b0b88be0bf55adc4",
})
FALLBACK_BLOCK = (
    b"# MPW_STATIC_STORE_FALLBACK_V1\n"
    b"RewriteEngine On\n"
    b"RewriteCond %{REQUEST_METHOD} ^GET$\n"
    b"RewriteCond %{REQUEST_URI} ^/store/?$\n"
    b"RewriteRule ^store/?$ store/index.html [END]\n\n"
)


def _safe_read(root: Path, relative: str, limit: int = 240_000):
    """Allow only regular bounded files below a non-symlink root."""
    if not root.is_dir() or root.is_symlink():
        return None
    dest = root / relative
    part = dest
    while part != root:
        if part.is_symlink():
            return None
        part = part.parent
    try:
        st = dest.stat()
        if not stat.S_ISREG(st.st_mode) or not 0 < st.st_size <= limit:
            return None
        raw = dest.read_bytes()
        if len(raw) != st.st_size:
            return None
        return raw
    except (OSError, ValueError):
        return None


class StaticCheckoutControlInspector(HTMLParser):
    """Classify actual input/select/textarea tags, not CSS or HTML comments.

    This is deliberately *not* a Django template renderer and gives no
    assurance about the effective runtime template or purchase behavior.
    """

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.email_controls = 0
        self.forms = 0
        self.post_forms = 0

    def handle_starttag(self, tag, attrs):
        values = {name.lower(): (value or "").strip().lower()
                  for name, value in attrs if name}
        if tag == "form":
            self.forms += 1
            if values.get("method") == "post":
                self.post_forms += 1
        if tag in ("input", "textarea", "select"):
            if any("email" in values.get(key, "") for key in
                   ("name", "id", "type", "autocomplete")):
                self.email_controls += 1



def classify_apache_passenger_directives(raw, public: Path, app: Path) -> str:
    """Classify only on-disk Apache directives; never infer effective routing.

    Returned values are fixed categories, not roots or host configuration.
    Passenger UAPI, rewrite precedence and the live Django loader remain
    separately unverified even for an exact public-root match.
    """
    if raw is None:
        return "htaccess_missing_or_unsafe"
    try:
        lines = raw.decode("utf-8").splitlines()
    except UnicodeError:
        return "htaccess_unreadable"
    directives = {"passengerapproot": [], "passengerbaseuri": [],
                  "passengerenabled": []}
    pattern = re.compile(
        r"""\s*(PassengerAppRoot|PassengerBaseURI|PassengerEnabled)\s+("[^"]+"|'[^']+'|[^\s#'"]+)\s*(?:#.*)?$""",
        re.IGNORECASE,
    )
    for line in lines:
        stripped = line.lstrip()
        if stripped.startswith("#"):
            continue
        if not re.match(r"\s*Passenger(?:AppRoot|BaseURI|Enabled)\b",
                        line, re.IGNORECASE):
            continue
        match = pattern.fullmatch(line)
        if match is None:
            return "ambiguous_directives"
        key = match.group(1).lower()
        token = match.group(2)
        value = token[1:-1] if token[:1] in ("'", '"') else token
        directives[key].append(value.strip())
        if len(directives[key]) > 1:
            return "ambiguous_directives"
    enabled = directives["passengerenabled"]
    if enabled:
        if enabled[0].lower() in ("off", "false", "0"):
            return "passenger_disabled_on_disk"
        if enabled[0].lower() not in ("on", "true", "1"):
            return "ambiguous_directives"
    roots = directives["passengerapproot"]
    if not roots:
        return "app_root_not_declared"
    base = directives["passengerbaseuri"]
    if not base:
        return "base_uri_not_declared"
    if base[0] != "/":
        return "base_uri_not_slash"
    root = roots[0].rstrip("/")
    if root == str(public).rstrip("/"):
        return "public_root_slash_directives_on_disk"
    if root == str(app).rstrip("/"):
        return "staging_root_slash_directives_on_disk"
    return "other_root_slash_directives_on_disk"

def inspect(app: Path = APP, public: Path = PUBLIC) -> dict:
    """Use explicit roots in isolated tests; never expose raw file contents."""
    guest = _safe_read(app, "services/mpw_trx_guest_commerce.py")
    template = _safe_read(app, "mpw_commerce/templates/mpw_commerce/product_checkout.html")
    htaccess = _safe_read(public, ".htaccess")
    wsgi = _safe_read(public, "passenger_wsgi.py")
    store_html = _safe_read(public, "store/index.html")
    store_view = _safe_read(app, "core/mojplaywin_views.py")
    checkout_view = _safe_read(app, "mpw_commerce/product_checkout_page.py")
    guest_hash = hashlib.sha256(guest).hexdigest() if guest else ""
    guest_class = ("approved_email_free_source" if guest_hash == APPROVED_GUEST_SHA256
                   else "reviewed_legacy_source" if guest_hash in REVIEWED_LEGACY_SHA256
                   else "source_unknown" if guest is not None else "source_missing_or_unsafe")
    # These are disk-source observations, not proof of Django's effective
    # template selection (which needs a separate owner-gated loader probe).
    template_state = "missing_or_unsafe"
    template_forms = None
    template_post_forms = None
    legacy_label_only = False
    if template is not None:
        try:
            inspector = StaticCheckoutControlInspector()
            inspector.feed(template.decode("utf-8"))
            inspector.close()
            template_forms = min(inspector.forms, 100)
            template_post_forms = min(inspector.post_forms, 100)
            legacy_label_only = (
                b"mpw-buy-email" in template.lower()
                and inspector.email_controls == 0
            )
            template_state = ("email_field_present" if inspector.email_controls
                              else "email_not_found_static_source")
        except (UnicodeError, ValueError):
            template_state = "unreadable_static_source"
    # Presence on disk does not establish the effective Apache or Passenger
    # routing. Accept the exact *leading* owned rule only, never a duplicate
    # or text merely embedded lower in the file.
    fallback = "unknown"
    if htaccess is not None and store_html is not None:
        fallback = ("owned_static_fallback_rule_on_disk" if
                    htaccess.startswith(FALLBACK_BLOCK) and
                    htaccess.count(FALLBACK_BLOCK) == 1 and
                    b"MPW_STATIC_STORE_FALLBACK_V1" in store_html
                    else "fallback_not_exactly_proven")
    wsgi_staging = (wsgi is not None and
                    b"APP='/home/zomorod2/Saeit-staging'" in wsgi)
    result = {
        "schema": "mpw.cpanel.source_provenance.readonly.v1",
        "guest_source": guest_class,
        "guest_sha256_prefix": guest_hash[:16] if guest else None,
        "template_disk_source": template_state,
        "template_forms_count_capped": template_forms,
        "template_post_forms_count_capped": template_post_forms,
        "template_legacy_email_label_without_control": legacy_label_only,
        "effective_django_template_origin_verified": False,
        "store_view_source_regular": store_view is not None,
        "store_view_sha256_prefix": (hashlib.sha256(store_view).hexdigest()[:16]
                                     if store_view else None),
        "store_view_source_function_marker": (
            store_view is not None and b"def store(request):" in store_view),
        "checkout_view_source_regular": checkout_view is not None,
        "checkout_view_sha256_prefix": (
            hashlib.sha256(checkout_view).hexdigest()[:16]
            if checkout_view else None),
        "checkout_view_explicit_script_src_source_marker": (
            checkout_view is not None and b"script-src" in checkout_view),
        "effective_checkout_view_import_verified": False,
        "public_fallback": fallback,
        "apache_passenger_directive_source": classify_apache_passenger_directives(htaccess, public, app),
        "passenger_stage_source_marker": wsgi_staging,
        "private_checkout_source_readable": template is not None,
        "production_invoice_post_verified": False,
        "independent_chain_finality_verified": False,
        "authenticated_delivery_verified": False,
        "confirmed_revenue": None,
        "customer_data_read": False,
        "database_accessed": False,
        "external_network_requests": False,
        "files_modified": False,
        "production_release_permitted_by_this_report": False,
    }
    return result


def main():
    if pwd.getpwuid(os.geteuid()).pw_name != "zomorod2":
        raise SystemExit("MPW_CPANEL_SOURCE_PROVENANCE=WRONG_ACCOUNT")
    report = inspect()
    print("MPW_CPANEL_SOURCE_PROVENANCE=" + json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
