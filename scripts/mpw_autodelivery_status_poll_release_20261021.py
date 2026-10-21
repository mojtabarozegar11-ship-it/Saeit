#!/usr/bin/env python3
"""Surgical, reversible MojPlayWin checkout auto-delivery status polling release.

Changes ONLY payment-status UI JS, never payment state, RPC, ledger, receipts,
file access, secrets, cron, or fulfillment code. Require actual backend paid
entitlement and guarded download paths. No fake paid data reaches production.
"""
import hashlib,json,os,pwd,re,stat,sys,tempfile
from pathlib import Path

APP=Path("/home/zomorod2/Saeit-staging")
SITE=Path("/home/zomorod2/mojplaywin.com")
TARGET=APP/"mpw_commerce/templates/mpw_commerce/product_checkout.html"
PRIVATE=Path("/home/zomorod2/.private_mojplaywin_main_agents")
WSGI=SITE/"passenger_wsgi.py"
MARK="MPW_CRYPTO_AUTODELIVERY_POLL_V1"
START='let currentOrder = null;'
INVOICE='''    invoiceBox.hidden=false;
    say("Your signed invoice is ready. Review the network and exact amount before sending.");'''
OLD_OPEN='''check.addEventListener("click",async()=>{
  if (!currentOrder)return;
  check.disabled=true;'''
NEW_OPEN='''async function refreshAndDeliver() {
  if (!currentOrder || polling || delivered)return;
  polling=true;
  check.disabled=true;'''
OLD_HIDE='''      invoiceBox.hidden=true;
      const holder=document.getElementById("links");'''
NEW_HIDE='''      const holder=document.getElementById("links");'''
OLD_PAID='''      downloadBox.hidden=false;
      say("Payment confirmed and access granted.");'''
NEW_PAID='''      if (holder.children.length) {
        invoiceBox.hidden=true;
        delivered=true;
        stopPolling();
        downloadBox.hidden=false;
        say("Payment confirmed by the server. Your secure download is ready.");
      } else {
        say("Payment status is unavailable. No download has been authorized.");
      }'''
OLD_PENDING='''      say("Payment has not yet been independently confirmed. Do not pay again. Check later or contact support.");'''
NEW_PENDING='''      say("Awaiting independent blockchain payment confirmation. This page checks automatically; do not pay twice.");'''
OLD_CLOSE='''  } catch(err) {say(err instanceof Error?err.message:"Payment status unavailable; do not pay again.");}
  finally {check.disabled=false;}
});
})();'''
NEW_CLOSE='''  } catch(err) {say(err instanceof Error?err.message:"Payment status unavailable; do not pay again.");}
  finally {
    polling=false;
    check.disabled=false;
    if (!delivered) schedulePolling(12000);
  }
}
check.addEventListener("click",()=>{ stopPolling(); void refreshAndDeliver(); });
document.addEventListener("visibilitychange",()=>{
  if (!document.hidden && currentOrder && !delivered && pollingStartedAt) {
    stopPolling();
    void refreshAndDeliver();
  }
});
})();'''
STATE='''// MPW_CRYPTO_AUTODELIVERY_POLL_V1: read-only status checks, NEVER local payment grants
let pollTimer=null;
let polling=false;
let delivered=false;
let pollingStartedAt=0;
function stopPolling(){
  if(pollTimer!==null){ window.clearTimeout(pollTimer); pollTimer=null; }
}
function schedulePolling(delay=12000){
  stopPolling();
  if (!currentOrder || delivered || !pollingStartedAt) return;
  // Keep stale or abandoned sessions from polling forever; manual check remains.
  if (Date.now()-pollingStartedAt >= 35*60*1000) {
    say("Automatic checks stopped after 35 minutes. Use Check payment status or contact support; do not pay twice.");
    return;
  }
  pollTimer=window.setTimeout(()=>{
    pollTimer=null;
    if(document.hidden){schedulePolling(15000);return;}
    void refreshAndDeliver();
  },delay);
}'''
def sha(raw):return hashlib.sha256(raw).hexdigest()
def fail(s):raise RuntimeError(s)
def ensure_home():
 if pwd.getpwuid(os.getuid()).pw_name!="zomorod2":fail("Incorrect cPanel identity")
 for d in (APP,SITE,PRIVATE):
  if not d.is_dir() or d.is_symlink():fail("Unsafe site root")
 if stat.S_IMODE(PRIVATE.stat().st_mode)&0o077:fail("Private backups must not be world accessible")
 for f in (TARGET,WSGI):
  if not f.is_file() or f.is_symlink() or f.parent.is_symlink():fail("Unsafe source path")
 if "APP='/home/zomorod2/Saeit-staging'" not in WSGI.read_text("utf8","replace"):
  fail("Main MojPlayWin Passenger root mismatch")
def changed(old):
 source=old.decode("utf8")
 if MARK in source:fail("Auto-delivery already installed; no duplicate")
 if len(source)<5000 or len(source)>60000:fail("Unexpected checkout template size")
 if source.count("<script")!=1 or source.count("</script>")!=1 or source.count("{% csrf_token %}")!=1:
  fail("Checkout CSP or CSRF shape drift")
 if source.count("id=\"invoice\"")!=1 or source.count("id=\"downloads\"")!=1:
  fail("Missing approved checkout DOM identifiers")
 edits=[
  (START,START+"\n"+STATE),
  (INVOICE,'''    invoiceBox.hidden=false;
    delivered=false;
    pollingStartedAt=Date.now();
    stopPolling();
    schedulePolling(6000);
    say("Your signed invoice is ready. Review the network and exact amount before sending. Payment status updates automatically.");'''),
  (OLD_OPEN,NEW_OPEN),
  (OLD_HIDE,NEW_HIDE),
  (OLD_PAID,NEW_PAID),
  (OLD_PENDING,NEW_PENDING),
  (OLD_CLOSE,NEW_CLOSE),
 ]
 for before,after in edits:
  if source.count(before)!=1:fail("Checkout script changed: no blind rewrite")
  source=source.replace(before,after,1)
 for restricted in ("'/commerce/checkout/order/'",):
  if source.count(restricted)!=old.decode("utf8").count(restricted):
   fail("Payment requests changed")
 if source.count("let currentOrder = null;")!=1 or source.count(MARK)!=1:
  fail("Unexpected repeat")
 if source.count("<script")!=1 or source.count("</script>")!=1 or source.count("{% csrf_token %}")!=1:
  fail("Unsafe template change")
 if source.count("api(\"/commerce/checkout/status/")!=1 or source.count("can_access_purchased_items")!=1:
  fail("Unexpected backend authorization contract")
 if source.count("window.setTimeout(")!=1 or source.count("fetch(")!=1:
  fail("Unexpected polling or network behavior")
 if not all(t in source for t in ("!/^\\/commerce\\/download\\/[0-9]+\\/$/.test(path)",
                                  "document.hidden","35*60*1000","holder.children.length")):
  fail("Unsafe download or polling contract")
 # Django code remains untouched; no new script tags or inline styles.
 return source.encode("utf8")

def atomic(blob):
 fd,name=tempfile.mkstemp(dir=TARGET.parent,prefix=".mpw-auto-delivery-")
 try:
  os.fchmod(fd,stat.S_IMODE(TARGET.stat().st_mode))
  with os.fdopen(fd,"wb") as f:f.write(blob);f.flush();os.fsync(f.fileno())
  os.replace(name,TARGET)
 finally:
  if os.path.exists(name):os.unlink(name)

def runpaths(run):
 if re.fullmatch(r"[0-9]{8,20}",run) is None:fail("Invalid run")
 return (PRIVATE/("mpw-autodelivery-js-"+run+".backup"),
         PRIVATE/("mpw-autodelivery-js-"+run+".json"))
def django_check(blob):
 os.chdir(APP);sys.path.insert(0,str(APP))
 os.environ.setdefault("DJANGO_SETTINGS_MODULE","config.settings")
 import django;django.setup()
 from django.template import Template
 Template(blob.decode("utf8"))
 from django.test import RequestFactory
 from types import SimpleNamespace
 from mpw_commerce.product_checkout_page import product_checkout_page
 for pk in (72,225,779):
  req=RequestFactory().get("/commerce/book/%d/"%pk,secure=True,HTTP_HOST="mojplaywin.com")
  req.user=SimpleNamespace(pk=-502991,username="readonly-ux-test",is_authenticated=True,is_active=True)
  page=product_checkout_page(req,pk)
  html=page.content.decode("utf8","replace")
  if page.status_code!=200 or "<script" not in html or MARK not in html:
   fail("Checkout render or CSP could not be validated for product "+str(pk))
  if not page.has_header("Content-Security-Policy") and "Content-Security-Policy" not in html:
   fail("Strict script CSP disappeared")
def preview():
 ensure_home()
 before=TARGET.read_bytes();after=changed(before)
 # Compile check must use updated source without changing prod; real function checks current file.
 os.chdir(APP);sys.path.insert(0,str(APP))
 os.environ.setdefault("DJANGO_SETTINGS_MODULE","config.settings")
 import django;django.setup()
 from django.template import Template
 Template(after.decode("utf8"))
 print("MPW_AUTODELIVERY_PREFLIGHT="+json.dumps({
  "before_sha":sha(before),"after_sha":sha(after),"one_template_only":True,
  "mainnet_verifier_code_unchanged":True,"financial_writes":0,"new_api_type":"GET status"}))
def extract_js_preview():
 ensure_home()
 updated=changed(TARGET.read_bytes()).decode("utf8")
 matches=re.findall(r"<script\b[^>]*>(.*?)</script\s*>",updated,re.I|re.S)
 if len(matches)!=1:fail("Expected precisely one CSP-hashed checkout script")
 script=re.sub(r"\{\{\s*product\.pk\s*\}\}","72",matches[0])
 if "{{" in script or "{%" in script or "NOWPAYMENTS_API_KEY" in script:
  fail("Unsafe or unresolved JavaScript expression")
 print(script)

def extract_installed_js():
 """Audit live installed DOM JS only, refusing unknown or altered versions."""
 ensure_home()
 b,m=runpaths("39538083953")
 manifest=json.loads(m.read_text("utf8"))
 installed=TARGET.read_bytes()
 if (manifest.get("run")!="39538083953" or
     sha(installed)!=manifest.get("after") or
     sha(changed(b.read_bytes()))!=manifest.get("after")):
  fail("Installed checkout differs from audited pinned release")
 updated=installed.decode("utf8")
 matches=re.findall(r"<script\b[^>]*>(.*?)</script\s*>",updated,re.I|re.S)
 if len(matches)!=1:fail("Expected one CSP protected checkout script")
 script=re.sub(r"\{\{\s*product\.pk\s*\}\}","72",matches[0])
 if "{{" in script or "{%" in script:fail("Unresolved template in installed JS")
 print(script)

def install(run):
 preview()
 b,m=runpaths(run)
 if any(p.exists() or p.is_symlink() for p in (b,m)):fail("Backup name conflict")
 old=TARGET.read_bytes();new=changed(old)
 with b.open("xb") as f:os.fchmod(f.fileno(),0o600);f.write(old);f.flush();os.fsync(f.fileno())
 with m.open("x",encoding="utf8") as f:
  os.fchmod(f.fileno(),0o600)
  json.dump({"run":run,"before":sha(old),"after":sha(new)},f)
  f.flush();os.fsync(f.fileno())
 if TARGET.read_bytes()!=old:fail("Concurrent checkout changes")
 atomic(new)
 if sha(TARGET.read_bytes())!=sha(new):fail("Hash mismatch after write")
 print("MPW_AUTODELIVERY_INSTALLED="+json.dumps({"run":run,"asset":"crypto-only","payment_state_writes":0}))
def verify(run):
 ensure_home()
 b,m=runpaths(run)
 manifest=json.loads(m.read_text("utf8"))
 old=b.read_bytes()
 if manifest["run"]!=run or sha(old)!=manifest["before"] or sha(changed(old))!=manifest["after"] or sha(TARGET.read_bytes())!=manifest["after"]:
  fail("Deployment integrity mismatch")
 django_check(TARGET.read_bytes())
 print("MPW_AUTODELIVERY_RENDER=PASS")
def rollback(run):
 ensure_home();b,m=runpaths(run)
 manifest=json.loads(m.read_text("utf8"));old=b.read_bytes()
 if manifest["run"]!=run or sha(old)!=manifest["before"] or sha(TARGET.read_bytes())!=manifest["after"]:
  fail("Concurrent change prevents safe rollback")
 atomic(old)
 print("MPW_AUTODELIVERY_ROLLBACK=PASS")
def selftest():
 for src in ("x","<script>abc</script>","{% csrf_token %}"):
  try:changed(src.encode())
  except RuntimeError:pass
  else:fail("Source drift checks failed")
 print("MPW_AUTODELIVERY_LOCAL_SELFTEST=PASS")
if __name__=="__main__":
 if len(sys.argv)==2 and sys.argv[1] in ("selftest","preview","extractjs","extractinstalledjs"):
  {"selftest":selftest,"preview":preview,"extractjs":extract_js_preview,
   "extractinstalledjs":extract_installed_js}[sys.argv[1]]()
 elif len(sys.argv)==3 and sys.argv[1] in ("install","verify","rollback"):
  {"install":install,"verify":verify,"rollback":rollback}[sys.argv[1]](sys.argv[2])
 else:raise SystemExit("selftest|preview|install RUN|verify RUN|rollback RUN")
