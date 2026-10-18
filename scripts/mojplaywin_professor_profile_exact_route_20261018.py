#!/usr/bin/env python3
"""Exact-GET MojPlayWin CEO profile only; atomic install & fail-closed rollback."""
import hashlib,json,os,re,stat,sys,tempfile
from pathlib import Path
ROOT=Path("/home/zomorod2/mojplaywin.com")
HT=ROOT/".htaccess"
PAGE=ROOT/"design-preview-20261017/professor-mojtaba-roozegar-20261018.html"
EXPECTED_HT="723bb8ba5de87725bc6f1865d895a6407aae55dca4588a16bc8708a5154b6d6d"
MARKER="# MPW_EXACT_LEADERSHIP_ROOZEGAR_20261018"
RULE=(MARKER+"\n"+
      "RewriteCond %{REQUEST_METHOD} ^GET$\n"+
      "RewriteCond %{REQUEST_URI} ^/about/mojtaba-rozegar/$\n"+
      "RewriteRule ^about/mojtaba-rozegar/$ /design-preview-20261017/professor-mojtaba-roozegar-20261018.html [END,QSD]\n")
PRESENT_MARKERS=("MOJPLAYWIN_PROFESSOR_MOJTabA_ROOZEGAR_PROFILE_20261018",
     "Professor Mojtaba Roozegar","Universiti Putra Malaysia",
     "Production Economics and Farm Management",
     "official_profile_20261016/portrait.2935ce8cb70d.webp")
def sha(x):return hashlib.sha256(x).hexdigest()
def fail(s):raise RuntimeError(s)
def validrun(s):
    if not re.fullmatch(r"[0-9]{9,20}",s):fail("Invalid run")
    return s
def stagepath(run):return ROOT.parent/(".mpw-professor-stage-"+validrun(run)+".html")
def backdir(run):return ROOT.parent/(".mpw-professor-rollback-"+validrun(run))
def atomic(path,blob,mode):
    if path.is_symlink():fail("Unexpected symlink")
    fd,t=tempfile.mkstemp(dir=path.parent,prefix=".mpw-professor-")
    try:
      os.fchmod(fd,mode)
      with os.fdopen(fd,"wb") as f:
        f.write(blob);f.flush();os.fsync(f.fileno())
      os.replace(t,path)
    finally:
      if os.path.exists(t):os.unlink(t)
def deploy(run,digest):
    stage=stagepath(run);bk=backdir(run)
    if not re.fullmatch(r"[a-f0-9]{64}",digest):fail("Incorrect digest")
    if not ROOT.is_dir() or ROOT.is_symlink():fail("Docroot safety check failed")
    if not HT.is_file() or HT.is_symlink():fail("Htaccess unsafe")
    before=HT.read_bytes()
    if sha(before)!=EXPECTED_HT:fail("Root rewrite changed since preflight")
    if not (ROOT/"design-preview-20261017").is_dir():fail("Static source directory missing")
    if PAGE.exists() or PAGE.is_symlink():fail("Profile asset exists; refuse overwrite")
    if bk.exists() or bk.is_symlink():fail("Backup already exists")
    if not stage.is_file() or stage.is_symlink():fail("Staged profile missing")
    profile=stage.read_bytes()
    if sha(profile)!=digest or not (12000<len(profile)<130000):fail("Bad profile payload")
    for mark in PRESENT_MARKERS:
      if mark.encode() not in profile:fail("Profile evidence absent")
    if re.search(br"^RewriteEngine On\s*$",before,re.M|re.I) is None:fail("No RewriteEngine")
    if b"MPW_EXACT_ABOUT_80_20_20261018" not in before:fail("Existing 80/20 About rewrite missing")
    if MARKER.encode() in before:fail("Profile already installed")
    after=before.replace(b"RewriteEngine On",b"RewriteEngine On\n"+RULE.encode(),1)
    if after.replace(b"\n"+RULE.encode(),b"",1)!=before:fail("Not reversible")
    # Single exact path. A sibling or its parent must never match.
    matcher=re.compile(r"^/about/mojtaba-rozegar/$")
    if not matcher.fullmatch("/about/mojtaba-rozegar/"):fail("Target matcher defective")
    for path in ("/","/about/","/store/","/checkout/","/mojtaba.roozegar/",
                 "/about/mojtaba-rozegar/more/","/farnaz/","/picm/","/saman/","/studio.Roham/"):
      if matcher.fullmatch(path):fail("Protected path matched")
    bk.mkdir(mode=0o700)
    (bk/"original.htaccess").write_bytes(before)
    (bk/"manifest.json").write_text(json.dumps(
      {"ht_before":sha(before),"ht_after":sha(after),"page_sha":digest,"filename":PAGE.name,"route":"/about/mojtaba-rozegar/"}))
    try:
      atomic(PAGE,profile,0o644)
      if sha(PAGE.read_bytes())!=digest:fail("Profile write verification mismatch")
      atomic(HT,after,stat.S_IMODE(HT.stat().st_mode))
      if sha(HT.read_bytes())!=sha(after):fail("Rewrite checksum mismatch")
    except BaseException:
      if HT.is_file() and sha(HT.read_bytes())==sha(after):
        atomic(HT,before,stat.S_IMODE(HT.stat().st_mode))
      if PAGE.is_file() and not PAGE.is_symlink() and sha(PAGE.read_bytes())==digest:
        PAGE.unlink()
      (bk/"INSTALL_FAILED").write_text("yes\n")
      raise
    stage.unlink()
    print(json.dumps({"status":"PROFESSOR_PROFILE_LIVE_INSTALLED",
      "route":"/about/mojtaba-rozegar/","page_sha":digest,"ht_before":sha(before),
      "ht_after":sha(after),"rollback_present":True,
      "passenger_restarted":False,"payments_untouched":True,"protected_paths_unmatched":True}))
def rollback(run):
    bk=backdir(run)
    if not bk.is_dir() or bk.is_symlink():fail("Rollback folder missing")
    manifest=json.loads((bk/"manifest.json").read_text())
    before=(bk/"original.htaccess").read_bytes()
    if sha(before)!=EXPECTED_HT or sha(before)!=manifest["ht_before"]:fail("Rollback source changed")
    if not HT.is_file() or HT.is_symlink():fail("Current htaccess unsafe")
    current=HT.read_bytes()
    if sha(current)==manifest["ht_after"]:
      atomic(HT,before,stat.S_IMODE(HT.stat().st_mode))
    elif sha(current)!=EXPECTED_HT:
      fail("Concurrent rewrite edit: do not overwrite unknown data")
    if PAGE.is_file() and not PAGE.is_symlink() and sha(PAGE.read_bytes())==manifest["page_sha"]:
      PAGE.unlink()
    staged=stagepath(run)
    if staged.is_file() and not staged.is_symlink():staged.unlink()
    (bk/"ROLLED_BACK").write_text("yes\n")
    print(json.dumps({"status":"PROFESSOR_ROLLED_BACK","ht_sha":sha(HT.read_bytes()),"asset_deleted":not PAGE.exists()}))
if __name__=="__main__":
    if len(sys.argv)<3:fail("install RUNID SHA or rollback RUNID")
    if sys.argv[1]=="install" and len(sys.argv)==4:deploy(sys.argv[2],sys.argv[3])
    elif sys.argv[1]=="rollback" and len(sys.argv)==3:rollback(sys.argv[2])
    else:fail("Invalid arguments")
