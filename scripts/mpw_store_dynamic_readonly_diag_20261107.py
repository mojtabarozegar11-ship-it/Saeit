#!/usr/bin/env python3
"""Redacted, read-only Django render readiness for the existing MojPlayWin store."""
import json
import os
import pwd
import sys
from pathlib import Path

APP = Path("/home/zomorod2/Saeit-staging")
TARGET = APP / "core/mojplaywin_views.py"
REQUIRED_BYTES = 16371
GUARDED_STORE_ANCHOR = b"def store(request):\n # Analytics must never make the public storefront unavailable."
STATIC_KEYS = {
    "css": "site/mojplaywin.css",
    "header_image": "site/mojplaywin-header-emblem.jpg",
}


def known_guarded_store_source(raw):
    """Require the bounded post-repair view without importing optional analytics."""
    if len(raw) != REQUIRED_BYTES or raw.count(GUARDED_STORE_ANCHOR) != 1:
        return False
    tail = raw[raw.index(GUARDED_STORE_ANCHOR):][:900]
    return (b"try:\n  from .commerce_funnel import record_funnel_event" in tail and
            b"except Exception as exc:" in tail and
            raw.count(b"def store(request):") == 1)


def manifest_target_collected(root, mapping, key):
    """Check only the recorded static target; never follow a manifest path outside root."""
    target = mapping.get(key)
    if not isinstance(target, str) or "\\" in target or "\x00" in target:
        return False
    parts = target.split("/")
    if (len(parts) != 2 or parts[0] != "site" or
            not parts[1] or parts[1] in (".", "..") or
            not parts[1].startswith(Path(key).stem + ".") or
            not parts[1].endswith(Path(key).suffix)):
        return False
    target_path = Path(root) / parts[0] / parts[1]
    if target_path.parent.is_symlink() or target_path.is_symlink():
        return False
    return target_path.is_file()


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


def static_root_matches_expected(configured, app):
    """Boolean-only guard against diagnosing a different static collection root."""
    try:
        if not configured:
            return False
        root = Path(configured)
        expected = Path(app) / "staticfiles"
        return root.is_absolute() and root == expected and not root.is_symlink()
    except (OSError, ValueError, TypeError):
        return False


def manifest_summary(app):
    """Read bounded static metadata only; no Django calls or manifest mutation."""
    root = Path(app) / "staticfiles"
    manifest = root / "staticfiles.json"
    source_dir = Path(app) / "core/static/site"
    source = source_dir / "mojplaywin-header-emblem.jpg"
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
            "header_image_source_present": (
                source.is_file() and not source.is_symlink() and
                not source_dir.is_symlink() and not source_dir.parent.is_symlink() and not source_dir.parent.parent.is_symlink()
            ),
            "free_space_above_512mib": os.statvfs(app).f_bavail * os.statvfs(app).f_frsize >= 512 * 1024 * 1024,
            "css_recorded": STATIC_KEYS["css"] in mapping,
            "header_image_recorded": STATIC_KEYS["header_image"] in mapping,
            "css_collected": (root / STATIC_KEYS["css"]).is_file(),
            "header_image_collected": (root / STATIC_KEYS["header_image"]).is_file(),
            "css_manifest_target_collected": manifest_target_collected(root, mapping, STATIC_KEYS["css"]),
            "header_image_manifest_target_collected": manifest_target_collected(
                root, mapping, STATIC_KEYS["header_image"]
            ),
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
        if not known_guarded_store_source(raw):
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
        from django.conf import settings
        if isinstance(manifest, dict):
            manifest["runtime_static_root_matches_expected"] = static_root_matches_expected(
                getattr(settings, "STATIC_ROOT", None), APP
            )
        phase = "import_view"
        from core.mojplaywin_views import store
        phase = "request_factory"
        from django.test import RequestFactory
        from django.contrib.auth.models import AnonymousUser
        req = RequestFactory().get("/store/", secure=True, HTTP_HOST="mojplaywin.com")
        req.user = AnonymousUser()
        phase = "render_real_view_without_metrics_stub"
        response = store(req)
        data = response.content
        if response.status_code != 200 or len(data) < 2000:
            raise RuntimeError("Store page render invalid")
        for route in (b"/store/product/72/checkout/", b"/store/product/225/checkout/", b"/store/product/879/"):
            if route not in data:
                raise RuntimeError("Product CTA missing")
        phase = "resolve_django_store_path"
        from django.urls import resolve
        match = resolve("/store/")
        phase = "get_store_through_full_django_middleware"
        from django.test import Client
        import logging
        previous_logging_disable = logging.root.manager.disable
        logging.disable(logging.CRITICAL)
        try:
            routed_response = Client(raise_request_exception=False).get(
                "/store/", secure=True, HTTP_HOST="mojplaywin.com", HTTP_ACCEPT="text/html"
            )
        finally:
            logging.disable(previous_logging_disable)
        routed_body = routed_response.content
        product_routes = (b"/store/product/72/checkout/",
                          b"/store/product/225/checkout/",
                          b"/store/product/879/")
        route_check = {
            "name_is_store": match.url_name == "store",
            "http_status": routed_response.status_code,
            "django_store_marker": b"mpw-shop-kicker" in routed_body,
            "owned_static_fallback_marker": b"MPW_STATIC_STORE_FALLBACK_V1" in routed_body,
            "product_cta_count": sum(route in routed_body for route in product_routes),
        }
        is_ready = (route_check["name_is_store"] and route_check["http_status"] == 200
                    and route_check["django_store_marker"]
                    and not route_check["owned_static_fallback_marker"]
                    and route_check["product_cta_count"] == 3)
        print(json.dumps({
            "classification": "MPW_DYNAMIC_STORE_READONLY",
            "status": "passed" if is_ready else "blocked",
            "phase": "complete",
            "product_cta_count": 3,
            "routed_django_get": route_check,
            "static_manifest": manifest,
            "payments_created": False,
            "mail_sent": False,
            "source_mutated": False,
        }, sort_keys=True))
        return 0 if is_ready else 2
    except BaseException as exc:
        print(json.dumps(safe_error(phase, exc, manifest), sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
