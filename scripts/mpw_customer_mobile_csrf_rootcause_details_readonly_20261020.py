#!/usr/bin/env python3
"""Inspect production MojPlayWin mobile login and registration CSRF render only, without writes."""
import os,sys,inspect,json,ast,re
from pathlib import Path
APP=Path("/home/zomorod2/Saeit-staging")
if not APP.is_dir() or APP.is_symlink():raise RuntimeError("Unexpected Django app")
os.chdir(APP);sys.path.insert(0,str(APP));os.environ.setdefault("DJANGO_SETTINGS_MODULE","config.settings")
import django
django.setup()
from django.urls import resolve
from django.template.loader import get_template
from django.conf import settings
from django.test import Client
def output(name,data):print(name+"="+json.dumps(data,ensure_ascii=False,default=str))
for path in ("/accounts/login/","/accounts/register/"):
 fn=inspect.unwrap(resolve(path).func)
 mod=__import__(fn.__module__,fromlist=["_"])
 src=Path(mod.__file__).read_text(encoding="utf8")
 tree=ast.parse(src)
 funcs=[]
 for node in tree.body:
  if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef)) and node.name in (fn.__name__,"customer_login","customer_register","login"):
   content=ast.get_source_segment(src,node) or ""
   lines=[line[:180] if not any(t in line.lower() for t in ("password=","secret_key","api_key","private_key","session_key")) else "[REDACTED]" for line in content.splitlines()[:95]]
   funcs.append({"name":node.name,"lines":lines})
 output("MPW_CSRF_CUSTOMER_HANDLER",{"route":path,"module":fn.__module__,"functions":funcs})
 c=Client(enforce_csrf_checks=True)
 response=c.get(path,secure=True,HTTP_HOST="mojplaywin.com")
 html=response.content.decode("utf8","replace")
 output("MPW_CSRF_LOGIN_PAGE",{"route":path,"status":response.status_code,"html_len":len(html),"has_meta_viewport":bool(re.search(r'<meta\s+name=["\']viewport',html,re.I)),"has_csrf_token_input":'name="csrfmiddlewaretoken"' in html,"has_cookie_diagnostics":"document.cookie" in html,"has_return_to_checkout":"/commerce/book/779/" in html,"forms":[re.sub(r"\s+"," ",m)[:210] for m in re.findall(r"<form\b[^>]*>",html,re.I)[:4]],"set_cookie_names":list(response.cookies.keys()),"visible_post_button":bool(re.search(r'<button[^>]+type=["\']submit',html,re.I))})
for name in ["mpw_commerce/login.html","mpw_commerce/register.html","mpw_commerce/customer_login.html","registration/login.html"]:
 try:
  tpl=get_template(name)
  origin=tpl.origin.name if hasattr(tpl,"origin") else ""
  output("MPW_CSRF_TEMPLATE",{"name":name,"origin_rel":str(Path(origin).relative_to(APP)) if str(origin).startswith(str(APP)) else "<other-root>"})
 except Exception:pass

for name in ("mpw_commerce/customer_login.html","mpw_commerce/customer_register.html"):
 p=APP/"mpw_commerce/templates"/name
 if p.is_file() and not p.is_symlink():
  src=p.read_text("utf8","replace")
  output("MPW_CSRF_TEMPLATE_SOURCE",{"name":name,"source":src[:18000]})
  c=Client(enforce_csrf_checks=True)
  route="/accounts/login/" if "login" in name else "/accounts/register/"
  response=c.get(route,secure=True,HTTP_HOST="mojplaywin.com")
  output("MPW_CSRF_LOGIN_SECURITY_HEADERS",{"name":name,"csp":response.get("Content-Security-Policy"),"cache_control":response.get("Cache-Control"),"xframe":response.get("X-Frame-Options")})
print("MPW_CSRF_PRODUCTION_SOURCE_READONLY=PASS")
