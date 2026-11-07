#!/usr/bin/env python3
"""Redacted, read-only Django render readiness for the existing MojPlayWin store."""
import hashlib, json, os, pwd, sys, types
from pathlib import Path
APP=Path("/home/zomorod2/Saeit-staging")
TARGET=APP/"core/mojplaywin_views.py"
REQUIRED_HASH_PREFIX="337bd51a2390578d"
REQUIRED_BYTES=15919

def safe_error(phase, exc):
    return {"classification":"MPW_DYNAMIC_STORE_READONLY", "status":"blocked",
            "phase":phase, "exception_class":type(exc).__name__,
            "payments_created":False, "mail_sent":False, "source_mutated":False}

def main():
    phase="preflight"
    try:
        if pwd.getpwuid(os.geteuid()).pw_name!="zomorod2":
            raise RuntimeError("Wrong account")
        if APP.is_symlink() or not APP.is_dir() or TARGET.is_symlink() or not TARGET.is_file():
            raise RuntimeError("Invalid app root")
        raw=TARGET.read_bytes()
        if len(raw)!=REQUIRED_BYTES or not hashlib.sha256(raw).hexdigest().startswith(REQUIRED_HASH_PREFIX):
            raise RuntimeError("Unexpected source version")
        if (APP/"core/commerce_funnel.py").exists():
            raise RuntimeError("Optional metrics now installed")
        sys.dont_write_bytecode=True
        os.environ["PYTHONDONTWRITEBYTECODE"]="1"
        os.chdir(APP)
        sys.path.insert(0,str(APP))
        os.environ.setdefault("DJANGO_SETTINGS_MODULE","config.settings")
        phase="django_setup"
        import django
        django.setup()
        phase="import_view"
        from core.mojplaywin_views import store
        phase="request_factory"
        from django.test import RequestFactory
        from django.contrib.auth.models import AnonymousUser
        req=RequestFactory().get("/store/", secure=True, HTTP_HOST="mojplaywin.com")
        req.user=AnonymousUser()
        phase="render_view_with_memory_only_metrics_stub"
        from unittest.mock import patch
        stub=types.ModuleType("core.commerce_funnel")
        stub.record_funnel_event=lambda *args, **kwargs: None
        with patch.dict(sys.modules, {"core.commerce_funnel":stub}):
            response=store(req)
        data=response.content
        if response.status_code!=200 or len(data)<2000:
            raise RuntimeError("Store page render invalid")
        for route in (b"/store/product/72/checkout/",b"/store/product/225/checkout/",b"/store/product/879/"):
            if route not in data:
                raise RuntimeError("Product CTA missing")
        print(json.dumps({"classification":"MPW_DYNAMIC_STORE_READONLY","status":"passed",
           "phase":"complete","product_cta_count":3,"payments_created":False,
           "mail_sent":False,"source_mutated":False},sort_keys=True))
        return 0
    except BaseException as exc:
        print(json.dumps(safe_error(phase,exc),sort_keys=True))
        return 2

if __name__=="__main__":
    raise SystemExit(main())
