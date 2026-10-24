#!/usr/bin/env python3
"""Reversible MojPlayWin book-copy coherence patch. No order/payment writes."""
from pathlib import Path
import hashlib, json, os, stat, sys, tempfile, re
HOME=Path("/home/zomorod2"); APP=HOME/"Saeit-staging"; SITE=HOME/"mojplaywin.com"
WSGI=SITE/"passenger_wsgi.py"; BACKUPS=HOME/".private_mojplaywin_main_agents"
FILES={"store":APP/"core/templates/mojplaywin/store.html",
       "product":APP/"core/templates/brands/mojplaywin/product.html"}
CHESS=("A 415-page English digital PDF (2026 edition) built around an 84-day structured chess training plan, with critical-position review worksheets, human-first game review, and practice and progress tracking.")
STORE_COPY=(
"<p>Two English digital books are available to buy now. Sign in or create an account to open a secure TRX invoice. Review the USD price before you pay. Your private download unlocks after payment is independently confirmed.</p>",
"<p>Two English digital books are available now. Sign in or create an account, then open the product checkout to create an invoice tied to your order. It shows the exact TRX amount and receiving address. Pay from Trust Wallet or another compatible TRON wallet; no wallet connection or sender-address registration is needed. Network fees are extra. Your private PDF unlocks after on-chain confirmation.</p>")
BOOK_COPY=("<p>A research-informed training guide on chess decisions, game analysis, strategic understanding, and deliberate practice.</p>","<p>"+CHESS+"</p>")
STATE_COPY=('<span class="mpw-book-state">Secure TRX invoice · account required</span>','<span class="mpw-book-state">Sign in for your order-specific TRX invoice</span>')
PAY_COPY=('<p class="mpw-book-pay-note">Sign in or create an account to open your order-specific TRX invoice. Send only the exact amount shown. Your private download appears after the network confirms payment.</p>','<p class="mpw-book-pay-note">Sign in or create an account to create an invoice linked to your order. The invoice shows the exact TRX amount and receiving address. No wallet connection or sender-address registration is needed: pay from Trust Wallet or another compatible TRON wallet. Network fees are extra. Send TRX only to the displayed address; do not send USDT or use another network. Your private PDF unlocks after on-chain confirmation.</p>')
PRODUCT_COPY=("Sign in to receive an order-specific secure invoice for this verified digital book. Private delivery is granted only after independently confirmed payment.","Sign in to create an order-specific TRX invoice linked to your account. The invoice shows the exact amount and receiving address. Pay from Trust Wallet or another compatible TRON wallet; no wallet connection or sender-address registration is needed. Network fees are extra. The private PDF unlocks after on-chain confirmation.")
DESCRIPTION=("The Science and Practice of Chess Improvement is a 415-page English digital PDF (2026 Grandmaster Analytical Research Edition) built around an 84-day structured chess training plan. It includes critical-position review worksheets, human-first game review, and practice and progress tracking. Listed price: US $7.50. Private PDF delivery follows independently confirmed payment.")
FIELDS=("description","seo_description","summary")
def fail(msg): raise RuntimeError("MPW_STORE_COPY_ABORT: "+msg)
def digest(data): return hashlib.sha256(data).hexdigest()
def run_id(value):
 if not re.fullmatch(r"[0-9]{9,20}",value): fail("Invalid workflow run id")
 return value
def state_dir(run): return BACKUPS/("store-copy-coherence-"+run)
def roots():
 if APP.is_symlink() or not APP.is_dir() or SITE.is_symlink() or not SITE.is_dir(): fail("Pinned app/site root unavailable")
 if WSGI.is_symlink() or not WSGI.is_file() or "APP='/home/zomorod2/Saeit-staging'" not in WSGI.read_text("utf8","replace"): fail("Passenger root is not pinned")
 if BACKUPS.is_symlink() or not BACKUPS.is_dir() or BACKUPS.stat().st_mode&0o077: fail("Private backup root unsafe")
 for p in FILES.values():
  if p.is_symlink() or not p.is_file() or p.parent.is_symlink() or p.stat().st_size>2_000_000: fail("Template missing or unsafe")
def once(s,a,b,label):
 n=s.count(a)
 if n!=1: fail("%s exact match count %s"%(label,n))
 return s.replace(a,b,1)
def templates(old):
 st=old["store"].decode("utf8")
 for label,pair in (("buyer copy",STORE_COPY),("chess listing",BOOK_COPY),("invoice account note",STATE_COPY),("checkout instructions",PAY_COPY)): st=once(st,*pair,label)
 prod=once(old["product"].decode("utf8"),*PRODUCT_COPY,"product checkout instructions")
 return {"store":st.encode(),"product":prod.encode()}
def setup_product():
 os.chdir(APP);sys.path.insert(0,str(APP));os.environ.setdefault("DJANGO_SETTINGS_MODULE","config.settings")
 import django;django.setup()
 from core.models import Product
 p=Product.objects.get(pk=72)
 if p.title!="The Science and Practice of Chess Improvement" or str(p.price)!="7.50" or p.currency!="USD" or not isinstance(p.metadata,dict): fail("Chess identity/price/metadata changed")
 return p
def read_metadata():
 from core.models import Product
 p=Product.objects.get(pk=72)
 return {k:p.metadata.get(k) for k in FIELDS}
def set_metadata(values,expected=None):
 from django.db import transaction
 from core.models import Product
 with transaction.atomic():
  p=Product.objects.select_for_update().get(pk=72); md=p.metadata
  if p.title!="The Science and Practice of Chess Improvement" or str(p.price)!="7.50" or p.currency!="USD" or not isinstance(md,dict): fail("Chess identity/price changed")
  if expected is not None and any(md.get(k)!=expected.get(k) for k in FIELDS): fail("Concurrent metadata edit")
  updated=dict(md)
  for k in FIELDS:
   if k not in values: updated.pop(k,None)
   else: updated[k]=values[k]
  p.metadata=updated;p.save(update_fields=["metadata","updated_at"])
def restart_markers():
 for root in (APP,SITE):
  if root.is_symlink() or not root.is_dir():fail("Restart root changed")
  d=root/"tmp"
  if d.is_symlink():fail("Restart directory symlink")
  d.mkdir(exist_ok=True)
  p=d/"restart.txt"
  if p.is_symlink() or (p.exists() and not p.is_file()):fail("Restart marker unsafe")
  p.touch()

def atomic_write(p,data):
 fd,tmp=tempfile.mkstemp(prefix=".mpw-store-copy-",dir=p.parent)
 try:
  os.fchmod(fd,stat.S_IMODE(p.stat().st_mode))
  with os.fdopen(fd,"wb") as f:f.write(data);f.flush();os.fsync(f.fileno())
  os.replace(tmp,p)
 finally:
  if os.path.exists(tmp):os.unlink(tmp)
def install(run):
 run=run_id(run);roots();setup_product()
 old={k:p.read_bytes() for k,p in FILES.items()}; new=templates(old); before=read_metadata()
 d=state_dir(run)
 if d.exists() or d.is_symlink():fail("Backup collision")
 d.mkdir(mode=0o700);manifest={"run":run,"metadata_before":before,"files":{}}
 for k,p in FILES.items():
  with (d/(k+".bak")).open("xb") as f:os.fchmod(f.fileno(),0o600);f.write(old[k]);f.flush();os.fsync(f.fileno())
  manifest["files"][k]={"path":str(p),"before":digest(old[k]),"after":digest(new[k])}
 with (d/"manifest.json").open("x") as f:os.fchmod(f.fileno(),0o600);json.dump(manifest,f,sort_keys=True);f.flush();os.fsync(f.fileno())
 changed=[];meta_written=False
 try:
  for k,p in FILES.items():
   if digest(p.read_bytes())!=manifest["files"][k]["before"]:fail("Concurrent template edit: "+k)
   atomic_write(p,new[k]);changed.append(k)
   if digest(p.read_bytes())!=manifest["files"][k]["after"]:fail("Template write mismatch: "+k)
  set_metadata({k:DESCRIPTION for k in FIELDS},expected=before);meta_written=True
  from django.template import Template
  for b in new.values():Template(b.decode("utf8"))
  restart_markers()
 except BaseException:
  if meta_written:set_metadata(before,expected={k:DESCRIPTION for k in FIELDS})
  for k in reversed(changed):
   if digest(FILES[k].read_bytes())==manifest["files"][k]["after"]:atomic_write(FILES[k],old[k])
  raise
 print(json.dumps({"status":"MPW_STORE_COPY_COHERENCE_INSTALLED","run":run,"changed_templates":list(FILES),"metadata_fields":list(FIELDS),"orders_or_payments_changed":False,"backup":str(d)},sort_keys=True))
def rollback(run):
 run=run_id(run);roots();d=state_dir(run)
 if d.is_symlink() or not d.is_dir():fail("Backup missing")
 m=json.loads((d/"manifest.json").read_text("utf8"))
 if m.get("run")!=run:fail("Backup run mismatch")
 olds={}
 for k,p in FILES.items():
  info=m["files"][k];old=(d/(k+".bak")).read_bytes()
  if str(p)!=info["path"] or digest(old)!=info["before"] or digest(p.read_bytes())!=info["after"]:fail("Concurrent template change")
  olds[k]=old
 expected={k:DESCRIPTION for k in FIELDS};set_metadata(m["metadata_before"],expected=expected)
 for k,p in FILES.items():atomic_write(p,olds[k])
 restart_markers()
 from django.db import transaction
 from core.models import Product
 with transaction.atomic():
  p=Product.objects.select_for_update().get(pk=72);md=dict(p.metadata)
  for k,v in m["metadata_before"].items():
   if v is None:md.pop(k,None)
   else:md[k]=v
  p.metadata=md;p.save(update_fields=["metadata","updated_at"])
 print(json.dumps({"status":"MPW_STORE_COPY_COHERENCE_ROLLED_BACK","restored_templates":list(FILES),"orders_or_payments_changed":False},sort_keys=True))
if __name__=="__main__":
 if len(sys.argv)!=3 or sys.argv[1] not in ("install","rollback"):raise SystemExit("Usage: patch.py install|rollback RUN_ID")
 {"install":install,"rollback":rollback}[sys.argv[1]](sys.argv[2])
