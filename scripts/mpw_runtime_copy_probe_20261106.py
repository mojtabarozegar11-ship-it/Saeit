#!/usr/bin/env python3
"""Read-only live checkout routing and cache probe, with no buyer data access."""
from __future__ import annotations

import ast
import hashlib
import json
import os
from pathlib import Path
import pwd
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
    for key, func in (("django_route", django_check), ("public_http", public_response)):
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
