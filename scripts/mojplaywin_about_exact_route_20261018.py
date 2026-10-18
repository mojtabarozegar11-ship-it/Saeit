#!/usr/bin/env python3
"""Exactly one Apache GET /about/ rewrite, transactional and reversible.

Run remotely on authorized cPanel only. Never restarts Passenger or touches
shared Django, subsite directories, product/order/payment or the database.
"""
import hashlib, json, os, re, shutil, stat, sys, tempfile
from pathlib import Path

ROOT=Path("/home/zomorod2/mojplaywin.com")
HOME=ROOT.parent
RULE_MARKER="# MPW_EXACT_ABOUT_80_20_20261018"
STATIC_REL="design-preview-20261017/complete-about-20261018.html"
EXPECTED_ROOT_SHA="5886985a2bb92578c26c05b74568a34a99d128eb505827a799773876a5e17a30"
SUFFICIENT_MARKERS=("MPW_ABOUT_RESEARCH_80_20_V1", "SPECIALISM 28", "COMPLEMENTARY SPECIALISM 30", "Original by Default")
RULE=(RULE_MARKER+"\n"
      "RewriteCond %{REQUEST_METHOD} ^GET$\n"
      "RewriteCond %{REQUEST_URI} ^/about/$\n"
      "RewriteRule ^about/$ /"+STATIC_REL+" [END,QSD]\n")

def digest(data):return hashlib.sha256(data).hexdigest()
def die(message):raise RuntimeError(message)
def paths(runid):
    if not re.fullmatch(r"[0-9]{9,20}",runid):die("Unsafe run ID")
    return (HOME/f".mpw-about-stage-{runid}.html",
            HOME/f".mpw-about-rollback-{runid}",
            ROOT/STATIC_REL,ROOT/".htaccess")
def secure_atomic(p,data,mode=0o644):
    if p.is_symlink():die("Unexpected target symlink")
    fd,tmp=tempfile.mkstemp(prefix=".mpw-about-",dir=p.parent)
    try:
        os.fchmod(fd,mode)
        with os.fdopen(fd,"wb") as f:
            f.write(data);f.flush();os.fsync(f.fileno())
        os.replace(tmp,p)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)
def precheck(ht,static):
    if not ROOT.is_dir() or ROOT.is_symlink() or ROOT.resolve()!=ROOT:die("Docroot mismatch")
    if not ht.is_file() or ht.is_symlink():die("Unsafe root htaccess")
    current=ht.read_bytes()
    if digest(current)!=EXPECTED_ROOT_SHA:die("Root rewrite rules have changed since read-only evidence; refusing deployment")
    if not (ROOT/"design-preview-20261017").is_dir():die("Missing known static preview directory")
    if static.exists() or static.is_symlink():die("Static About file already exists; refusing overwrite")
    if RULE_MARKER.encode() in current:die("About rule already installed")
    if re.search(br"^RewriteEngine\s+On\s*$",current,re.M|re.I) is None:die("RewriteEngine not found")
    if b"/about/" in current:die("Existing /about/ route special-case; update needs review")
    return current
def install(runid,sha):
    stage,backup,target,ht=paths(runid)
    if not re.fullmatch(r"[0-9a-f]{64}",sha):die("Bad SHA")
    original=precheck(ht,target)
    if not stage.is_file() or stage.is_symlink():die("Expected private staged content absent")
    data=stage.read_bytes()
    if digest(data)!=sha:die("Staged content digest mismatch")
    if len(data)<50_000 or len(data)>700_000:die("Content size outside 50KB - 700KB")
    for marker in SUFFICIENT_MARKERS:
        if marker.encode() not in data:die("Missing specialist content marker: "+marker)
    if backup.exists() or backup.is_symlink():die("Rollback directory already exists")
    inserted = original.replace(b"RewriteEngine On",b"RewriteEngine On\n"+RULE.encode(),1)
    if inserted==original or inserted.count(RULE_MARKER.encode())!=1:die("Could not create exactly one rule")
    if inserted.replace(b"\n"+RULE.encode(),b"",1)!=original:die("Exact patch reversibility check failed")
    # Verify rule does not match /about/mojtaba-rozegar/, any child path,
    # any other request method, or any protected prefix.
    regex=re.compile(r"^/about/$")
    assert regex.fullmatch("/about/") and not regex.fullmatch("/about/mojtaba-rozegar/")
    for route in ("/store/","/checkout/","/mojtaba.roozegar/","/farnaz/","/saman/","/picm/"):
        if regex.fullmatch(route):die("Unsafe route matcher")
    backup.mkdir(mode=0o700)
    (backup/"original.htaccess").write_bytes(original)
    (backup/"about.original.sha256").write_text(digest(original)+"\n")
    (backup/"manifest.json").write_text(json.dumps({"runid":runid,"ht_sha_before":digest(original),"ht_sha_installed":digest(inserted),"page_sha":sha,"rule":RULE_MARKER}))
    try:
        secure_atomic(target,data,0o644)
        if digest(target.read_bytes())!=sha:die("Static file verification failed")
        secure_atomic(ht,inserted,stat.S_IMODE(ht.stat().st_mode))
        if digest(ht.read_bytes())!=digest(inserted):die("Rewrite patch digest validation failed")
    except BaseException:
        # Local rollback on a partial failure; never restore over external changes.
        if ht.exists() and digest(ht.read_bytes())==digest(inserted):
            secure_atomic(ht,original,stat.S_IMODE(ht.stat().st_mode))
        if target.is_file() and not target.is_symlink() and digest(target.read_bytes())==sha:target.unlink()
        (backup/"FAILED").write_text("failed\n")
        raise
    stage.unlink()
    print(json.dumps({"result":"installed-exact-GET-only","runid":runid,"page_bytes":len(data),"page_sha256":sha,"ht_before":digest(original),"ht_after":digest(inserted),"protected_routes_unchanged_by_rule":True,"passenger_restarted":False}))
def rollback(runid):
    stage,backup,target,ht=paths(runid)
    if not backup.is_dir() or backup.is_symlink():die("Backup directory missing")
    data=(backup/"original.htaccess").read_bytes()
    manifest=json.loads((backup/"manifest.json").read_text())
    if digest(data)!=manifest["ht_sha_before"] or digest(data)!=EXPECTED_ROOT_SHA:die("Rollback source corrupt")
    actual=digest(ht.read_bytes()) if ht.is_file() and not ht.is_symlink() else ""
    if actual==manifest["ht_sha_installed"]:
        secure_atomic(ht,data,stat.S_IMODE(ht.stat().st_mode))
    elif actual!=digest(data):
        die("Unknown concurrent root .htaccess edit; do not overwrite")
    if target.is_file() and not target.is_symlink() and digest(target.read_bytes())==manifest["page_sha"]:
        target.unlink()
    if stage.is_file() and not stage.is_symlink():stage.unlink()
    (backup/"ROLLED_BACK").write_text("yes\n")
    print(json.dumps({"result":"restored-original-about-route","ht_sha256":digest(ht.read_bytes()),"preview_file_deleted":not target.exists()}))
def status(runid):
    stage,backup,target,ht=paths(runid)
    manifest=json.loads((backup/"manifest.json").read_text()) if (backup/"manifest.json").is_file() else {}
    ht_sha=digest(ht.read_bytes()) if ht.is_file() and not ht.is_symlink() else None
    page_sha=digest(target.read_bytes()) if target.is_file() and not target.is_symlink() else None
    print(json.dumps({"result":"read-only-status","runid":runid,"ht_sha256":ht_sha,"static_exists":bool(page_sha),"static_sha256":page_sha,"is_installed":ht_sha==manifest.get("ht_sha_installed") and page_sha==manifest.get("page_sha"),"is_rolled_back":ht_sha==EXPECTED_ROOT_SHA}))
if __name__=="__main__":
    if len(sys.argv)<3:die("Usage mode RUNID [SHA]")
    mode,runid=sys.argv[1:3]
    if mode=="install" and len(sys.argv)==4:install(runid,sys.argv[3])
    elif mode=="rollback" and len(sys.argv)==3:rollback(runid)
    elif mode=="status" and len(sys.argv)==3:status(runid)
    else:die("Invalid mode")
