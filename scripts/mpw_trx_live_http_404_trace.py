#!/usr/bin/env python3
"""Read-only trace: why live MojPlayWin mounted TRX URL returns HTTP 404.

No user creation, DB mutation, financial operation, HTML or secret output.
"""
from __future__ import annotations
import json,os,sys,urllib.request,urllib.error
from pathlib import Path
ROOT=Path("/home/zomorod2/Saeit-staging")
SITE=Path("/home/zomorod2/mojplaywin.com")
os.chdir(ROOT)
sys.path.insert(0,str(ROOT))
os.environ.setdefault("DJANGO_SETTINGS_MODULE","config.settings")
import django
django.setup()
from django.conf import settings
from django.urls import resolve
from django.test import RequestFactory
from django.contrib.auth.models import AnonymousUser

URLS=("/store/","/store/product/72/","/commerce/trx-easy/status/987654321/",
      "/commerce/trx-easy/start/72/","/accounts/login/")
class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):
        return None
def public_status(url):
    req=urllib.request.Request("https://mojplaywin.com"+url,
        headers={"User-Agent":"MojPlayWin-Commerce-Smoke/1.0",
                 "Accept":"text/html"},method="GET")
    try:
        with urllib.request.build_opener(NoRedirect()).open(req,timeout=15) as r:
            return {"code":r.status,"content_type":r.headers.get("Content-Type","").split(";")[0]}
    except urllib.error.HTTPError as e:
        return {"code":e.code,"content_type":e.headers.get("Content-Type","").split(";")[0]}
    except Exception as e:
        return {"error_class":type(e).__name__}
def direct_view(route):
    try:
        match=resolve(route)
        req=RequestFactory().get(route,secure=True,HTTP_HOST="mojplaywin.com")
        req.user=AnonymousUser()
        result=match.func(req,**match.kwargs)
        return {"matched":True,"module":getattr(match.func,"__module__","?")[:100],
                "handler_status":getattr(result,"status_code",None),
                "has_login_redirect":getattr(result,"status_code",None)==302}
    except Exception as e:
        return {"matched":False,"error_type":type(e).__name__}
def other_info():
    app=SITE/"passenger_wsgi.py"
    public=SITE/".htaccess"
    src=app.read_text("utf8","replace")
    return {"passenger_exists":app.is_file(),
        "passenger_imports_wsgi":("application" in src and "config.wsgi" in src),
        "passenger_uses_staging":("Saeit-staging" in src),
        "htaccess_exists":public.is_file() and not public.is_symlink(),
        "htaccess_rewrite_directives":sum(1 for l in public.read_text("utf8","replace").splitlines()
            if l.strip().lower().startswith(("rewriterule","rewritecond"))) if public.is_file() else None,
        "sys_path_staging":str(ROOT) in sys.path,
        "settings_release_enabled":bool(getattr(settings,"MPW_WALLETLESS_TRX_PUBLIC_ENABLED",False))}
print("MPW_TRX_HTTP_404_TRACE="+json.dumps({"public":{p:public_status(p) for p in URLS},
    "direct":{p:direct_view(p) for p in URLS if "trx-easy" in p},
    "passenger":other_info()},sort_keys=True))
