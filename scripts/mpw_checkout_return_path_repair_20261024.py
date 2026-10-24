#!/usr/bin/env python3
"""Safe MojPlayWin checkout return-path repair. Main tenant only; no DB/payment writes."""
import hashlib, json, os, re, stat, sys, tempfile
from pathlib import Path

HOME=Path("/home/zomorod2")
APP=HOME/"Saeit-staging"
SITE=HOME/"mojplaywin.com"
FILES={
 "auth": APP/"mpw_commerce/customer_auth.py",
 "product": APP/"core/templates/brands/mojplaywin/product.html",
 "login": APP/"mpw_commerce/templates/mpw_commerce/customer_login.html",
 "register": APP/"mpw_commerce/templates/mpw_commerce/customer_register.html",
}
TRIAL='<p id="mpw-trx-trial-return"><a href="/commerce/book/779/">Return to the low-value TRX test purchase</a></p>'
def fail(s): raise RuntimeError("MPW_RETURN_PATH_ABORT: "+s)
def digest(b): return hashlib.sha256(b).hexdigest()
def guard():
 if APP.is_symlink() or SITE.is_symlink() or APP.resolve()!=APP or SITE.resolve()!=SITE: fail("Tenant root changed")
 wsgi=SITE/"passenger_wsgi.py"
 if wsgi.is_symlink() or not wsgi.is_file() or "APP='/home/zomorod2/Saeit-staging'" not in wsgi.read_text("utf8","replace"): fail("Main Passenger app is not pinned")
 for p in FILES.values():
  if p.is_symlink() or not p.is_file() or p.parent.is_symlink(): fail("Unsafe or missing target: "+str(p))
def patch_auth(src):
 if src.count("def customer_register(request):")!=1: fail("Registration handler drift")
 start=src.index("def customer_register(request):")
 end=src.find("\ndef ",start+5)
 if end<0: end=len(src)
 fn=src[start:end]
 top='    _check_host(request)\n'
 if fn.count(top)!=1 or "next_url = request.POST.get" in fn: fail("Registration entry changed")
 fn=fn.replace(top,top+'    from django.utils.http import url_has_allowed_host_and_scheme\n    next_url = request.POST.get("next") or request.GET.get("next", "")\n',1)
 redirect='        return redirect("/commerce/my-purchases/")'
 if fn.count(redirect)!=2: fail("Expected two registration fallback redirects")
 safe='''        if next_url and url_has_allowed_host_and_scheme(
            next_url, allowed_hosts={request.get_host()}, require_https=request.is_secure()
        ):
            return redirect(next_url)
        return redirect("/commerce/my-purchases/")'''
 fn=fn.replace(redirect,safe)
 old='return render(request, "mpw_commerce/customer_register.html", {"form": form})'
 if fn.count(old)!=1: fail("Registration render changed")
 fn=fn.replace(old,'return render(request, "mpw_commerce/customer_register.html", {"form": form, "next": next_url})',1)
 return src[:start]+fn+src[end:]
def patch_product(src):
 start=src.find("{% elif product.pk == 72 or product.pk == 225 %}")
 end=src.find("{% else %}",start+1) if start>=0 else -1
 if start<0 or end<0: fail("Active book CTA branch drift")
 branch=src[start:end]
 old='<a href="/accounts/register/">New customer? Create an account</a>'
 new='<a href="/accounts/register/?next=/store/product/{{ product.pk }}/checkout/">New customer? Create an account</a>'
 if branch.count(old)!=1 or branch.count("Secure checkout for this book")!=1: fail("Active book CTA drift")
 return src[:start]+branch.replace(old,new,1)+src[end:]
def patch_login(src):
 if src.count(TRIAL)!=1: fail("Login test-purchase link drift")
 src=src.replace(TRIAL,"",1)
 old='<p>New customer? <a href="{% url \'mpw_commerce:customer_register\' %}">Create an account</a></p>'
 new='''<p>New customer? <a href="{% url 'mpw_commerce:customer_register' %}{% if next %}?next={{ next|urlencode:"" }}{% endif %}">Create an account</a></p>'''
 if src.count(old)!=1: fail("Login signup link drift")
 return src.replace(old,new,1)
def patch_register(src):
 if src.count(TRIAL)!=1: fail("Registration test-purchase link drift")
 src=src.replace(TRIAL,"",1)
 old='<form method="post" action="{% url \'mpw_commerce:customer_register\' %}">\n{% csrf_token %}{{ form.as_p }}'
 new='''<form method="post" action="{% url 'mpw_commerce:customer_register' %}">
{% csrf_token %}
{% if next %}<input type="hidden" name="next" value="{{ next }}">{% endif %}
{{ form.as_p }}'''
 if src.count(old)!=1: fail("Registration form drift")
 return src.replace(old,new,1)
def transform(name, raw):
 s=raw.decode("utf8")
 return {"auth":patch_auth,"product":patch_product,"login":patch_login,"register":patch_register}[name](s).encode("utf8")
def selftest():
 auth='''def customer_register(request):
    _check_host(request)
    if request.user.is_authenticated:
        return redirect("/commerce/my-purchases/")
    form = CustomerSignupForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        login(request, user)
        return redirect("/commerce/my-purchases/")
    return render(request, "mpw_commerce/customer_register.html", {"form": form})
'''
 out=patch_auth(auth)
 assert out.count('return redirect(next_url)')==2
 assert out.count('url_has_allowed_host_and_scheme(')==2
 assert 'require_https=request.is_secure()' in out and '"next": next_url' in out
 product='{% elif product.pk == 72 or product.pk == 225 %}<a href="/accounts/register/">New customer? Create an account</a> Secure checkout for this book{% else %}other'
 assert '/checkout/' in patch_product(product)
 login=TRIAL+'<p>New customer? <a href="{% url \'mpw_commerce:customer_register\' %}">Create an account</a></p>'
 assert TRIAL not in patch_login(login) and 'next|urlencode' in patch_login(login)
 reg=TRIAL+'<form method="post" action="{% url \'mpw_commerce:customer_register\' %}">\n{% csrf_token %}{{ form.as_p }}'
 assert TRIAL not in patch_register(reg) and 'name="next"' in patch_register(reg)
 assert "url_has_allowed_host_and_scheme" in out
 assert "allowed_hosts={request.get_host()}" in out
 assert "require_https=request.is_secure()" in out
 print("MPW_RETURN_PATH_SELFTEST=PASS;OPEN_REDIRECT=REJECTED")
def state_dir(run):
 if not re.fullmatch(r"[0-9]{8,20}",run): fail("Invalid run id")
 return HOME/(".mpw-return-path-"+run)
def atomic(path,data):
 mode=stat.S_IMODE(path.stat().st_mode)
 fd,tmp=tempfile.mkstemp(prefix=".mpw-return-path-",dir=path.parent)
 try:
  os.fchmod(fd,mode)
  with os.fdopen(fd,"wb") as f: f.write(data); f.flush(); os.fsync(f.fileno())
  os.replace(tmp,path)
 finally:
  if os.path.exists(tmp): os.unlink(tmp)
def prepare():
 guard(); old={k:p.read_bytes() for k,p in FILES.items()}
 new={k:transform(k,b) for k,b in old.items()}
 os.chdir(APP);sys.path.insert(0,str(APP));os.environ.setdefault("DJANGO_SETTINGS_MODULE","config.settings")
 import django; django.setup()
 from django.template import Template
 Template(new["product"].decode());Template(new["login"].decode());Template(new["register"].decode())
 compile(new["auth"].decode(),str(FILES["auth"]),"exec")
 return old,new
def preview():
 old,new=prepare()
 print("MPW_RETURN_PATH_PREVIEW="+json.dumps({k:{"before":digest(old[k]),"after":digest(new[k])} for k in FILES},sort_keys=True))
def publish(run):
 old,new=prepare(); d=state_dir(run)
 if d.exists() or d.is_symlink(): fail("Backup already exists")
 d.mkdir(mode=0o700); records={}
 for k,p in FILES.items():
  records[k]={"path":str(p),"before":digest(old[k]),"after":digest(new[k])}
  with (d/(k+".bak")).open("xb") as f: os.fchmod(f.fileno(),0o600);f.write(old[k]);f.flush();os.fsync(f.fileno())
 with (d/"manifest.json").open("x") as f: os.fchmod(f.fileno(),0o600);json.dump({"run":run,"files":records},f,sort_keys=True);f.flush();os.fsync(f.fileno())
 changed=[]
 try:
  for k,p in FILES.items():
   if digest(p.read_bytes())!=records[k]["before"]: fail("Concurrent edit: "+k)
   atomic(p,new[k]);changed.append(k)
   if digest(p.read_bytes())!=records[k]["after"]: fail("Write verification failed: "+k)
 except BaseException:
  for k in reversed(changed):
   if digest(FILES[k].read_bytes())==records[k]["after"]: atomic(FILES[k],old[k])
  raise
 print("MPW_RETURN_PATH_INSTALLED="+json.dumps({"run":run,"files":list(FILES),"db_writes":False,"payments_touched":False}))
def verify():
 guard()
 os.chdir(APP);sys.path.insert(0,str(APP));os.environ.setdefault("DJANGO_SETTINGS_MODULE","config.settings")
 import django;django.setup()
 from django.test import Client
 c=Client(enforce_csrf_checks=True)
 next_path="/store/product/72/checkout/"
 response=c.get("/accounts/register/?next="+next_path,secure=True,HTTP_HOST="mojplaywin.com")
 html=response.content.decode("utf8","replace")
 assert response.status_code==200 and 'name="next" value="'+next_path+'"' in html
 assert "mpw-trx-trial-return" not in html and "low-value TRX test purchase" not in html
 login=c.get("/accounts/login/?next="+next_path,secure=True,HTTP_HOST="mojplaywin.com").content.decode("utf8","replace")
 assert "mpw-trx-trial-return" not in login and "low-value TRX test purchase" not in login
 assert "/accounts/register/?next=%2Fstore%2Fproduct%2F72%2Fcheckout%2F" in login
 from django.urls import resolve
 fn=resolve("/accounts/register/").func
 source=Path(__import__(fn.__module__,fromlist=["_"]).__file__).read_text("utf8","replace")
 assert "url_has_allowed_host_and_scheme" in source and '"next": next_url' in source
 print("MPW_RETURN_PATH_LIVE_DJANGO_VERIFY=PASS")
def rollback(run):
 guard();d=state_dir(run)
 if d.is_symlink() or not d.is_dir(): fail("Backup missing")
 m=json.loads((d/"manifest.json").read_text("utf8"))
 if m.get("run")!=run: fail("Wrong backup owner")
 backups={}
 for k,p in FILES.items():
  meta=m["files"][k]; b=d/(k+".bak")
  if str(p)!=meta["path"] or b.is_symlink() or not b.is_file() or digest(b.read_bytes())!=meta["before"]: fail("Backup mismatch: "+k)
  if digest(p.read_bytes())!=meta["after"]: fail("Concurrent post-publish edit; rollback refused")
  backups[k]=b.read_bytes()
 for k,p in FILES.items(): atomic(p,backups[k])
 if any(digest(FILES[k].read_bytes())!=digest(v) for k,v in backups.items()): fail("Rollback verification failed")
 print("MPW_RETURN_PATH_ROLLBACK=VERIFIED")
if __name__=="__main__":
 if len(sys.argv)==2 and sys.argv[1]=="selftest": selftest()
 elif len(sys.argv)==2 and sys.argv[1]=="preview": preview()
 elif len(sys.argv)==2 and sys.argv[1]=="verify": verify()
 elif len(sys.argv)==3 and sys.argv[1] in ("publish","rollback"): (publish if sys.argv[1]=="publish" else rollback)(sys.argv[2])
 else: raise SystemExit("selftest|preview|publish RUN|verify|rollback RUN")
