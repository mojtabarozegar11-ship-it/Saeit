#!/usr/bin/env python3
"""Conservative exact-URI HTML footer enhancement without Passenger or Django reload.

Only the MojPlayWin document root .htaccess receives an appended output filter.
The filter applies to the five exact root-level public routes and serves a small
static JS asset. All existing document content, application code, shared sites,
database, payment handling, and server processes remain unchanged.
"""
import hashlib,json,os,pwd,re,stat,sys,tempfile
from pathlib import Path

HOME=Path("/home/zomorod2")
ROOT=HOME/"mojplaywin.com"
HT=ROOT/".htaccess"
ASSET=ROOT/"design-preview-20261017/static/site/mpw-founder-final-20261018.js"
EXPECTED_HT_SHA="2eb1087587880288219d8212b6785844aa094ed2b2c45aef52f701d82fd59017"
TAG="MPW_FIVE_EXACT_FOOTER_JS_20261018"
ORIGINAL_ROUTES=("/store/","/games/","/ai/","/contact/","/support/")
ASSET_PUBLIC="/design-preview-20261017/static/site/mpw-founder-final-20261018.js"
JS=r"""(function(){
  "use strict";
  var paths = /^(?:\/store\/|\/games\/|\/ai\/|\/contact\/|\/support\/)$/;
  if (!paths.test(window.location.pathname)) return;
  function addFounder(){
    var footers = Array.prototype.filter.call(document.querySelectorAll("footer"),function(node){
      return /MojPlayWin/i.test(node.textContent||"") &&
        (node.classList.contains("mw-site-footer") || node.classList.contains("mpw-footer"));
    });
    var footer=footers.length ? footers[footers.length-1] : null;
    if (!footer || footer.querySelector('[data-mpw-final-founder="true"]') || /Mojtaba Roozegar/.test(footer.textContent||"")) return;
    var name=document.createElement("div");
    name.setAttribute("data-mpw-final-founder","true");
    name.setAttribute("role","note");
    name.textContent="Mojtaba Roozegar";
    name.style.cssText="box-sizing:border-box;grid-column:1/-1;flex-basis:100%;width:100%;display:block;text-align:center;margin-top:12px;padding:16px 10px 6px;border-top:1px solid rgba(218,176,89,.38);font-size:clamp(1.05rem,2vw,1.4rem);font-weight:900;letter-spacing:.065em;color:#f2cb76;text-shadow:0 1px 0 #4b3418,0 2px 0 #241805,0 5px 14px rgba(214,173,85,.55);";
    footer.appendChild(name);
  }
  if(document.readyState==="loading")document.addEventListener("DOMContentLoaded",addFounder,{once:true});
  else addFounder();
})();
"""
BLOCK="""
# BEGIN MPW_FIVE_EXACT_FOOTER_JS_20261018
# Only HTML output for five exact root MojPlayWin routes is filtered.
# No URI rewrite, request-handler substitution or Passenger changes.
<IfModule mod_substitute.c>
<IfModule mod_filter.c>
<If "%{REQUEST_URI} =~ m#^/(store|games|ai|contact|support)/$#">
  AddOutputFilterByType SUBSTITUTE text/html
  Substitute "s|</body>|<script src='/design-preview-20261017/static/site/mpw-founder-final-20261018.js' defer></script></body>|ni"
</If>
</IfModule>
</IfModule>
# END MPW_FIVE_EXACT_FOOTER_JS_20261018
"""
def sha(data):return hashlib.sha256(data).hexdigest()
def safeid(runid):
    if not re.fullmatch(r"[0-9]{9,20}",runid):raise RuntimeError("Invalid run ID")
    return runid
def homepath(runid):return HOME/(".mpw-five-footer-"+safeid(runid))
def guard():
    if pwd.getpwuid(os.getuid()).pw_name!="zomorod2":raise RuntimeError("Unexpected account")
    if not ROOT.is_dir() or ROOT.is_symlink():raise RuntimeError("Unsafe docroot")
    if not ASSET.parent.is_dir() or ASSET.parent.is_symlink():raise RuntimeError("Missing static directory")
    if not HT.is_file() or HT.is_symlink():raise RuntimeError("Unsafe .htaccess")
    wsgi=ROOT/"passenger_wsgi.py"
    if not wsgi.is_file() or wsgi.is_symlink() or "Saeit-staging" not in wsgi.read_text(errors="replace"):
        raise RuntimeError("App mapping changed")
    original=HT.read_bytes()
    if sha(original)!=EXPECTED_HT_SHA:raise RuntimeError("Current routing SHA differs; stop")
    if TAG.encode() in original:raise RuntimeError("Footer rule already present")
    if ASSET.exists() or ASSET.is_symlink():raise RuntimeError("JS file already exists")
    if b"PassengerStartupFile" not in original or b"RewriteRule" not in original:
        raise RuntimeError("Expected routing structure absent")
    return original
def atomic(p,data,mode,allow_create=False):
    if p.is_symlink():raise RuntimeError("Symlink")
    if not allow_create and not p.is_file():raise RuntimeError("Not a file")
    fd,tmp=tempfile.mkstemp(prefix=".mpw-five-footer-",dir=p.parent)
    try:
        os.fchmod(fd,mode)
        with os.fdopen(fd,"wb") as f:
            f.write(data);f.flush();os.fsync(f.fileno())
        os.replace(tmp,p)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)
def install(runid):
    old=guard()
    target=homepath(runid)
    if target.exists() or target.is_symlink():raise RuntimeError("Backup collision")
    target.mkdir(mode=0o700)
    before=target/"original.htaccess"
    with before.open("xb") as f:f.write(old);f.flush();os.fsync(f.fileno())
    os.chmod(before,0o600)
    mode=stat.S_IMODE(HT.stat().st_mode)
    after=old+BLOCK.encode()
    metadata={"before":sha(old),"after":sha(after),"asset":sha(JS.encode()),"mode":mode,"tag":TAG}
    (target/"manifest.json").write_text(json.dumps(metadata),encoding="utf8")
    os.chmod(target/"manifest.json",0o600)
    try:
        if sha(HT.read_bytes())!=metadata["before"]:raise RuntimeError("Concurrent route change")
        atomic(ASSET,JS.encode(),0o644,allow_create=True)
        if sha(ASSET.read_bytes())!=metadata["asset"]:raise RuntimeError("Asset verification mismatch")
        atomic(HT,after,mode)
        if sha(HT.read_bytes())!=metadata["after"]:raise RuntimeError("Routing checksum mismatch")
    except Exception:
        if HT.is_file() and not HT.is_symlink() and sha(HT.read_bytes())==metadata["after"]:
            atomic(HT,old,mode)
        if ASSET.is_file() and not ASSET.is_symlink() and sha(ASSET.read_bytes())==metadata["asset"]:
            ASSET.unlink()
        (target/"FAILED").write_text("safely stopped")
        raise
    (target/"INSTALLED").write_text("yes")
    print("MPW_EXACT_5_FOOTER_INSTALLED=true PASSENGER_RESTART=false BACKUP="+str(target),flush=True)
def rollback(runid):
    folder=homepath(runid)
    if not folder.is_dir() or folder.is_symlink():raise RuntimeError("No backup")
    m=json.loads((folder/"manifest.json").read_text())
    original=(folder/"original.htaccess").read_bytes()
    if sha(original)!=m["before"]:raise RuntimeError("Backup corrupted")
    present=HT.read_bytes()
    if sha(present)==m["before"]:
        print("ROUTE_ALREADY_ORIGINAL",flush=True)
    elif sha(present)==m["after"]:
        atomic(HT,original,m["mode"])
    else:
        raise RuntimeError("Concurrent .htaccess edit: refuse dangerous rollback")
    if ASSET.exists():
        if ASSET.is_symlink() or sha(ASSET.read_bytes())!=m["asset"]:raise RuntimeError("Asset changed: refuse deletion")
        ASSET.unlink()
    (folder/"ROLLED_BACK").write_text("yes")
    print("MPW_5_FOOTERS_ROLLBACK=OK",flush=True)
def selftest():
    assert len(ORIGINAL_ROUTES)==5
    assert all(re.fullmatch(r"/(?:store|games|ai|contact|support)/",p) for p in ORIGINAL_ROUTES)
    assert "Mojtaba Roozegar" in JS
    assert "querySelectorAll(\"footer\")" in JS
    assert "<script src=" in BLOCK and "Substitute" in BLOCK
    assert BLOCK.count("BEGIN "+TAG)==1 and BLOCK.count("END "+TAG)==1
    assert len(EXPECTED_HT_SHA)==64 and not any(s in BLOCK for s in ("/farnaz/","/saman/","/picm/"))
    print("MPW_FOOTER_FILTER_SELFTEST=PASS")
if __name__=="__main__":
    arg=sys.argv[1] if len(sys.argv)>1 else ""
    if arg=="selftest":selftest()
    elif arg=="audit":
        raw=guard()
        print("MPW_FOOTER_FILTER_PREFLIGHT=PASS existing_bytes="+str(len(raw)))
    elif arg=="install" and len(sys.argv)==3:install(sys.argv[2])
    elif arg=="rollback" and len(sys.argv)==3:rollback(sys.argv[2])
    else:raise SystemExit("selftest|audit|install RUN_ID|rollback RUN_ID")
