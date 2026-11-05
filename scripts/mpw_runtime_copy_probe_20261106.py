#!/usr/bin/env python3
"""Read-only live checkout routing and cache probe, with no buyer data access."""
from __future__ import annotations

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
    candidates = [
        Path("/home/zomorod2/public_html/.htaccess"),
        Path("/home/zomorod2/mojplaywin.com/.htaccess"),
        ROOT / ".htaccess",
    ]
    clues = []
    for path in candidates:
        if not path.is_file() or path.is_symlink() or path.stat().st_size > 40000:
            continue
        settings = {}
        for line in path.read_text("utf-8", "replace").splitlines():
            parts = line.strip().split(maxsplit=1)
            if len(parts) == 2 and parts[0] in (
                    "PassengerAppRoot", "PassengerStartupFile", "PassengerBaseURI"):
                settings[parts[0]] = parts[1][:180]
        if settings:
            clues.append({"location": str(path), "directives": settings})
    marker = ROOT / "tmp/restart.txt"
    return {"directives": clues,
            "restart_marker_exists": marker.is_file() and not marker.is_symlink(),
            "restart_mtime_ns": marker.stat().st_mtime_ns if marker.is_file()
            and not marker.is_symlink() else None}


def main():
    if (pwd.getpwuid(os.geteuid()).pw_name != "zomorod2"
            or ROOT.is_symlink() or not ROOT.is_dir()):
        raise RuntimeError("WRONG_READONLY_HOST")
    out = {"disk": file_check(), "passenger": passenger_hints()}
    for key, func in (("django_route", django_check), ("public_http", public_response)):
        try:
            out[key] = func()
        except Exception as exc:
            out[key] = {"error_type": type(exc).__name__}
    out.update({"read_only": True, "emails_sent": 0,
                "db_writes": 0, "payments": 0})
    print("MPW_RUNTIME_COPY_PROBE=" + json.dumps(out, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
