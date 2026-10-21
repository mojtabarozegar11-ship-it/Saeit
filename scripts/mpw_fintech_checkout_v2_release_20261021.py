#!/usr/bin/env python3
"""MojPlayWin checkout visual refresh only: isolated, pinned, reversible.

No edits to payment logic, invoice creation, wallet addresses, authentication,
CSRF settings, order DB, other tenant roots or processor state.
"""
import hashlib
import json
import os
import pwd
import re
import stat
import sys
import tempfile
from pathlib import Path

HOME=Path("/home/zomorod2")
APP=HOME/"Saeit-staging"
ROOT=HOME/"mojplaywin.com"
WSGI=ROOT/"passenger_wsgi.py"
BACKUPS=HOME/".private_mojplaywin_main_agents"
TARGET=APP/"mpw_commerce/templates/mpw_commerce/product_checkout.html"
ASSETS=ROOT/"mpw-editorial/revenue/assets"
CSS=ASSETS/"mpw-fintech-checkout-v2.css"
PIN="b17fbc0dae7fd5b912fb1363383d257ec89b89bdcd0edc046608bb79720b1ab1"
CSS_LINK='<link rel="stylesheet" href="/mpw-editorial/revenue/assets/mpw-fintech-checkout-v2.css?v=20261021">'
MARKER='data-mpw-fintech-checkout="v2-20261021"'
HERO='''<div class="mpwf-top" data-mpw-fintech-checkout="v2-20261021">
  <section class="mpwf-intro" aria-label="Checkout overview">
    <span class="mpwf-eyebrow">MOJPLAYWIN / DIGITAL CHECKOUT</span>
    <div class="mpwf-intro-title">Checkout, without the guesswork.</div>
    <p class="mpwf-intro-subtitle">Review your item and price, create a unique invoice, and track payment confirmation before private delivery.</p>
  </section>
  <ol class="mpwf-steps" aria-label="Checkout stages">
    <li><span class="mpwf-step-num">01</span><span class="mpwf-step-copy">Review price</span></li>
    <li><span class="mpwf-step-num">02</span><span class="mpwf-step-copy">Secure invoice</span></li>
    <li><span class="mpwf-step-num">03</span><span class="mpwf-step-copy">Verified delivery</span></li>
  </ol>
</div>
'''
RUNPAT=re.compile(r"[0-9]{8,20}")
def fail(msg): raise RuntimeError(msg)
def digest(b):return hashlib.sha256(b).hexdigest()
def paths(run):
 if not RUNPAT.fullmatch(run):fail("Invalid release ID")
 return BACKUPS/("mpw-fintech-checkout-v2-"+run), BACKUPS/("mpw-fintech-checkout-v2-"+run+".staged.css")
def guard():
 if pwd.getpwuid(os.getuid()).pw_name!="zomorod2":fail("Wrong host identity")
 for p in (APP,ROOT,BACKUPS,ASSETS):
  if not p.is_dir() or p.is_symlink():fail("Unexpected directory "+str(p))
 if stat.S_IMODE(BACKUPS.stat().st_mode)&0o077:fail("Backup must be private")
 for p in (TARGET,WSGI):
  if not p.is_file() or p.is_symlink() or p.parent.is_symlink():fail("Unsafe target")
 if "APP='/home/zomorod2/Saeit-staging'" not in WSGI.read_text("utf8","replace"):
  fail("Unexpected main tenant Passenger identity")
 if CSS.is_symlink():fail("Unsafe theme path")
def valid_css(blob):
 if len(blob)<4000 or len(blob)>20000:fail("Unexpected theme CSS size")
 txt=blob.decode("utf8")
 for anchor in ("main .panel","main #invoice","main #downloads","main .mpwf-intro",
                "main #start","@media (max-width: 640px)"):
  if anchor not in txt:fail("Theme CSS missing "+anchor)
 if any(x in txt.lower() for x in ("javascript:", "@import", "behavior:")):
  fail("Unexpected active CSS payload")
def transform(blob,strict=True):
 if strict and digest(blob)!=PIN:fail("Checkout source SHA drift; refuse styling")
 t=blob.decode("utf8")
 if MARKER in t or CSS_LINK in t:fail("Already styled; no duplicate")
 if t.count("</head>")!=1 or len(re.findall(r"<main\b[^>]*>",t,re.I))!=1 or t.count("</main>")!=1:
  fail("Unexpected checkout template structure")
 if len(re.findall(r"<style\b",t,re.I))!=2 or len(re.findall(r"<script\b",t,re.I))!=1:
  fail("CSP-dependent style and script count has drifted")
 if t.count("{% csrf_token %}")!=1 or any(t.count('id="'+x+'"')!=1 for x in ("start","check","invoice","downloads")):
  fail("Checkout form and invoice controls diverged")
 head=t.replace("</head>",CSS_LINK+"\n</head>",1)
 m=re.search(r"<main\b[^>]*>",head,re.I)
 updated=head[:m.end()]+"\n"+HERO+head[m.end():]
 for term in ("{% csrf_token %}","<form","<script","<style"):
  if updated.count(term)!=t.count(term):fail("Protected checkout source was altered")
 reverted=updated.replace("\n"+HERO,"",1).replace(CSS_LINK+"\n","",1)
 if reverted!=t:fail("Out-of-scope template change")
 return updated.encode("utf8")
def atomic(target,blob,mode):
 fd,name=tempfile.mkstemp(dir=target.parent,prefix=".mpwf-modern-checkout-")
 try:
  os.fchmod(fd,mode)
  with os.fdopen(fd,"wb") as f:
   f.write(blob);f.flush();os.fsync(f.fileno())
  os.replace(name,target)
 finally:
  if os.path.exists(name):os.unlink(name)
def compile_template(blob):
 os.chdir(APP);sys.path.insert(0,str(APP))
 os.environ.setdefault("DJANGO_SETTINGS_MODULE","config.settings")
 import django;django.setup()
 from django.template import Template
 Template(blob.decode("utf8"))
def preview(run):
 guard()
 d,staged=paths(run)
 if d.exists() or CSS.exists():fail("Prior release or theme exists")
 if not staged.is_file() or staged.is_symlink():fail("Staged CSS missing")
 styles=staged.read_bytes();valid_css(styles)
 before=TARGET.read_bytes();after=transform(before)
 compile_template(after)
 print("MPWF_THEME_PREFLIGHT="+json.dumps({"checkout_source_pin":digest(before),
  "checkout_updated_sha":digest(after),"css_sha":digest(styles),
  "checkout_only":True,"script_count_unchanged":True,"style_count_unchanged":True,
  "csrf_preserved":True,"payment_code_unchanged":True}))
def publish(run):
 preview(run)
 d,staged=paths(run)
 old=TARGET.read_bytes();new=transform(old)
 theme=staged.read_bytes()
 if not d.parent.is_dir() or d.parent.is_symlink():fail("Unsafe backup parent")
 d.mkdir(mode=0o700)
 backup=d/"checkout-template.bak"
 with backup.open("xb") as f:
  os.fchmod(f.fileno(),0o600);f.write(old);f.flush();os.fsync(f.fileno())
 manifest={"run":run,"template_before":digest(old),"template_after":digest(new),
           "css_sha":digest(theme),"payment_logic_modified":False}
 with (d/"manifest.json").open("x",encoding="utf8") as f:
  os.fchmod(f.fileno(),0o600);json.dump(manifest,f);f.flush();os.fsync(f.fileno())
 if TARGET.read_bytes()!=old or CSS.exists():fail("Concurrent page change")
 try:
  atomic(CSS,theme,0o644)
  atomic(TARGET,new,stat.S_IMODE(TARGET.stat().st_mode))
  if digest(CSS.read_bytes())!=manifest["css_sha"] or digest(TARGET.read_bytes())!=manifest["template_after"]:
   fail("Failed post-write hash comparison")
 except BaseException:
  if digest(TARGET.read_bytes())==digest(new):
   atomic(TARGET,old,stat.S_IMODE(TARGET.stat().st_mode))
  if CSS.exists() and digest(CSS.read_bytes())==digest(theme):CSS.unlink()
  raise
 print("MPWF_FINTECH_THEME_INSTALLED="+json.dumps({"checkout_only":True,"backed_up":True,"run":run,
  "payment_logic_untouched":True,"public_asset":"/mpw-editorial/revenue/assets/mpw-fintech-checkout-v2.css"}))
def verify(run):
 guard()
 d,_=paths(run)
 manifest=json.loads((d/"manifest.json").read_text("utf8"))
 if manifest["run"]!=run or not (d/"checkout-template.bak").is_file():
  fail("Invalid release manifest")
 before=(d/"checkout-template.bak").read_bytes()
 if digest(before)!=manifest["template_before"] or digest(transform(before))!=manifest["template_after"]:
  fail("Template release proof failed")
 if digest(TARGET.read_bytes())!=manifest["template_after"] or digest(CSS.read_bytes())!=manifest["css_sha"]:
  fail("Active checkout or style differs")
 compile_template(TARGET.read_bytes())
 from django.test import RequestFactory
 from types import SimpleNamespace
 from mpw_commerce.product_checkout_page import product_checkout_page
 for pk in (72,225):
  req=RequestFactory().get("/store/product/%d/checkout/"%pk,secure=True,HTTP_HOST="mojplaywin.com")
  req.user=SimpleNamespace(is_authenticated=True,is_active=True,pk=-800812,username="isolated-buyer-theme-verifier")
  res=product_checkout_page(req,pk)
  page=res.content.decode("utf8","replace")
  if (res.status_code!=200 or CSS_LINK not in page or MARKER not in page
      or 'id="invoice"' not in page or 'id="downloads"' not in page
      or 'id="start"' not in page or "{% csrf_token %}" in page):
   fail("Authenticated test checkout render failed "+str(pk))
  if "Content-Security-Policy" not in page:
   fail("Strict checkout CSP not rendered")
 print("MPWF_FINTECH_THEME_VERIFIED="+json.dumps({"rendered_products":[72,225],
  "checkout_status":200,"payment_created":False,"financial_mutation":False,
  "css_sha":manifest["css_sha"],"csrf_rendered":True}))
def rollback(run):
 guard()
 d,_=paths(run);manifest=json.loads((d/"manifest.json").read_text("utf8"))
 old=(d/"checkout-template.bak").read_bytes()
 if digest(old)!=manifest["template_before"] or digest(TARGET.read_bytes())!=manifest["template_after"]:
  fail("Concurrent change; cannot safely rollback")
 if not CSS.is_file() or digest(CSS.read_bytes())!=manifest["css_sha"]:
  fail("Theme has been changed; cannot safely rollback")
 atomic(TARGET,old,stat.S_IMODE(TARGET.stat().st_mode))
 CSS.unlink()
 print("MPWF_FINTECH_THEME_ROLLBACK=PASS")
def selftest():
 sample=('<!doctype html><html><head><meta charset="utf-8"></head><body>'
         '<style></style><style></style><main><h1>Checkout</h1>'
         '<form>{% csrf_token %}<button id="start">Start</button></form>'
         '<button id="check">Check</button><section id="invoice"></section>'
         '<section id="downloads"></section></main><script></script></body></html>').encode()
 newer=transform(sample,strict=False)
 assert newer.count(CSS_LINK.encode())==1 and newer.count(MARKER.encode())==1
 assert newer.replace(("\n"+HERO).encode(),b"",1).replace((CSS_LINK+"\n").encode(),b"",1)==sample
 for bad in [b"<html></html>",newer]:
  try:transform(bad,strict=False)
  except RuntimeError:pass
  else:fail("Unsafe source passed selftest")
 print("MPWF_FINTECH_THEME_SELFTEST=PASS")
if __name__=="__main__":
 if len(sys.argv)==2 and sys.argv[1]=="selftest":selftest()
 elif len(sys.argv)==3 and sys.argv[1] in ("preview","publish","verify","rollback"):
  {"preview":preview,"publish":publish,"verify":verify,"rollback":rollback}[sys.argv[1]](sys.argv[2])
 else:raise SystemExit("selftest | preview|publish|verify|rollback RUN_ID")
