#!/usr/bin/env python3
"""Read-only live checkout routing and cache probe, with no buyer data access."""
from __future__ import annotations

import ast
import hashlib
import inspect
import json
import os
from pathlib import Path
import pwd
import re
import secrets
import sys
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


ROOT = Path("/home/zomorod2/Saeit-staging")
LIVE = Path("/home/zomorod2/mojplaywin.com")
TEMPLATE = ROOT / "mpw_commerce/templates/mpw_commerce/product_checkout.html"
OLD = "to recover your download"
NEW = "Email recovery on another device is not yet available"


def file_check():
    if TEMPLATE.is_symlink() or not TEMPLATE.is_file():
        return {"available": False}
    data = TEMPLATE.read_bytes()
    if len(data) > 180000:
        return {"oversize": True}
    decoded = data.decode("utf-8", "replace")
    return {"sha256": hashlib.sha256(data).hexdigest(),
            "old_text": OLD in decoded, "new_text": NEW in decoded,
            "mtime_ns": TEMPLATE.stat().st_mtime_ns}


def django_check():
    sys.path.insert(0, str(ROOT))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    import django
    django.setup()
    from django.template.loader import get_template
    from django.urls import resolve
    tpl = get_template("mpw_commerce/product_checkout.html")
    found = resolve("/commerce/book/72/")
    return {"origin": str(Path(tpl.origin.name).relative_to(ROOT)),
            "url_module": getattr(found.func, "__module__", "unknown"),
            "url_name": found.url_name or "unnamed"}


def _bounded_source(path):
    """Return source bytes only for a small regular file inside staging.

    Reject symlinks, including parent directory symlinks, before reading.
    There is no fallback to reading an arbitrary path supplied by Django.
    """
    try:
        root = ROOT.resolve(strict=True)
        item = Path(path)
        resolved = item.resolve(strict=True)
        relative = resolved.relative_to(root)
        if (relative == Path(".") or item.is_symlink()
                or any(parent.is_symlink() for parent in item.parents if parent != item)
                or not item.is_file() or item.stat().st_size > 500_000):
            return None
        return relative.as_posix(), item.read_bytes()
    except (OSError, ValueError, RuntimeError):
        return None


def _template_names(source_bytes):
    """Find possible literal template references; do not claim execution."""
    try:
        tree = ast.parse(source_bytes)
    except (SyntaxError, ValueError, UnicodeDecodeError):
        return []
    names = set()
    for node in ast.walk(tree):
        if (not isinstance(node, ast.Constant) or not isinstance(node.value, str)
                or len(node.value) > 160):
            continue
        name = node.value
        if name.endswith(".html") and re.fullmatch(r"[A-Za-z0-9_./-]+", name):
            if not name.startswith("/") and ".." not in name.split("/"):
                names.add(name)
    return sorted(names)[:12]


def product_detail_source_map(resolve_route=None, load_template=None):
    """Map *configured* detail routes without querying orders or buyer data.

    Neither Django's resolver nor template-loader inspection establishes the
    effective HTTP worker identity or permission to release to production.
    """
    if resolve_route is None:
        from django.urls import resolve as resolve_route
    if load_template is None:
        from django.template.loader import get_template as load_template
    details = {}
    for product_id in (72, 225, 879):
        try:
            route = resolve_route(f"/store/product/{product_id}/")
            view = inspect.unwrap(route.func)
            view_file = inspect.getsourcefile(view)
            source = _bounded_source(view_file) if view_file else None
            info = {"route_resolved": True,
                    "url_name": str(route.url_name or "unnamed")[:100],
                    "handler_module": str(getattr(view, "__module__", "unknown"))[:140],
                    "view_source_available": source is not None}
            if source:
                relative, data = source
                info.update({"view_source_relative": relative,
                             "view_source_sha256": hashlib.sha256(data).hexdigest()})
                templates = []
                for name in _template_names(data):
                    try:
                        template = load_template(name)
                        origin = _bounded_source(template.origin.name)
                        if origin:
                            tpl_relative, tpl_bytes = origin
                            templates.append({"name": name,
                                              "relative": tpl_relative,
                                              "sha256": hashlib.sha256(tpl_bytes).hexdigest()})
                    except Exception:
                        # An unresolved template is a candidate, never evidence.
                        continue
                info["candidate_templates"] = templates
            details[str(product_id)] = info
        except Exception as exc:
            details[str(product_id)] = {"route_resolved": False,
                                        "error_type": type(exc).__name__}
    return {"configured_django_details": details,
            "effective_public_worker_verified": False,
            "template_candidates_are_active": False,
            "release_permitted": False}


def public_response():
    url = ("https://mojplaywin.com/commerce/book/72/"
           "?runtime_copy_probe=" + secrets.token_hex(8))
    request = Request(url, headers={"Cache-Control": "no-cache",
                                    "Pragma": "no-cache",
                                    "User-Agent": "MPW-ReadOnly-Monitor/1.0"})
    try:
        with urlopen(request, timeout=12) as response:
            if response.status != 200:
                return {"status": response.status}
            raw = response.read(250000)
            html = raw.decode("utf-8", "replace")
            hdrs = response.headers
            return {"status": response.status,
                    "old_text": OLD in html, "new_text": NEW in html,
                    "headers": {k: hdrs.get(k) for k in (
                        "Cache-Control", "Age", "X-LiteSpeed-Cache",
                        "CF-Cache-Status", "Server", "Vary") if hdrs.get(k)}}
    except (HTTPError, URLError, TimeoutError, OSError) as exc:
        return {"error_type": type(exc).__name__}


def passenger_hints():
    # Never publish PassengerAppRoot or other raw directives in public CI logs.
    # A UAPI app root and the WSGI module import path are different identities.
    candidates = [
        ("public_html", Path("/home/zomorod2/public_html/.htaccess")),
        ("site_root", LIVE / ".htaccess"),
        ("source_root", ROOT / ".htaccess"),
    ]
    clues = []
    for label, path in candidates:
        if not path.is_file() or path.is_symlink() or path.stat().st_size > 40000:
            continue
        settings = {}
        for line in path.read_text("utf-8", "replace").splitlines():
            parts = line.strip().split(maxsplit=1)
            if len(parts) == 2 and parts[0] in (
                    "PassengerAppRoot", "PassengerStartupFile", "PassengerBaseURI"):
                settings[parts[0]] = parts[1].strip()
        if settings:
            clues.append({
                "location_label": label,
                "app_root_is_site_root": settings.get("PassengerAppRoot") == str(LIVE),
                "app_root_is_source_root": settings.get("PassengerAppRoot") == str(ROOT),
                "startup_is_passenger_wsgi": settings.get("PassengerStartupFile") == "passenger_wsgi.py",
                "base_uri_is_root": settings.get("PassengerBaseURI") == "/",
                "has_root_directive": "PassengerAppRoot" in settings,
            })
    marker = ROOT / "tmp/restart.txt"
    return {"directives": clues,
            "restart_marker_exists": marker.is_file() and not marker.is_symlink(),
            "restart_mtime_ns": marker.stat().st_mtime_ns if marker.is_file()
            and not marker.is_symlink() else None}


def active_root_inventory():
    """Hashes and counts only, without loading live database or secrets."""
    if LIVE.is_symlink() or not LIVE.is_dir():
        return {"root_available": False}
    inspected = {}
    for rel in (
        "passenger_wsgi.py",
        "mpw_commerce/templates/mpw_commerce/product_checkout.html",
        "services/mpw_trx_guest_commerce.py",
        "services/mpw_trx_email_recovery.py",
        "config/settings.py",
        "tmp/restart.txt",
    ):
        p = LIVE / rel
        if p.is_symlink() or not p.is_file() or not p.resolve().is_relative_to(LIVE):
            inspected[rel] = {"regular_file": False}
            continue
        if p.stat().st_size > 180000:
            inspected[rel] = {"oversize": True}
            continue
        data = p.read_bytes()
        content = data.decode("utf-8", "replace")
        details = {"sha256": hashlib.sha256(data).hexdigest(),
                   "size": len(data)}
        if rel.endswith("product_checkout.html"):
            details.update({"old_text": OLD in content, "new_text": NEW in content,
                            "old_occurrences": content.count(OLD)})
        if rel == "services/mpw_trx_guest_commerce.py":
            details["capture_setting_referenced"] = (
                "MPW_GUEST_EMAIL_CLAIM_CAPTURE_ENABLED" in content)
        if rel == "passenger_wsgi.py":
            try:
                tree = ast.parse(content)
                path_literals = [n.value for n in ast.walk(tree)
                                 if isinstance(n, ast.Constant) and isinstance(n.value, str)
                                 if ("Saeit" in n.value or "mojplaywin" in n.value)
                                 if len(n.value) < 200]
                details["source_root_literal_present"] = str(ROOT) in path_literals
                details["site_root_literal_present"] = str(LIVE) in path_literals
                details["wsgi_parse_status"] = "valid_python"
                details["important_limitation"] = (
                    "WSGI path literals alone do not establish the effective imported app"
                )
            except SyntaxError:
                details["wsgi_parse_status"] = "syntax_error"
        inspected[rel] = details
    return {"root_available": True, "files": inspected}


def main():
    if (pwd.getpwuid(os.geteuid()).pw_name != "zomorod2"
            or ROOT.is_symlink() or not ROOT.is_dir()):
        raise RuntimeError("WRONG_READONLY_HOST")
    out = {"disk": file_check(), "passenger": passenger_hints(),
           "active_root": active_root_inventory()}
    for key, func in (("django_route", django_check),
                      ("configured_product_details", product_detail_source_map),
                      ("public_http", public_response)):
        try:
            out[key] = func()
        except Exception as exc:
            out[key] = {"error_type": type(exc).__name__}
    out.update({"read_only": True, "emails_sent": 0,
                "db_writes": 0, "payments": 0,
                "effective_wsgi_import_verified": False,
                "recovery_backup_verified": False,
                "release_permitted": False})
    print("MPW_RUNTIME_COPY_PROBE=" + json.dumps(out, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
