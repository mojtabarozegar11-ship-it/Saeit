#!/usr/bin/env python3
"""Redacted, read-only Django render readiness for the existing MojPlayWin store."""
import hashlib
import json
import os
import pwd
import sys
import types
from pathlib import Path

APP = Path("/home/zomorod2/Saeit-staging")
TARGET = APP / "core/mojplaywin_views.py"
REQUIRED_HASH_PREFIX = "337bd51a2390578d"
REQUIRED_BYTES = 15919
STATIC_KEYS = {
    "css": "site/mojplaywin.css",
    "header_image": "site/mojplaywin-header-emblem.jpg",
}


def classify_frame(filename):
    """Use fixed labels, never disclose runtime paths or traceback source lines."""
    path = str(filename).replace("\\", "/")
    if path.endswith(("/whitenoise/storage.py", "/django/contrib/staticfiles/storage.py")):
        return "staticfiles_storage"
    if path.endswith("/command_center/mpw_public.py"):
        return "managed_public_context"
    if path.endswith("/command_center/templatetags/mpw_main.py"):
        return "managed_template_tag"
    if path.endswith("/core/mojplaywin_views.py"):
        return "store_view"
    if "/django/template/" in path:
        return "django_template_engine"
    return "unknown"


def exception_origin(exc):
    locations = []
    tb = exc.__traceback__
    while tb is not None and len(locations) < 128:
        locations.append(classify_frame(tb.tb_frame.f_code.co_filename))
        tb = tb.tb_next
    return next((location for location in reversed(locations) if location != "unknown"), "unknown")


def manifest_summary(app):
    """Read bounded static metadata only; no Django calls or manifest mutation."""
    root = Path(app) / "staticfiles"
    manifest = root / "staticfiles.json"
    if root.is_symlink() or manifest.is_symlink():
        return {"state": "symlink_refused"}
    if not manifest.is_file():
        return {"state": "missing"}
    try:
        if manifest.stat().st_size > 3_000_000:
            return {"state": "oversize_refused"}
        data = json.loads(manifest.read_text(encoding="utf-8"))
        mapping = data.get("paths") if isinstance(data, dict) else None
        if not isinstance(mapping, dict):
            return {"state": "invalid_shape"}
        return {
            "state": "readable",
            "css_recorded": STATIC_KEYS["css"] in mapping,
            "header_image_recorded": STATIC_KEYS["header_image"] in mapping,
            "css_collected": (root / STATIC_KEYS["css"]).is_file(),
            "header_image_collected": (root / STATIC_KEYS["header_image"]).is_file(),
        }
    except (OSError, ValueError, TypeError, UnicodeError):
        return {"state": "unreadable_or_invalid"}


def safe_error(phase, exc, manifest=None):
    result = {
        "classification": "MPW_DYNAMIC_STORE_READONLY",
        "status": "blocked",
        "phase": phase,
        "exception_class": type(exc).__name__,
        "exception_origin": exception_origin(exc),
        "payments_created": False,
        "mail_sent": False,
        "source_mutated": False,
    }
    if manifest is not None:
        result["static_manifest"] = manifest
    return result


def main():
    phase = "preflight"
    manifest = None
    try:
        if pwd.getpwuid(os.geteuid()).pw_name != "zomorod2":
            raise RuntimeError("Wrong account")
        if APP.is_symlink() or not APP.is_dir() or TARGET.is_symlink() or not TARGET.is_file():
            raise RuntimeError("Invalid app root")
        raw = TARGET.read_bytes()
        if len(raw) != REQUIRED_BYTES or not hashlib.sha256(raw).hexdigest().startswith(REQUIRED_HASH_PREFIX):
            raise RuntimeError("Unexpected source version")
        if (APP / "core/commerce_funnel.py").exists():
            raise RuntimeError("Optional metrics now installed")

        manifest = manifest_summary(APP)
        sys.dont_write_bytecode = True
        os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
        os.chdir(APP)
        sys.path.insert(0, str(APP))
        os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
        phase = "django_setup"
        import django
        django.setup()
        phase = "import_view"
        from core.mojplaywin_views import store
        phase = "request_factory"
        from django.test import RequestFactory
        from django.contrib.auth.models import AnonymousUser
        req = RequestFactory().get("/store/", secure=True, HTTP_HOST="mojplaywin.com")
        req.user = AnonymousUser()
        phase = "render_view_with_memory_only_metrics_stub"
        from unittest.mock import patch
        stub = types.ModuleType("core.commerce_funnel")
        stub.record_funnel_event = lambda *args, **kwargs: None
        with patch.dict(sys.modules, {"core.commerce_funnel": stub}):
            response = store(req)
        data = response.content
        if response.status_code != 200 or len(data) < 2000:
            raise RuntimeError("Store page render invalid")
        for route in (b"/store/product/72/checkout/", b"/store/product/225/checkout/", b"/store/product/879/"):
            if route not in data:
                raise RuntimeError("Product CTA missing")
        print(json.dumps({
            "classification": "MPW_DYNAMIC_STORE_READONLY",
            "status": "passed",
            "phase": "complete",
            "product_cta_count": 3,
            "static_manifest": manifest,
            "payments_created": False,
            "mail_sent": False,
            "source_mutated": False,
        }, sort_keys=True))
        return 0
    except BaseException as exc:
        print(json.dumps(safe_error(phase, exc, manifest), sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
