#!/usr/bin/env python3
"""Fix MojPlayWin HTTPS signup POST 403 from no-referrer authentication pages.

No global CSRF weakening. Only two main-site customer form templates change;
their same-origin Referer is permitted, cross-site referers remain suppressed.
All existing tokens, cookies, form fields, JS, handlers and payment flow remain.
"""
import hashlib,json,os,pwd,re,stat,sys,tempfile
from pathlib import Path

ROOT=Path("/home/zomorod2/Saeit-staging")
SITE=Path("/home/zomorod2/mojplaywin.com")
WSGI=SITE/"passenger_wsgi.py"
BACK=Path("/home/zomorod2/.private_mojplaywin_main_agents")
FILES={
 "login":ROOT/"mpw_commerce/templates/mpw_commerce/customer_login.html",
 "register":ROOT/"mpw_commerce/templates/mpw_commerce/customer_register.html",
}
OLD='<meta name="referrer" content="no-referrer">'
NEW='<meta name="referrer" content="same-origin">'
def fail(message):raise RuntimeError(message)
def digest(raw):return hashlib.sha256(raw).hexdigest()
def guard():
 if pwd.getpwuid(os.getuid()).pw_name!="zomorod2":fail("Unexpected user")
 for folder in (ROOT,SITE,BACK):
  if folder.is_symlink() or not folder.is_dir():fail("Unexpected main tenant folder")
 if stat.S_IMODE(BACK.stat().st_mode)&0o077:fail("Backups are not private")
 if WSGI.is_symlink() or not WSGI.is_file() or "APP='/home/zomorod2/Saeit-staging'" not in WSGI.read_text("utf8","replace"):
  fail("Main MojPlayWin Passenger root unverified")
 for file in FILES.values():
  if file.is_symlink() or file.parent.is_symlink() or not file.is_file():
   fail("Unexpected customer template")
def modified(blob,kind):
 text=blob.decode("utf8")
 if text.count(OLD)!=1 or NEW in text:
  fail("Unexpected or already-fixed template; no blind rewrite")
 if text.count("{% csrf_token %}")!=1 or text.count("</form>")!=1:
  fail("CSRF form shape changed")
 if ("mpw-csrf-fresh-submit-20261020" not in text or
     'data-mpw-django-home-20261020' not in text):
  fail("Existing mobile security behavior changed")
 expected="mpw_commerce:customer_register" if kind=="register" else "mpw_commerce:customer_login"
 if expected not in text:fail("Incorrect named customer form")
 new=text.replace(OLD,NEW,1)
 if new.replace(NEW,OLD,1)!=text:fail("Diff exceeds Referrer-Policy")
 return new.encode("utf8")
def dirs(run):
 if not re.fullmatch(r"[0-9]{8,20}",run):fail("Invalid operation ID")
 return {
  kind:BACK/("mpw-csrf-referrer-"+kind+"-"+run+".bak")
  for kind in FILES
 }
def atomic(path,blob):
 fd,tmp=tempfile.mkstemp(dir=path.parent,prefix=".mpw-auth-referrer-")
 try:
  os.fchmod(fd,stat.S_IMODE(path.stat().st_mode))
  with os.fdopen(fd,"wb") as file:
   file.write(blob);file.flush();os.fsync(file.fileno())
  os.replace(tmp,path)
 finally:
  if os.path.exists(tmp):os.unlink(tmp)
def contract(expect_installed=False):
 os.chdir(ROOT);sys.path.insert(0,str(ROOT))
 os.environ.setdefault("DJANGO_SETTINGS_MODULE","config.settings")
 import django;django.setup()
 from django.test import Client
 from django.conf import settings
 import re as regex
 if not settings.CSRF_COOKIE_SECURE or not settings.SESSION_COOKIE_SECURE:
  fail("HTTPS cookie security was unexpectedly disabled")
 if settings.DEBUG is not False:fail("DEBUG must be false in production")
 if getattr(settings,"SECURE_REFERRER_POLICY","")=="no-referrer":
  fail("Header overrides template policy; cannot proceed")
 for route in ("/accounts/login/","/accounts/register/"):
  c=Client(enforce_csrf_checks=True)
  got=c.get(route,secure=True,HTTP_HOST="mojplaywin.com")
  html=got.content.decode("utf8","replace")
  if got.status_code!=200 or not regex.search(r'name=["\x27]csrfmiddlewaretoken["\x27]',html):
   fail("Protected CSRF form missing")
  if expect_installed:
   if NEW not in html or OLD in html:fail("New policy not present in rendered form")
  else:
   if OLD not in html:fail("Current template drift")
  if got.get("Referrer-Policy","")=="no-referrer":
   fail("HTTP header overrides secure same-origin policy")
  cookie=c.cookies.get(settings.CSRF_COOKIE_NAME)
  if not cookie or not cookie["secure"]:fail("Secure CSRF cookie absent")
  match=regex.search(r'<input\b[^>]*name=["\x27]csrfmiddlewaretoken["\x27][^>]*>',html)
  if not match:fail("Token field missing")
  val=regex.search(r'value=["\x27]([^"\x27]+)',match.group(0))
  if not val:fail("Token value missing")
  token=val.group(1)
  # No form credentials at all: cannot create any new user. No Origin included,
  # matching mobile user agents which require a valid HTTPS Referer.
  body={"csrfmiddlewaretoken":token}
  args={"secure":True,"HTTP_HOST":"mojplaywin.com"}
  rejected=c.post(route,body,**args)
  if rejected.status_code!=403:fail("No-Origin + no-Referer unexpectedly passed")
  accepted=c.post(route,body,HTTP_REFERER="https://mojplaywin.com"+route,**args)
  if accepted.status_code==403:fail("Valid same-origin Referer incorrectly rejected")
  wrong=c.post(route,body,HTTP_REFERER="https://evil.example/phish",**args)
  if wrong.status_code!=403:fail("Cross-origin Referer unexpectedly passed")
  c.cookies.clear()
  missing=c.post(route,body,HTTP_REFERER="https://mojplaywin.com"+route,**args)
  if missing.status_code!=403:fail("CSRF missing-cookie protection weakened")
 print("MPW_CSRF_SECURE_REFERER_CONTRACT=PASS; invalid_credentials_only=1; users_created=0")
def preview():
 guard()
 for kind,file in FILES.items():
  raw=file.read_bytes();result=modified(raw,kind)
  print("MPW_CSRF_REFERER_PREVIEW="+json.dumps({
   "template":kind,"before":digest(raw),"after":digest(result),
   "only_meta_policy_changed":True}))
 contract(False)
def install(run):
 guard()
 backups=dirs(run)
 copies={}
 for kind,file in FILES.items():
  old=file.read_bytes();updated=modified(old,kind)
  if backups[kind].exists() or backups[kind].is_symlink():fail("Backup already exists")
  copies[kind]=(old,updated)
 contract(False)
 written=[]
 try:
  for kind,file in FILES.items():
   old,new=copies[kind]
   with backups[kind].open("xb") as f:
    os.fchmod(f.fileno(),0o600)
    f.write(old);f.flush();os.fsync(f.fileno())
   if file.read_bytes()!=old:fail("Concurrent customer page modification")
   atomic(file,new);written.append(kind)
   if file.read_bytes()!=new:fail("Failed template integrity proof")
 except BaseException:
  for kind in reversed(written):
   old,new=copies[kind];file=FILES[kind]
   if file.read_bytes()==new:atomic(file,old)
  raise
 print("MPW_CSRF_REFERER_INSTALLED="+json.dumps({
  "two_customer_templates_only":True,
  "csrf_unchanged":True,"session_security_unchanged":True,
  "payments_untouched":True,"run":run}))
def verify(run):
 guard()
 for kind,file in FILES.items():
  p=dirs(run)[kind]
  if p.is_symlink() or not p.is_file():fail("Original backup not available")
  if file.read_bytes()!=modified(p.read_bytes(),kind):fail("Unexpected deployed change")
 contract(True)
 print("MPW_CSRF_REFERER_VERIFIED=PASS")
def rollback(run):
 guard()
 restored=[]
 for kind,file in FILES.items():
  p=dirs(run)[kind]
  if p.is_symlink() or not p.is_file():fail("Rollback backup missing")
  old=p.read_bytes()
  if file.read_bytes()!=modified(old,kind):fail("Concurrent template change")
  restored.append((file,old))
 for file,old in restored:atomic(file,old)
 print("MPW_CSRF_REFERER_ROLLBACK=PASS")
def selftest():
 for kind in FILES:
  other="mpw_commerce:customer_register" if kind=="register" else "mpw_commerce:customer_login"
  sample=('<!doctype html><html><head>'+OLD+'</head><body data-mpw-django-home-20261020="true">'
    '<form action="'+other+'">{% csrf_token %}</form>'
    '<script id="mpw-csrf-fresh-submit-20261020"></script></body></html>').encode()
  result=modified(sample,kind)
  assert NEW.encode() in result and OLD.encode() not in result
  assert result.replace(NEW.encode(),OLD.encode())==sample
  try:modified(result,kind)
  except RuntimeError:pass
  else:fail("Duplicate publish guard missing")
 print("MPW_CSRF_REFERER_SELFTEST=PASS")
if __name__=="__main__":
 if len(sys.argv)==2 and sys.argv[1]=="selftest":selftest()
 elif len(sys.argv)==2 and sys.argv[1]=="preview":preview()
 elif len(sys.argv)==3 and sys.argv[1] in ("install","verify","rollback"):
  {"install":install,"verify":verify,"rollback":rollback}[sys.argv[1]](sys.argv[2])
 else:raise SystemExit("selftest|preview|install RUN|verify RUN|rollback RUN");
