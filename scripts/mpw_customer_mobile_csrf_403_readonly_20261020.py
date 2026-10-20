#!/usr/bin/env python3
"""Read-only 403 CSRF diagnosis for main MojPlayWin customer auth, no credentials or writes."""
import os,sys,re,json,inspect,urllib.request,urllib.error,http.cookiejar
from pathlib import Path
ROOT=Path('/home/zomorod2/Saeit-staging')
assert ROOT.is_dir() and not ROOT.is_symlink()
os.chdir(ROOT);sys.path.insert(0,str(ROOT));os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings')
import django
django.setup()
from django.conf import settings
from django.urls import resolve
from django.test import Client
from django.middleware.csrf import get_token
from django.http import HttpRequest
from django.template.loader import get_template

def report(key,obj):print(key+'='+json.dumps(obj,ensure_ascii=False,sort_keys=True,default=str),flush=True)
names=['DEBUG','ALLOWED_HOSTS','CSRF_TRUSTED_ORIGINS','CSRF_COOKIE_DOMAIN','CSRF_COOKIE_SECURE',
'CSRF_COOKIE_HTTPONLY','CSRF_COOKIE_SAMESITE','CSRF_USE_SESSIONS','CSRF_COOKIE_PATH',
'SESSION_COOKIE_DOMAIN','SESSION_COOKIE_SECURE','SESSION_COOKIE_SAMESITE',
'SECURE_PROXY_SSL_HEADER','USE_X_FORWARDED_HOST','LOGIN_URL','CSRF_FAILURE_VIEW','SECURE_SSL_REDIRECT']
values={}
for k in names:
 val=getattr(settings,k,None)
 if k=='ALLOWED_HOSTS':val=['<redacted-host>' if not ('mojplaywin' in s or s in ('localhost','127.0.0.1')) else s for s in val]
 values[k]=val
report('MPW_CSRF_RUNTIME',values)
report('MPW_CSRF_MIDDLEWARE',[x for x in settings.MIDDLEWARE if any(s in x.lower() for s in ('csrf','session','auth','security','common'))])
for path in ('/accounts/login/','/accounts/register/','/commerce/book/779/'):
 try:
  m=resolve(path)
  fn=inspect.unwrap(m.func)
  report('MPW_CSRF_ROUTE',{'path':path,'module':fn.__module__,'function':fn.__name__})
 except Exception as e:report('MPW_CSRF_ROUTE',{'path':path,'exception':type(e).__name__})
for route in ('/accounts/login/','/accounts/register/'):
 try:
  c=Client(enforce_csrf_checks=True)
  response=c.get(route,secure=True,HTTP_HOST='mojplaywin.com',HTTP_USER_AGENT='Mozilla/5.0 Android Mobile')
  body=response.content.decode('utf8','replace')
  csrf=c.cookies.get(settings.CSRF_COOKIE_NAME)
  report('MPW_CSRF_INTERNAL_GET',{'path':route,'status':response.status_code,
    'form_post':bool(re.search(r'<form[^>]*method\s*=\s*["\']?post',body,re.I)),
    'token_input':bool(re.search(r'name=["\']csrfmiddlewaretoken["\']',body,re.I)),
    'csrf_cookie_set':csrf is not None,'cookie_secure':bool(csrf['secure']) if csrf else None,
    'cookie_samesite':csrf['samesite'] if csrf else None,
    'cookie_domain':csrf['domain'] if csrf else None,
    'csrf_header':'Vary' in response.headers and 'Cookie' in response.headers['Vary'],
    'redirect_url':response.url if response.status_code in (301,302,303,307,308) else None})
  if csrf and 'csrfmiddlewaretoken' in body and route=='/accounts/login/':
   token=re.search(r'name=["\']csrfmiddlewaretoken["\']\s+value=["\']([^"\']+)',body)
   if token is None:
    token=re.search(r'value=["\']([^"\']+)["\']\s+name=["\']csrfmiddlewaretoken["\']',body)
   if token is not None:
    post=c.post(route,{'username':'mpw_csrf_nonexistent_readonly_probe','password':'not-a-real-password','csrfmiddlewaretoken':token.group(1)},secure=True,HTTP_HOST='mojplaywin.com',HTTP_REFERER='https://mojplaywin.com'+route,HTTP_ORIGIN='https://mojplaywin.com')
    report('MPW_CSRF_INTERNAL_POST',{'path':route,'status':post.status_code,
      'is_csrf_403':post.status_code==403,'redirect':post.status_code in (301,302,303,307,308)})
 except Exception as e:report('MPW_CSRF_INTERNAL_ERROR',{'path':route,'exception':type(e).__name__,'message':str(e)[:120]})
for host in ('https://mojplaywin.com','https://www.mojplaywin.com'):
 route='/accounts/login/'
 try:
  req=urllib.request.Request(host+route,headers={'User-Agent':'Mozilla/5.0 (Linux; Android 10) Chrome/128 Mobile Safari/537.36','Cache-Control':'no-cache'})
  handler=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
  with handler.open(req,timeout=16) as resp:
   html=resp.read(150000).decode('utf8','replace')
   cookie=resp.headers.get_all('Set-Cookie') or []
   report('MPW_CSRF_PUBLIC_GET',{'host':host,'status':resp.status,'final_host':resp.geturl().split('/')[2],
       'token_input':bool(re.search(r'name=["\']csrfmiddlewaretoken["\']',html,re.I)),
       'cookie_names':[x.split('=',1)[0] for x in cookie],
       'cookie_secure':[bool(re.search(r';\s*Secure(?:\s*;|$)',x,re.I)) for x in cookie],
       'cache_control':resp.headers.get('Cache-Control',''),
       'vary':resp.headers.get('Vary',''),'content_type':resp.headers.get('Content-Type','')})
 except Exception as e:report('MPW_CSRF_PUBLIC_ERROR',{'host':host,'error':type(e).__name__,'detail':str(e)[:130]})
print('MPW_CSRF_READONLY_COMPLETE=PASS')
