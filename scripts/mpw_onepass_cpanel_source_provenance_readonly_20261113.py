#!/usr/bin/env python3
"""Bounded, source-only cPanel release provenance. NEVER edits or imports the app.

Run via the *existing authorized cPanel read-only SSH route*, using Python -B.
This script does not query SQL, render Django, access orders, or contact payment
networks. Its result CANNOT certify commercial readiness or a live template
origin: it only identifies source-drift and safe next reconciliation steps.
"""
from __future__ import annotations

import ast
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
    """Inspect *usable* buyer-email controls in a real POST form on disk.

    A visible string, autocomplete label, detached input, textarea, select,
    disabled field, or GET form is not proof a guest can submit an email.
    This remains static source evidence, NEVER live checkout attestation.
    """

    _EMAIL_NAMES = frozenset({
        "email", "buyer_email", "customer_email", "purchase_email",
        "purchaser_email",
    })
    _VOID_TAGS = frozenset({
        "area", "base", "br", "col", "embed", "hr", "img", "input",
        "link", "meta", "param", "source", "track", "wbr",
    })
    _ACTION_RE = re.compile(r"/commerce/trx-easy/start/[1-9][0-9]{0,9}/\Z")
    _CONTROL_OVERRIDES = frozenset({
        "form", "formaction", "formmethod", "formenctype", "formtarget",
        "formnovalidate",
    })

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.email_controls = 0
        self.email_hints = 0
        self.forms = 0
        self.post_forms = 0
        self.rejection_codes = set()
        self._scopes = []
        self._form = None

    @staticmethod
    def _attributes(attrs):
        names = [key.lower() for key, _ in attrs if key]
        values = {key.lower(): (value or "").strip() for key, value in attrs if key}
        return names, values

    @staticmethod
    def _inert(tag, values):
        style = re.sub(r"\s+", "", values.get("style", "").lower())
        return (
            "hidden" in values or "inert" in values
            or values.get("aria-hidden", "").lower() == "true"
            or values.get("aria-disabled", "").lower() == "true"
            or "display:none" in style or "visibility:hidden" in style
            or "content-visibility:hidden" in style
            or "opacity:0" in style or "pointer-events:none" in style
            or (tag == "fieldset" and "disabled" in values)
            or tag == "template"
            or (tag in ("details", "dialog") and "open" not in values)
        )

    def handle_starttag(self, tag, attrs):
        names, values = self._attributes(attrs)
        inert = (bool(self._scopes and self._scopes[-1][1])
                 or self._inert(tag, values))
        if tag not in self._VOID_TAGS:
            self._scopes.append((tag, inert))
        if tag == "form":
            self.forms += 1
            method = values.get("method", "get").lower()
            if method == "post":
                self.post_forms += 1
            if self._form is not None:
                self.rejection_codes.add("nested_form")
            valid_form = (
                method == "post"
                and self._ACTION_RE.fullmatch(values.get("action", "")) is not None
                and names.count("method") == 1
                and names.count("action") == 1
                and "target" not in values and "novalidate" not in values
                and values.get("enctype", "application/x-www-form-urlencoded").lower()
                    == "application/x-www-form-urlencoded"
                and values.get("accept-charset", "utf-8").lower() == "utf-8"
                and not inert
            )
            self._form = {"valid": valid_form, "candidates": 0}
            if not valid_form:
                self.rejection_codes.add("not_usable_post_form")
            return
        if tag not in ("input", "textarea", "select"):
            return
        field = values.get("name", "").lower()
        kind = values.get("type", "text").lower()
        hint = (
            field in self._EMAIL_NAMES or kind == "email"
            or "email" in values.get("id", "").lower()
            or values.get("autocomplete", "").lower() == "email"
        )
        if not hint:
            return
        self.email_hints += 1
        if self._form is None or not self._form["valid"]:
            self.rejection_codes.add("email_not_in_usable_post_form")
            return
        duplicate = any(names.count(a) != 1 for a in ("name", "type"))
        duplicate = duplicate or any(names.count(a) > 1 for a in (
            "required", "disabled", "readonly", "maxlength", "minlength",
            "pattern", "autocomplete", "style", "hidden",
        ))
        blocked = (
            tag != "input" or field not in self._EMAIL_NAMES
            or kind != "email" or "required" not in values
            or "disabled" in values or "readonly" in values
            or "multiple" in values or "pattern" in values
            or values.get("inputmode", "").lower() == "none"
            or inert or duplicate
            or any(name in self._CONTROL_OVERRIDES for name in names)
        )
        try:
            if "maxlength" in values and not 6 <= int(values["maxlength"]) <= 254:
                blocked = True
            if "minlength" in values and not 0 <= int(values["minlength"]) <= 254:
                blocked = True
            if ("maxlength" in values and "minlength" in values
                    and int(values["minlength"]) > int(values["maxlength"])):
                blocked = True
        except (ValueError, TypeError):
            blocked = True
        if blocked:
            self.rejection_codes.add("email_control_inert_or_invalid")
        else:
            self._form["candidates"] += 1

    def handle_endtag(self, tag):
        if tag == "form":
            if self._form is not None:
                if self._form["valid"]:
                    self.email_controls += self._form["candidates"]
                self._form = None
            else:
                self.rejection_codes.add("orphan_form_end")
        for i in range(len(self._scopes) - 1, -1, -1):
            if self._scopes[i][0] == tag:
                del self._scopes[i:]
                break

    def close(self):
        super().close()
        if self._form is not None:
            self.rejection_codes.add("unclosed_form")
            self._form = None


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


def classify_wsgi_stage_assignment(raw, app: Path) -> str:
    """Classify top-level literal APP assignment without importing WSGI.

    Source comments, string decoys, dynamic expressions, multiple bindings and
    syntax errors cannot attest the actual loaded Passenger application.
    Returns fixed categories only; no paths or source content are disclosed.
    """
    if raw is None:
        return "wsgi_missing_or_unsafe"
    try:
        module = ast.parse(raw.decode("utf-8"))
    except (UnicodeError, SyntaxError, ValueError):
        return "wsgi_unparseable"
    bindings = []
    for statement in module.body:
        if isinstance(statement, ast.Assign):
            if any(isinstance(target, ast.Name) and target.id == "APP"
                   for target in statement.targets):
                bindings.append(statement.value)
        elif isinstance(statement, ast.AnnAssign):
            if isinstance(statement.target, ast.Name) and statement.target.id == "APP":
                bindings.append(statement.value)
        elif isinstance(statement, ast.AugAssign):
            if isinstance(statement.target, ast.Name) and statement.target.id == "APP":
                bindings.append(statement.value)
    if not bindings:
        return "wsgi_app_assignment_absent"
    if len(bindings) != 1:
        return "wsgi_app_assignment_ambiguous"
    value = bindings[0]
    if not isinstance(value, ast.Constant) or not isinstance(value.value, str):
        return "wsgi_app_assignment_dynamic"
    return ("wsgi_expected_stage_literal_on_disk"
            if value.value == str(app) else "wsgi_other_app_literal_on_disk")


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
    guest_class = ("email_free_candidate_blocked_by_owner_policy" if guest_hash == APPROVED_GUEST_SHA256
                   else "reviewed_legacy_source" if guest_hash in REVIEWED_LEGACY_SHA256
                   else "source_unknown" if guest is not None else "source_missing_or_unsafe")
    # These are disk-source observations, not proof of Django's effective
    # template selection (which needs a separate owner-gated loader probe).
    template_state = "missing_or_unsafe"
    template_forms = None
    template_post_forms = None
    template_email_hints = None
    template_email_valid_controls = None
    template_email_rejections = []
    legacy_label_only = False
    if template is not None:
        try:
            inspector = StaticCheckoutControlInspector()
            inspector.feed(template.decode("utf-8"))
            inspector.close()
            template_forms = min(inspector.forms, 100)
            template_post_forms = min(inspector.post_forms, 100)
            template_email_hints = min(inspector.email_hints, 100)
            template_email_valid_controls = min(inspector.email_controls, 100)
            template_email_rejections = sorted(inspector.rejection_codes)[:20]
            legacy_label_only = (
                b"mpw-buy-email" in template.lower()
                and inspector.email_controls == 0
            )
            template_state = (
                "email_source_ambiguous" if inspector.email_controls and inspector.rejection_codes
                else "email_field_present" if inspector.email_controls
                else "email_not_found_static_source"
            )
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
    wsgi_class = classify_wsgi_stage_assignment(wsgi, app)
    wsgi_staging = wsgi_class == "wsgi_expected_stage_literal_on_disk"
    result = {
        "schema": "mpw.cpanel.source_provenance.readonly.v1",
        "guest_source": guest_class,
        "guest_sha256_prefix": guest_hash[:16] if guest else None,
        "template_disk_source": template_state,
        "template_forms_count_capped": template_forms,
        "template_post_forms_count_capped": template_post_forms,
        "template_email_hints_count_capped": template_email_hints,
        "template_usable_email_controls_count_capped": template_email_valid_controls,
        "template_email_rejections": template_email_rejections,
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
        "wsgi_app_assignment_source": wsgi_class,
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
