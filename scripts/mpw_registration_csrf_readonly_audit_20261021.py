#!/usr/bin/env python3
"""MojPlayWin signup HTTP 403 audit. No accounts, orders, DB mutations or funds.

Checks actual cPanel Django runtime + page markup + intentionally INCOMPLETE POST.
Never prints cookies, CSRF tokens, passwords, emails, session identifiers or keys.
"""
import inspect,json,os,re,sys
from pathlib import Path

APP=Path("/home/zomorod2/Saeit-staging")
SITE=Path("/home/zomorod2/mojplaywin.com")
WSGI=SITE/"passenger_wsgi.py"
assert APP.is_dir() and not APP.is_symlink()
assert SITE.is_dir() and not SITE.is_symlink()
assert WSGI.is_file() and "APP='/home/zomorod2/Saeit-staging'" in WSGI.read_text("utf8","replace")
os.chdir(APP)
sys.path.insert(0,str(APP))
os.environ.setdefault("DJANGO_SETTINGS_MODULE","config.settings")
import django
django.setup()
from django.conf import settings
from django.urls import resolve
from django.test import Client

def out(k,v): print(k+"="+json.dumps(v,sort_keys=True,ensure_ascii=False,default=str),flush=True)
flags=("DEBUG","CSRF_COOKIE_SECURE","CSRF_COOKIE_HTTPONLY","CSRF_COOKIE_SAMESITE",
       "CSRF_COOKIE_DOMAIN","CSRF_COOKIE_PATH","CSRF_USE_SESSIONS",
       "SESSION_COOKIE_SECURE","SESSION_COOKIE_SAMESITE",
       "SECURE_PROXY_SSL_HEADER","USE_X_FORWARDED_HOST","SECURE_SSL_REDIRECT")
out("MPW_REGISTER_CSRF_SETTINGS",{k:getattr(settings,k,None) for k in flags})
out("MPW_REGISTER_CSRF_TRUST",{
  "origins_include_base":"https://mojplaywin.com" in getattr(settings,"CSRF_TRUSTED_ORIGINS",[]),
  "origins_include_www":"https://www.mojplaywin.com" in getattr(settings,"CSRF_TRUSTED_ORIGINS",[]),
  "middleware_enabled":any(x.endswith(".CsrfViewMiddleware") for x in settings.MIDDLEWARE),
  "allowed_base_host":"mojplaywin.com" in settings.ALLOWED_HOSTS,
  "allowed_www_host":"www.mojplaywin.com" in settings.ALLOWED_HOSTS,
})
for route in ("/accounts/login/","/accounts/register/"):
    fn=inspect.unwrap(resolve(route).func)
    mod=inspect.getmodule(fn)
    filename=Path(mod.__file__)
    out("MPW_REGISTER_HANDLER",{"route":route,"module":mod.__name__,
        "name":fn.__name__,"source_available":filename.is_file()})
    # Source shape only, not rendered personal data or secrets.
    text=filename.read_text("utf8","replace")
    out("MPW_REGISTER_HANDLER_FLAGS",{
        "route":route,
        "mark_csrf_exempt":"csrf_exempt" in inspect.getsource(fn),
        "uses_ensure_csrf_cookie":"ensure_csrf_cookie" in text,
        "uses_render": "render(" in inspect.getsource(fn),
        "has_signup_post": "POST" in inspect.getsource(fn),
    })
    for mode in ("https_direct","proxy_https"):
        secure=mode=="https_direct"
        extras={"HTTP_HOST":"mojplaywin.com",
                "HTTP_USER_AGENT":"Mozilla/5.0 (Linux; Android 10) Chrome/131 Mobile Safari/537.36"}
        if mode=="proxy_https":extras["HTTP_X_FORWARDED_PROTO"]="https"
        c=Client(enforce_csrf_checks=True)
        got=c.get(route,secure=secure,**extras)
        markup=got.content.decode("utf8","replace")
        forms=re.findall(r"<form\b[^>]*>",markup,re.I)
        csrf_m=re.search(r'<input\b[^>]*name=["\x27]csrfmiddlewaretoken["\x27][^>]*>',markup,re.I)
        if csrf_m is None:csrf_m=re.search(r'<input\b[^>]*name=["\x27]csrfmiddlewaretoken["\x27][^>]*>',markup,re.I)
        token=""
        if csrf_m:
            val=re.search(r'value=["\x27]([^"\x27]+)',csrf_m.group(0),re.I)
            token=val.group(1) if val else ""
        attrs=[]
        for form in forms[:3]:
            action=re.search(r'action=["\x27]([^"\x27]+)',form,re.I)
            method=re.search(r'method=["\x27]([^"\x27]+)',form,re.I)
            attrs.append({"method":method.group(1) if method else "",
                          "action":action.group(1) if action else ""})
        cookie=c.cookies.get(settings.CSRF_COOKIE_NAME)
        out("MPW_REGISTER_CSRF_GET",{
            "route":route,"mode":mode,"http":got.status_code,
            "request_secure":got.wsgi_request.is_secure(),
            "forms":attrs,"token_present":bool(token),
            "cookie_present":cookie is not None,
            "cookie_secure":bool(cookie["secure"]) if cookie else None,
            "cookie_httponly":bool(cookie["httponly"]) if cookie else None,
            "cookie_samesite":cookie["samesite"] if cookie else None,
            "cookie_path":cookie["path"] if cookie else None,
            "cache_control":got.get("Cache-Control",""),
            "http_csp":got.get("Content-Security-Policy","")[:1400],
            "meta_csp_present":bool(re.search(r'<meta[^>]+http-equiv=["\\x27]Content-Security-Policy',markup,re.I)),
            "form_script_present":"mpw-csrf-fresh-submit-20261020" in markup,
            "vary_has_cookie":"Cookie" in got.get("Vary",""),
            "fresh_form_script":"mpw-csrf-fresh-submit-20261020" in markup,
        })
        if not token:continue
        # Intentionally missing all registration credentials; cannot create a user.
        post_data={"csrfmiddlewaretoken":token}
        opts=dict(extras)
        opts["HTTP_ORIGIN"]="https://mojplaywin.com"
        opts["HTTP_REFERER"]="https://mojplaywin.com"+route
        posted=c.post(route,post_data,secure=secure,**opts)
        out("MPW_REGISTER_CSRF_POST",{
            "route":route,"mode":mode,"scenario":"cookie_and_token_from_same_get",
            "http":posted.status_code,"csrf_rejected":posted.status_code==403,
            "redirect":posted.status_code in (301,302,303,307,308),
        })
        c.cookies.clear()
        without=c.post(route,post_data,secure=secure,**opts)
        out("MPW_REGISTER_CSRF_POST",{
            "route":route,"mode":mode,"scenario":"cookie_removed",
            "http":without.status_code,"csrf_rejected":without.status_code==403,
        })
out("MPW_REGISTER_CSRF_AUDIT",{"writes":0,"users_created":0,"payments":0,
                                "scope":"read_only_internal_django"})
