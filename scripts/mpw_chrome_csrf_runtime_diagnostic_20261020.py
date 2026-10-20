#!/usr/bin/env python3
"""Only reads Django security configuration and probes dummy mobile login CSRF."""
import os,sys,re,json,inspect
from pathlib import Path
ROOT=Path("/home/zomorod2/Saeit-staging")
assert ROOT.is_dir() and not ROOT.is_symlink()
os.chdir(ROOT);sys.path.insert(0,str(ROOT))
os.environ.setdefault("DJANGO_SETTINGS_MODULE","config.settings")
import django
django.setup()
from django.conf import settings
from django.urls import resolve
from django.test import Client
def put(k,v):print(k+"="+json.dumps(v,sort_keys=True,default=str),flush=True)
names=("CSRF_COOKIE_DOMAIN","CSRF_COOKIE_PATH","CSRF_COOKIE_SECURE","CSRF_COOKIE_HTTPONLY","CSRF_COOKIE_SAMESITE","CSRF_USE_SESSIONS","CSRF_TRUSTED_ORIGINS","SESSION_COOKIE_DOMAIN","SESSION_COOKIE_PATH","SESSION_COOKIE_SAMESITE","SECURE_PROXY_SSL_HEADER","USE_X_FORWARDED_HOST","LOGIN_URL","CSRF_FAILURE_VIEW")
put("MPW_CHROME_CSRF_SETTINGS",{x:getattr(settings,x,None) for x in names})
for route in ("/accounts/login/","/accounts/register/"):
 m=resolve(route);fn=inspect.unwrap(m.func)
 put("MPW_CHROME_CSRF_HANDLER",{"route":route,"module":fn.__module__,"name":fn.__name__})
 for label,origin,referer,keep in (("normal","https://mojplaywin.com","https://mojplaywin.com"+route,True),("www-origin","https://www.mojplaywin.com","https://www.mojplaywin.com"+route,True),("no-referer",None,None,True),("no-cookie","https://mojplaywin.com","https://mojplaywin.com"+route,False)):
  c=Client(enforce_csrf_checks=True)
  g=c.get(route,secure=True,HTTP_HOST="mojplaywin.com",HTTP_USER_AGENT="Mozilla/5.0 Android Chrome/130 Mobile")
  body=g.content.decode("utf8","replace")
  m=re.search(r'csrfmiddlewaretoken["\x27]\\s+value=["\x27]([^"\x27]+)',body)
  if m is None:m=re.search(r'value=["\x27]([^"\x27]+)["\x27]\\s+name=["\x27]csrfmiddlewaretoken',body)
  csrf=m.group(1) if m else ""
  cookie=bool(g.cookies.get("csrftoken"))
  if not keep:c.cookies.clear()
  kw={"secure":True,"HTTP_HOST":"mojplaywin.com"}
  if origin:kw["HTTP_ORIGIN"]=origin
  if referer:kw["HTTP_REFERER"]=referer
  p=c.post(route,{"username":"fake-csrf-test-user-26020","password":"invalid-not-real","csrfmiddlewaretoken":csrf},**kw)
  put("MPW_CHROME_CSRF_CASE",{"route":route,"case":label,"GET":g.status_code,"cookie_sent":cookie,"token_present":bool(csrf),"POST":p.status_code})
print("MPW_CHROME_CSRF_READONLY=PASS")
