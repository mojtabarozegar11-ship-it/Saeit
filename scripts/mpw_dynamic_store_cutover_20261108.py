#!/usr/bin/env python3
"""Owner-gated, reversible cutover from the owned static /store/ fallback.

Touches only the exact fallback rule, its one-file directory, and the already
present Passenger restart marker. Never changes invoices, payments or mail.
"""
from __future__ import annotations

import ast
import hashlib
import json
import os
import pwd
import re
import stat
import sys
import tempfile
import time
import urllib.error
import urllib.request
from html.parser import HTMLParser
from pathlib import Path


HOME = Path("/home/zomorod2")
PUBLIC = HOME / "mojplaywin.com"
APP = HOME / "Saeit-staging"
BACKUP_BASE = HOME / ".backups/mpw-store-dynamic-cutover"
FALLBACK_BLOCK = (
    b"# MPW_STATIC_STORE_FALLBACK_V1\n"
    b"RewriteEngine On\n"
    b"RewriteCond %{REQUEST_METHOD} ^GET$\n"
    b"RewriteCond %{REQUEST_URI} ^/store/?$\n"
    b"RewriteRule ^store/?$ store/index.html [END]\n\n"
)
MARKER = b"MPW_STATIC_STORE_FALLBACK_V1"
PRODUCT_ROUTES = (
    b"/store/product/72/checkout/",
    b"/store/product/225/checkout/",
    b"/store/product/879/",
)
BUYER_ROUTE_PROBES = (
    ("/store/product/72/", b"The Science and Practice of Chess Improvement", b"Buy securely with native TRX"),
    ("/store/product/225/", b"Taniya and the Little Baker Worms", b"Buy securely with native TRX"),
    ("/store/product/879/", b"Atelier Interior", b"Buy securely with native TRX"),
    ("/store/product/72/checkout/", b"The Science and Practice of Chess Improvement", b"Create my TRX payment invoice"),
    ("/store/product/225/checkout/", b"Taniya and the Little Baker Worms", b"Create my TRX payment invoice"),
    ("/store/product/879/checkout/", b"Atelier Interior", b"Create my TRX payment invoice"),
    ("/commerce/book/72/", b"The Science and Practice of Chess Improvement", b"Create my TRX payment invoice"),
    ("/commerce/book/225/", b"Taniya and the Little Baker Worms", b"Create my TRX payment invoice"),
    ("/commerce/book/879/", b"Atelier Interior", b"Create my TRX payment invoice"),
)
# The owner-gated relay has a 150-second outer SSH timeout. Keep the complete
# mutable interval well below it so Python, not the relay, controls rollback.
BUYER_ROUTE_TOTAL_SECONDS = 25
PREFLIGHT_BUDGET_SECONDS = 40


def atomic_replace(target: Path, content: bytes, mode: int) -> None:
    fd, tmp = tempfile.mkstemp(prefix=".mpw-store-cutover-", dir=str(target.parent))
    try:
        with os.fdopen(fd, "wb") as out:
            out.write(content)
            out.flush()
            os.fsync(out.fileno())
        os.chmod(tmp, mode)
        os.replace(tmp, target)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def inspect_owned_fallback(public: Path) -> tuple[bytes, bytes, int]:
    """Require one exact owned rule and only one marker-bearing index file."""
    ht = public / ".htaccess"
    store = public / "store"
    index = store / "index.html"
    marker = public / "tmp/restart.txt"
    if (public.is_symlink() or not public.is_dir() or ht.is_symlink() or
            not ht.is_file() or store.is_symlink() or not store.is_dir() or
            index.is_symlink() or not index.is_file() or marker.is_symlink() or
            not marker.is_file()):
        raise RuntimeError("UNSAFE_PUBLIC_STORE_FILES")
    if any(p.stat().st_uid != os.geteuid() for p in (public, ht, store, index, marker)):
        raise RuntimeError("UNEXPECTED_FILE_OWNER")
    files = list(store.iterdir())
    if len(files) != 1 or files[0].name != "index.html":
        raise RuntimeError("UNOWNED_STORE_DIRECTORY_CONTENTS")
    if index.stat().st_size > 200_000 or ht.stat().st_size > 128_000:
        raise RuntimeError("FALLBACK_FILE_SIZE_REFUSED")
    data = index.read_bytes()
    conf = ht.read_bytes()
    if (MARKER not in data or conf.count(FALLBACK_BLOCK) != 1 or
            conf.count(MARKER) != 1):
        raise RuntimeError("FALLBACK_ANCHOR_DRIFT_REFUSED")
    changed = conf.replace(FALLBACK_BLOCK, b"", 1)
    if not changed or MARKER in changed:
        raise RuntimeError("FALLBACK_REPLACEMENT_INVALID")
    return conf, changed, stat.S_IMODE(ht.stat().st_mode)


def verify_guarded_store_source(source: bytes) -> None:
    """Accept source drift only when the actual fail-open storefront contract holds.

    Optional funnel instrumentation may exist, yet have no installed model/table.
    A fixed file length or an absent funnel module is not evidence of safety.
    Instead require that the recorder call is inside a broad, non-raising handler;
    the live Django render and public HTTPS check remain mandatory afterward.
    """
    if len(source) < 200 or len(source) > 64_000:
        raise RuntimeError("STAGING_VIEW_SOURCE_SIZE_REFUSED")
    try:
        tree = ast.parse(source.decode("utf-8"), filename="core/mojplaywin_views.py")
    except (UnicodeDecodeError, SyntaxError) as exc:
        raise RuntimeError("STAGING_VIEW_SOURCE_INVALID") from exc
    views = [node for node in tree.body if isinstance(node, ast.FunctionDef)
             and node.name == "store" and len(node.args.args) == 1
             and node.args.args[0].arg == "request"]
    if len(views) != 1:
        raise RuntimeError("STAGING_GUARDED_VIEW_NOT_PROVEN")
    view = views[0]
    guarded = [node for node in view.body if isinstance(node, ast.Try)
               and any(isinstance(handler.type, ast.Name)
                       and handler.type.id == "Exception" and handler.body
                       and not any(isinstance(item, ast.Raise)
                                   for item in ast.walk(handler))
                       for handler in node.handlers)]
    safe_recorder = any(
        any(isinstance(node, ast.ImportFrom) and node.level == 1
            and node.module == "commerce_funnel"
            and any(alias.name == "record_funnel_event" for alias in node.names)
            for child in guarded_try.body for node in ast.walk(child))
        and any(isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                and node.func.id == "record_funnel_event"
                for child in guarded_try.body for node in ast.walk(child))
        for guarded_try in guarded
    )
    store_render = any(
        isinstance(node, ast.Return) and isinstance(node.value, ast.Call)
        and isinstance(node.value.func, ast.Name) and node.value.func.id == "render"
        and len(node.value.args) >= 2
        and isinstance(node.value.args[1], ast.Constant)
        and node.value.args[1].value == "mojplaywin/store.html"
        for node in view.body
    )
    if not safe_recorder or not store_render:
        raise RuntimeError("STAGING_GUARDED_VIEW_NOT_PROVEN")


def verify_guest_email_ownership_source(source: bytes) -> None:
    """Require the staged checkout adapter to enforce buyer-email ownership.

    A required email input in the public HTML does not prove that the invoice
    handler validates and persists its owner. This structural gate does not
    create an invoice, send email, or claim a completed paid delivery.
    """
    if not 500 < len(source) < 100_000:
        raise RuntimeError("STAGING_GUEST_OWNER_SOURCE_INVALID")
    try:
        tree = ast.parse(source.decode("utf-8"), filename="services/mpw_trx_guest_commerce.py")
    except (UnicodeDecodeError, SyntaxError) as exc:
        raise RuntimeError("STAGING_GUEST_OWNER_SOURCE_INVALID") from exc
    functions = {
        name: [node for node in tree.body if isinstance(node, ast.FunctionDef)
               and node.name == name]
        for name in ("_new_user", "_dispatch")
    }
    if any(len(nodes) != 1 for nodes in functions.values()):
        raise RuntimeError("STAGING_GUEST_EMAIL_OWNERSHIP_NOT_PROVEN")
    new_user = functions["_new_user"][0]
    dispatch = functions["_dispatch"][0]

    def calls(node, function_name):
        return any(isinstance(item, ast.Call) and isinstance(item.func, ast.Name)
                   and item.func.id == function_name for item in ast.walk(node))

    def imports_from_recovery(node, function_name):
        return any(
            isinstance(item, ast.ImportFrom)
            and item.level == 0 and item.module == "services.mpw_trx_email_recovery"
            and any(alias.name == function_name and alias.asname in (None, function_name)
                    for alias in item.names)
            for item in ast.walk(node)
        )

    # New guests need an address persisted on their authenticated principal;
    # existing and new guests both require a durable per-order email claim.
    persists_email = any(
        isinstance(item, ast.Assign)
        and any(isinstance(target, ast.Attribute) and target.attr == "email"
                for target in item.targets)
        for item in ast.walk(new_user)
    )
    saves_email = any(
        isinstance(item, ast.Call) and isinstance(item.func, ast.Attribute)
        and item.func.attr == "save"
        and any(keyword.arg == "update_fields" and isinstance(keyword.value, (ast.List, ast.Tuple))
                and any(isinstance(field, ast.Constant) and field.value == "email"
                        for field in keyword.value.elts)
                for keyword in item.keywords)
        for item in ast.walk(new_user)
    )
    if not (imports_from_recovery(tree, "_posted_email")
            and imports_from_recovery(tree, "bound_checkout")
            and calls(new_user, "_posted_email") and persists_email
            and saves_email and calls(dispatch, "bound_checkout")):
        raise RuntimeError("STAGING_GUEST_EMAIL_OWNERSHIP_NOT_PROVEN")



def verify_guest_recovery_checkout_source(source: bytes) -> None:
    """Refuse a staged email-claim adapter without its checkout dependency.

    The public GET forms cannot exercise this module; a missing or stale
    recovery dependency otherwise breaks invoice POST after the store switch.
    This is a structural, read-only preflight, not a paid-order test.
    """
    if not 200 < len(source) < 120_000:
        raise RuntimeError("STAGING_GUEST_RECOVERY_SOURCE_INVALID")
    try:
        tree = ast.parse(source.decode("utf-8"), filename="services/mpw_trx_email_recovery.py")
    except (UnicodeDecodeError, SyntaxError) as exc:
        raise RuntimeError("STAGING_GUEST_RECOVERY_SOURCE_INVALID") from exc
    functions = {
        name: [item for item in tree.body if isinstance(item, ast.FunctionDef)
               and item.name == name]
        for name in ("_posted_email", "bound_checkout")
    }
    if any(len(nodes) != 1 for nodes in functions.values()):
        raise RuntimeError("STAGING_GUEST_RECOVERY_CHECKOUT_NOT_PROVEN")
    bound = functions["bound_checkout"][0]
    calls = [node.func for node in ast.walk(bound) if isinstance(node, ast.Call)]
    direct = {node.id for node in calls if isinstance(node, ast.Name)}
    attributes = {node.attr for node in calls if isinstance(node, ast.Attribute)}
    claim_create = any(
        isinstance(node, ast.Attribute) and node.attr == "create"
        and isinstance(node.value, ast.Attribute) and node.value.attr == "objects"
        and isinstance(node.value.value, ast.Name)
        and node.value.value.id == "GuestOrderEmail"
        for node in calls
    )
    atomic = any(
        isinstance(node, ast.Attribute) and node.attr == "atomic"
        and isinstance(node.value, ast.Name) and node.value.id == "transaction"
        for node in calls
    )
    import_claim = any(
        isinstance(node, ast.ImportFrom) and node.level == 0
        and node.module == "core.models"
        and any(alias.name == "GuestOrderEmail" for alias in node.names)
        for node in tree.body
    )
    if not (import_claim and "_posted_email" in direct and "_digest" in direct
            and claim_create and atomic and
            {"connect", "disconnect", "fullmatch"}.issubset(attributes)):
        raise RuntimeError("STAGING_GUEST_RECOVERY_CHECKOUT_NOT_PROVEN")


def verify_guest_order_claim_schema(guest_order_email_model, database_connection) -> None:
    """Read-only validation of the columns and one-order-one-claim DB constraint.

    Merely finding the table name is insufficient: an interrupted migration or
    an unrelated legacy table can lack the fields needed to bind an invoice to
    its buyer, or the unique order constraint that prevents duplicate claims.
    """
    table = guest_order_email_model._meta.db_table
    required = {field.column for field in guest_order_email_model._meta.concrete_fields}
    if not isinstance(table, str) or not table or "order_id" not in required:
        raise RuntimeError("STAGING_GUEST_ORDER_EMAIL_MODEL_INVALID")
    try:
        with database_connection.cursor() as cursor:
            introspection = database_connection.introspection
            names = introspection.table_names(cursor)
            if table in names:
                columns = {
                    item.name for item in introspection.get_table_description(cursor, table)
                }
                constraints = introspection.get_constraints(cursor, table)
    except Exception as exc:
        raise RuntimeError("STAGING_GUEST_ORDER_EMAIL_SCHEMA_UNKNOWN") from exc
    if table not in names:
        raise RuntimeError("STAGING_GUEST_ORDER_EMAIL_SCHEMA_MISSING")
    if not required.issubset(columns):
        raise RuntimeError("STAGING_GUEST_ORDER_EMAIL_COLUMNS_MISSING")
    if not any(
        details.get("unique") is True
        and tuple(details.get("columns") or ()) == ("order_id",)
        for details in constraints.values()
    ):
        raise RuntimeError("STAGING_GUEST_ORDER_EMAIL_UNIQUE_ORDER_MISSING")



def verify_email_free_guest_source(source: bytes) -> None:
    """Fail closed unless staged checkout uses signed guest sessions, not buyer email."""
    if not 500 < len(source) < 100_000:
        raise RuntimeError("STAGING_EMAIL_FREE_GUEST_SOURCE_INVALID")
    try:
        tree = ast.parse(source.decode("utf-8"), "services/mpw_trx_guest_commerce.py")
    except (SyntaxError, UnicodeDecodeError) as exc:
        raise RuntimeError("STAGING_EMAIL_FREE_GUEST_SOURCE_INVALID") from exc
    required_functions = ("_read_user", "_new_user", "_identity", "_dispatch",
                          "_install_cookie", "_checkout_page", "patch_commercial")
    functions = {
        name: [node for node in tree.body if isinstance(node, ast.FunctionDef)
               and node.name == name] for name in required_functions
    }
    if any(len(nodes) != 1 for nodes in functions.values()):
        raise RuntimeError("STAGING_EMAIL_FREE_IDENTITY_NOT_PROVEN")
    raw = source.decode("utf-8")
    required = ("signing.loads(", "signing.dumps(", "set_unusable_password(",
                "set_cookie(", "secure=True", "httponly=True", 'samesite="Lax"',
                "csrf_protect(", "require_POST", "rights_cleared_for_sale(",
                "_eligible(", "_configured_receiver(")
    forbidden = ("request.POST", "_posted_email", "bound_checkout",
                 "mpw_trx_email_recovery")
    if any(part not in raw for part in required) or any(part in raw for part in forbidden):
        raise RuntimeError("STAGING_EMAIL_FREE_IDENTITY_NOT_PROVEN")
    called = {n.func.id for n in ast.walk(functions["_dispatch"][0])
              if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
    if not {"_identity", "_install_cookie"}.issubset(called):
        raise RuntimeError("STAGING_EMAIL_FREE_DISPATCH_NOT_PROVEN")


def verify_email_free_invoice_sources(app: Path) -> None:
    """Read-only email-dependency scan; does not assert that paid invoices succeed."""
    files = ("services/mpw_trx_commercial_web.py",
             "services/mpw_trx_commercial_context.py",
             "mpw_commerce/buyer_orders.py")
    start_count = 0
    for rel in files:
        p = app / rel
        if p.is_symlink() or not p.is_file() or not 200 < p.stat().st_size <= 250_000:
            raise RuntimeError("STAGING_INVOICE_SOURCE_MISSING_OR_UNSAFE")
        try:
            tree = ast.parse(p.read_text("utf-8"), filename=rel)
        except (OSError, SyntaxError, UnicodeError) as exc:
            raise RuntimeError("STAGING_INVOICE_SOURCE_UNREADABLE") from exc
        funcs = {}
        imported_recorders = set()
        for n in tree.body:
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
                funcs.setdefault(n.name, []).append(n)
            elif isinstance(n, ast.ImportFrom):
                imported_recorders.update((a.asname or a.name) for a in n.names
                                          if a.name == "record_invoice")
        if rel.endswith("mpw_trx_commercial_web.py"):
            start_count = len(funcs.get("_start_order", ()))
        waiting = [n for n in ("_start_order", "record_invoice") if n in funcs]
        reviewed = set()
        while waiting:
            name = waiting.pop()
            if name in reviewed:
                continue
            reviewed.add(name)
            if len(funcs.get(name, ())) != 1:
                raise RuntimeError("STAGING_INVOICE_HELPER_AMBIGUOUS")
            for node in ast.walk(funcs[name][0]):
                if isinstance(node, ast.Name) and "email" in node.id.lower():
                    raise RuntimeError("STAGING_INVOICE_EMAIL_DEPENDENCY")
                if isinstance(node, ast.Attribute) and "email" in node.attr.lower():
                    raise RuntimeError("STAGING_INVOICE_EMAIL_DEPENDENCY")
                if isinstance(node, ast.Constant) and isinstance(node.value, str) and "email" in node.value.lower():
                    raise RuntimeError("STAGING_INVOICE_EMAIL_DEPENDENCY")
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                    if node.func.id in imported_recorders:
                        raise RuntimeError("STAGING_INVOICE_IMPORTED_RECORDER_UNVERIFIED")
                    if node.func.id in funcs and node.func.id not in reviewed:
                        waiting.append(node.func.id)
    if start_count != 1:
        raise RuntimeError("STAGING_INVOICE_HANDLER_MISSING")
    template = app / "mpw_commerce/templates/mpw_commerce/product_checkout.html"
    if template.is_symlink() or not template.is_file() or not 100 < template.stat().st_size <= 250_000:
        raise RuntimeError("STAGING_INVOICE_TEMPLATE_UNAVAILABLE")
    markup = template.read_bytes().lower()
    if (b'name="email"' in markup or b'type="email"' in markup or
            b"mpw-buy-email" in markup or
            not (b"csrf_token" in markup or b"csrfmiddlewaretoken" in markup)):
        raise RuntimeError("STAGING_INVOICE_TEMPLATE_REQUIRES_EMAIL_OR_LACKS_CSRF")


def verify_buyer_route_resolution(resolver):
    """Verify the actual Django URL table, not only a directly imported view.

    Rendering a function by hand is insufficient if /store/ still resolves to
    a different handler, or if the three catalogue checkout links are 404s.
    No request is submitted here, so no order, invoice or payment is created.
    """
    try:
        store_match = resolver("/store/")
        if (store_match.url_name != "store" or store_match.args or
                store_match.kwargs or not callable(store_match.func)):
            raise RuntimeError("STAGING_STORE_URL_NOT_RESOLVED")
        for product_id in (72, 225, 879):
            match = resolver(f"/store/product/{product_id}/checkout/")
            if (match.args or match.kwargs != {"product_id": product_id} or
                    not callable(match.func)):
                raise RuntimeError("STAGING_BUYER_CHECKOUT_ROUTE_INVALID")
            start_match = resolver(f"/commerce/trx-easy/start/{product_id}/")
            if (start_match.args or
                    start_match.kwargs != {"product_id": product_id} or
                    not callable(start_match.func)):
                raise RuntimeError("STAGING_INVOICE_START_ROUTE_INVALID")
    except RuntimeError:
        raise
    except Exception as exc:
        raise RuntimeError("STAGING_BUYER_ROUTE_UNAVAILABLE") from exc
    return store_match.func


def check_actual_staging_store() -> None:
    """Import and render the real store view; never supply a metrics stub."""
    target = APP / "core/mojplaywin_views.py"
    funnel = APP / "core/commerce_funnel.py"
    guest_adapter = APP / "services/mpw_trx_guest_commerce.py"
    if (APP.is_symlink() or not APP.is_dir() or target.is_symlink() or
            not target.is_file() or funnel.is_symlink() or
            (funnel.exists() and not funnel.is_file()) or
            guest_adapter.is_symlink() or not guest_adapter.is_file()):
        raise RuntimeError("STAGING_SOURCE_DRIFT")
    verify_guarded_store_source(target.read_bytes())
    verify_email_free_guest_source(guest_adapter.read_bytes())
    verify_email_free_invoice_sources(APP)
    os.environ["DJANGO_SETTINGS_MODULE"] = "config.settings"
    os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
    sys.dont_write_bytecode = True
    os.chdir(APP)
    sys.path.insert(0, str(APP))
    import django
    django.setup()
    from django.test import RequestFactory
    from django.urls import resolve
    from core import mojplaywin_views
    if Path(mojplaywin_views.__file__).resolve() != target.resolve():
        raise RuntimeError("STAGING_VIEW_IMPORT_ORIGIN_MISMATCH")
    store_callback = verify_buyer_route_resolution(resolve)
    factory = RequestFactory()
    page = store_callback(factory.get("/store/", secure=True, HTTP_HOST="mojplaywin.com"))
    if page.status_code != 200 or len(page.content) < 2000 or any(
            route not in page.content for route in PRODUCT_ROUTES):
        raise RuntimeError("REAL_STAGING_STORE_RENDER_FAILED")
    print("MPW_DYNAMIC_STAGING_GUARDED_RENDER=PASS;PRODUCTS=3")


def public_response(run_id: str) -> bytes:
    """Public HTTPS GET, cache-busted; no credentials, payment or mail."""
    url = "https://mojplaywin.com/store/?mpw_cutover_probe=" + run_id
    request = urllib.request.Request(url, headers={
        "User-Agent": "MojPlayWin-owner-cutover-smoke/1.0",
        "Cache-Control": "no-cache, no-store",
        "Pragma": "no-cache",
    })
    with urllib.request.urlopen(request, timeout=7) as reply:
        if reply.status != 200 or reply.geturl() != url:
            raise RuntimeError("PUBLIC_STORE_UNEXPECTED_HTTP_STATUS_OR_REDIRECT")
        data = reply.read(700_000)
    if len(data) < 2000:
        raise RuntimeError("PUBLIC_STORE_BODY_TOO_SMALL")
    return data


class _InvoiceFormScanner(HTMLParser):
    """Inspect form structure, including externally associated email controls.

    A successful public probe requires exactly one matching invoice POST form.
    Newsletter forms elsewhere on the page do not count as checkout forms.
    """

    def __init__(self, action: str) -> None:
        super().__init__(convert_charrefs=True)
        self.action = action
        self.active = None
        self.forms = []
        self.external_emails = set()
        self.ids_seen = set()
        self.duplicate_ids = set()
        self.malformed = False

    @staticmethod
    def _is_email_control(attrs):
        return ((attrs.get("name") or "").lower() == "email"
                or (attrs.get("type") or "").lower() == "email"
                or (attrs.get("id") or "").lower() == "mpw-buy-email")

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if tag == "form":
            if self.active is not None:
                self.malformed = True
                return
            form_id = attributes.get("id", "")
            if form_id:
                if form_id in self.ids_seen:
                    self.duplicate_ids.add(form_id)
                self.ids_seen.add(form_id)
            self.active = {
                "id": form_id,
                "method": (attributes.get("method") or "").lower(),
                "action": attributes.get("action"),
                "email_present": False,
                "csrf": False,
            }
        elif tag == "input":
            association = attributes.get("form")
            if association and self._is_email_control(attributes):
                self.external_emails.add(association)
            if self.active is None:
                return
            # An input with a form attribute belongs to that other form,
            # not automatically to the nearest enclosing form.
            if association and association != self.active["id"]:
                return
            if self._is_email_control(attributes):
                self.active["email_present"] = True
            if (attributes.get("name") == "csrfmiddlewaretoken"
                    and bool(attributes.get("value"))):
                self.active["csrf"] = True

    def handle_endtag(self, tag):
        if tag == "form":
            if self.active is None:
                self.malformed = True
            else:
                self.forms.append(self.active)
                self.active = None


def has_guarded_guest_invoice_form(body: bytes, product_id: int) -> bool:
    """Enforce one exact no-email CSRF invoice form; reject ambiguous duplicates."""
    if type(product_id) is not int or product_id <= 0:
        return False
    action = f"/commerce/trx-easy/start/{product_id}/"
    scanner = _InvoiceFormScanner(action)
    try:
        scanner.feed(body.decode("utf-8"))
        scanner.close()
    except (UnicodeDecodeError, ValueError):
        return False
    if scanner.malformed or scanner.active is not None:
        return False
    matching = [form for form in scanner.forms if form["action"] == action]
    if len(matching) != 1:
        return False
    form = matching[0]
    return (form["method"] == "post" and form["csrf"]
            and not form["email_present"]
            and (not form["id"] or (
                form["id"] not in scanner.external_emails
                and form["id"] not in scanner.duplicate_ids)))



def verify_public_buyer_routes(run_id: str) -> bool:
    """Require nine buyer-facing GET pages before and after public cutover.

    These probes never submit forms, create invoices, transfer funds or send mail.
    Only coarse failure categories are emitted, without customer information.
    """
    checked = 0
    deadline = time.monotonic() + BUYER_ROUTE_TOTAL_SECONDS
    for route, title, action in BUYER_ROUTE_PROBES:
        url = "https://mojplaywin.com" + route + "?mpw_cutover_probe=" + run_id
        request = urllib.request.Request(url, headers={
            "User-Agent": "MojPlayWin-owner-cutover-smoke/1.0",
            "Cache-Control": "no-cache, no-store",
            "Pragma": "no-cache",
        }, method="GET")
        category = "unexpected_response"
        remaining = deadline - time.monotonic()
        if remaining < 0.5:
            category = "probe_deadline_exceeded"
        else:
            try:
                with urllib.request.urlopen(request, timeout=min(7, remaining)) as reply:
                    if reply.status == 200 and reply.geturl() == url:
                        body = reply.read(250_000)
                        if title in body and action in body:
                            checkout = ("/checkout/" in route or route.startswith("/commerce/book/"))
                            if not checkout or has_guarded_guest_invoice_form(body, int(route.split("/")[3])):
                                checked += 1
                                continue
                            category = "checkout_form_invalid"
            except urllib.error.HTTPError as exc:
                category = ("http_" + str(exc.code) if exc.code in
                            (403, 404, 429, 500, 502, 503, 504) else "http_other")
            except (OSError, TimeoutError, RuntimeError, urllib.error.URLError):
                category = "network_or_read_error"
        print("MPW_BUYER_ROUTE_PROBE=" + json.dumps({
            "checked": checked, "passed": False,
            "route_group": ("checkout" if ("/checkout/" in route or
                                           route.startswith("/commerce/book/")) else "detail"),
            "category": category,
        }, sort_keys=True))
        return False
    print("MPW_BUYER_ROUTE_PROBE=" + json.dumps({"checked": checked, "passed": True}, sort_keys=True))
    return True


def verify_dynamic_public(run_id: str) -> bool:
    # Allow Passenger time to switch while bounding public requests and the
    # total observation window. A fixed six probes only waited ~15 seconds.
    end = time.monotonic() + 55
    observations = {}
    attempts = 0
    while attempts < 18 and (attempts == 0 or time.monotonic() < end - 4):
        attempt = attempts
        attempts += 1
        try:
            data = public_response(run_id + "-" + str(attempt))
            if (MARKER not in data and b"mpw-shop-kicker" in data and
                    b"mpw-store-catalog-20261026" in data and
                    all(route in data for route in PRODUCT_ROUTES)):
                if not verify_public_buyer_routes(run_id + "-after"):
                    observations["buyer_route_guard_failed"] = 1
                    print("MPW_PUBLIC_SWITCH_PROBE=" + json.dumps({
                        "dynamic_confirmed": False,
                        "observations": observations,
                        "attempts": attempts,
                    }, sort_keys=True))
                    return False
                print("MPW_PUBLIC_SWITCH_PROBE=" + json.dumps({
                    "dynamic_confirmed": True,
                    "observations": observations,
                    "attempts": attempts,
                }, sort_keys=True))
                return True
            category = "still_owned_static_fallback" if MARKER in data else "unexpected_non_django_html"
        except urllib.error.HTTPError as err:
            category = "http_" + str(err.code) if err.code in (403, 404, 429, 500, 502, 503, 504) else "http_other"
        except TimeoutError:
            category = "network_timeout"
        except (OSError, RuntimeError, urllib.error.URLError):
            category = "network_or_response_validation_error"
        observations[category] = observations.get(category, 0) + 1
        remaining = end - time.monotonic() - 4
        if attempts < 18 and remaining > 0:
            time.sleep(min(3, remaining))
    print("MPW_PUBLIC_SWITCH_PROBE=" + json.dumps({
        "dynamic_confirmed": False,
        "observations": observations,
        "attempts": attempts,
    }, sort_keys=True))
    return False


def perform_cutover(public: Path, backup_base: Path, run_id: str, probe) -> None:
    """Guaranteed rollback of owned files for any failed verification."""
    if not re.fullmatch(r"[0-9]{8,12}", run_id):
        raise RuntimeError("INVALID_RUN_ID")
    old_conf, new_conf, mode = inspect_owned_fallback(public)
    ht = public / ".htaccess"
    store = public / "store"
    marker = public / "tmp/restart.txt"
    backup = backup_base / run_id
    if backup.exists() or backup.is_symlink() or backup_base.is_symlink():
        raise RuntimeError("NON_UNIQUE_OR_UNSAFE_BACKUP")
    backup.mkdir(parents=True, mode=0o700)
    original = backup / "htaccess.original"
    with original.open("xb") as out:
        out.write(old_conf)
        out.flush()
        os.fsync(out.fileno())
    if original.read_bytes() != old_conf:
        raise RuntimeError("BACKUP_READBACK_FAILED")
    conf_changed = False
    dir_moved = False
    try:
        if ht.read_bytes() != old_conf:
            raise RuntimeError("CONCURRENT_HTACCESS_CHANGE")
        atomic_replace(ht, new_conf, mode)
        conf_changed = True
        if ht.read_bytes() != new_conf:
            raise RuntimeError("HTACCESS_REPLACEMENT_NOT_VERIFIED")
        if sorted(p.name for p in store.iterdir()) != ["index.html"]:
            raise RuntimeError("CONCURRENT_STORE_DIRECTORY_CHANGE")
        store.rename(backup / "store")
        dir_moved = True
        marker.touch()
        if not probe():
            raise RuntimeError("LIVE_DYNAMIC_PUBLIC_SMOKE_FAILED")
        print("MPW_DYNAMIC_STORE_CUTOVER=PASS;PUBLIC_DJANGO_CONFIRMED=YES;BACKUP=VERIFIED")
    except BaseException:
        rollback_safe = True
        if dir_moved:
            if store.exists() or not (backup / "store").is_dir():
                rollback_safe = False
            else:
                (backup / "store").rename(store)
        if conf_changed:
            if ht.read_bytes() != new_conf:
                rollback_safe = False
            else:
                atomic_replace(ht, old_conf, mode)
        marker.touch()
        if not rollback_safe:
            raise RuntimeError("ROLLBACK_CONFLICT_REQUIRES_MANUAL_RECOVERY")
        print("MPW_DYNAMIC_STORE_CUTOVER=ROLLED_BACK;FALLBACK_RESTORED=YES")
        raise


def main(run_id: str) -> None:
    if pwd.getpwuid(os.geteuid()).pw_name != "zomorod2":
        raise RuntimeError("UNEXPECTED_CPANEL_ACCOUNT")
    if not re.fullmatch(r"[0-9]{8,12}", run_id):
        raise RuntimeError("INVALID_RUN_ID")
    started = time.monotonic()
    check_actual_staging_store()
    baseline = public_response(run_id + "-before")
    if MARKER not in baseline:
        raise RuntimeError("PUBLIC_FALLBACK_BASELINE_NOT_PROVEN")
    # Existing static-fallback pages may legitimately serve 404, legacy
    # email forms or unusable checkout links. Requiring them to pass the NEW
    # guest purchase contract before cutover creates an impossible dependency:
    # the cutover intended to remove the fallback can never start.
    #
    # Observe this old state, but never accept it as proof of purchase. The
    # staged URLconf, invoice source and no-email CSRF form are checked above.
    # After cutover verify_dynamic_public MUST independently pass all nine
    # public routes. Any failed post-cutover route triggers exact rollback.
    baseline_passed = verify_public_buyer_routes(run_id + "-before")
    print("MPW_STATIC_BUYER_BASELINE=" + json.dumps({
        "passed": baseline_passed,
        "legacy_routes_not_commercial_proof": True,
        "after_cutover_nine_routes_mandatory": True,
    }, sort_keys=True))
    if time.monotonic() - started > PREFLIGHT_BUDGET_SECONDS:
        raise RuntimeError("CUTOVER_PREPARATION_TIME_BUDGET_EXCEEDED")
    print("MPW_STATIC_FALLBACK_BASELINE=CONFIRMED")
    perform_cutover(PUBLIC, BACKUP_BASE, run_id, lambda: verify_dynamic_public(run_id))


if __name__ == "__main__":
    try:
        if len(sys.argv) != 2:
            raise RuntimeError("INVALID_ARGUMENTS")
        main(sys.argv[1])
    except BaseException as err:
        print("MPW_DYNAMIC_STORE_CUTOVER=BLOCKED_OR_REVERTED;ERROR_CLASS=" + type(err).__name__, file=sys.stderr)
        raise SystemExit(1)

