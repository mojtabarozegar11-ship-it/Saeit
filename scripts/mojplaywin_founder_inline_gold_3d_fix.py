#!/usr/bin/env python3
"""Correct founder text placement in already-published MojPlayWin static pages.

Exact scope: production-home-20261017.html currently routed at /
and 22 noindex static design-preview HTML pages in the same directory.
Move signature INSIDE the first footer brand column, remove external-looking
boxed founder tile, add genuinely layered 3D metallic gold text.
Never modify .htaccess, Django, Passenger, other sites, payments or products.
Preflight all files before first write; verified backups, atomic writes and
independent automatic rollback are mandatory.
"""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path("/home/zomorod2/mojplaywin.com")
FOLDER = ROOT / "design-preview-20261017"
PROD = FOLDER / "production-home-20261017.html"
HT = ROOT / ".htaccess"
BACKUP_ROOT = Path("/home/zomorod2/.mpw-founder-inline3d-backups")
PROD_SHA = "caa94d5d998095bed802cd1bf6d48c7bed9f5d5ee6424139677e8557a74a4f4d"
HT_SHA = "5886985a2bb92578c26c05b74568a34a99d128eb505827a799773876a5e17a30"
MARKER = 'data-mpw-inline-gold-3d="true"'
NEW_STYLE = """<style id="mpw-footer-gold-3d-inline-v2">
.mw-site-footer .mpw-footer-founder-inline{display:block;margin:16px 0 0;padding:0!important;border:0!important;border-radius:0!important;background:none!important;box-shadow:none!important;max-width:100%;text-align:start}
.mw-site-footer .mpw-footer-founder-inline .mpw-gold-3d{position:relative;isolation:isolate;display:inline-block;font-family:Georgia,'Times New Roman',serif;font-size:clamp(1.2rem,2.2vw,1.85rem);font-weight:900;line-height:1.35;letter-spacing:.04em;color:#f6d57b;background:linear-gradient(180deg,#fffbe2 0%,#f9de8f 16%,#d9a640 38%,#fff3b6 48%,#ad7117 71%,#f7d880 100%);-webkit-background-clip:text;background-clip:text;-webkit-text-fill-color:transparent;filter:drop-shadow(0 3px 2px rgba(0,0,0,.5))}
.mw-site-footer .mpw-footer-founder-inline .mpw-gold-3d::before{content:attr(data-text);position:absolute;inset:0;z-index:-1;transform:translate(2px,3px);color:#86551b;-webkit-text-fill-color:#86551b;background:none;text-shadow:1px 1px 0 #8e631f,2px 2px 0 #77501b,3px 3px 0 #5e3d14,5px 7px 8px rgba(0,0,0,.7)}
@media(max-width:560px){.mw-site-footer .mpw-footer-founder-inline .mpw-gold-3d{font-size:1.3rem;letter-spacing:.015em}}
@media(prefers-reduced-motion:reduce){.mw-site-footer .mpw-footer-founder-inline .mpw-gold-3d{animation:none;transition:none}}
</style>"""
NEW_LINE = '<p class="mpw-footer-founder-inline" data-mpw-inline-gold-3d="true" aria-label="Mojtaba Roozegar"><strong class="mpw-gold-3d" data-text="Mojtaba Roozegar">Mojtaba Roozegar</strong></p>'
OLD_STYLE = re.compile(r'<style id="mpw-(?:root|preview)-founder-style">.*?</style>',re.I|re.S)
OLD_TILE = re.compile(r'<div class="mpw-(?:root|preview)-founder" data-mpw-(?:root|preview)-founder-20261018="true" aria-label="Founder: Mojtaba Roozegar"><strong>Mojtaba Roozegar</strong></div>',re.I)
BRAND_FIRST = re.compile(r'(<footer\b[^>]*class="mw-site-footer"[^>]*>\s*<div>\s*<strong>MojPlayWin</strong>.*?<p>Play\. Build\. Evolve\.</p>)\s*(</div>)', re.I|re.S)

def sha(data): return hashlib.sha256(data).hexdigest()

def paths():
    if ROOT.is_symlink() or FOLDER.is_symlink() or not ROOT.is_dir() or not FOLDER.is_dir():
        raise RuntimeError("unexpected site directories")
    if HT.is_symlink() or not HT.is_file() or sha(HT.read_bytes()) != HT_SHA:
        raise RuntimeError("production routing changed")
    if BACKUP_ROOT.is_symlink(): raise RuntimeError("backup root symlink")
    page_paths = sorted(x for x in FOLDER.iterdir()
        if x.name.endswith(".html") and not x.is_symlink() and x.is_file()
        and "noindex,nofollow,noarchive" in x.read_text(encoding="utf-8"))
    if len(page_paths)!=22 or PROD in page_paths or PROD.is_symlink() or not PROD.is_file():
        raise RuntimeError("independent preview scope changed")
    if sha(PROD.read_bytes())!=PROD_SHA:
        raise RuntimeError("live production root file changed")
    if sum(x.name=="index.html" for x in page_paths)!=1:
        raise RuntimeError("missing original preview home")
    return [PROD]+page_paths

def rewrite(raw,is_prod):
    if len(raw)>900000 or len(raw)<4000:raise RuntimeError("unexpected original page length")
    doc=raw.decode("utf-8")
    if MARKER in doc or doc.count("</head>")!=1 or doc.count("</footer>")!=1:
        raise RuntimeError("document edited or footer topology changed")
    if is_prod:
        if "MJWP_ROOT_CANDIDATE_ONLY_20261017" not in doc or "noindex,nofollow,noarchive" in doc:
            raise RuntimeError("main production root identity or indexability changed")
        if 'data-mpw-root-founder-20261018="true"' not in doc:
            raise RuntimeError("root original founder missing")
    else:
        if "noindex,nofollow,noarchive" not in doc or 'data-mpw-preview-founder-20261018="true"' not in doc:
            raise RuntimeError("preview identity or original founder missing")
    doc,n1=OLD_STYLE.subn(NEW_STYLE,doc,count=1)
    doc,n2=OLD_TILE.subn("",doc,count=1)
    if n1!=1 or n2!=1:raise RuntimeError("boxed founder CSS/HTML not uniquely identifiable")
    brand=BRAND_FIRST.search(doc)
    if brand is None:raise RuntimeError("brand footer first column absent")
    point=brand.start(2)
    doc=doc[:point]+NEW_LINE+"\n"+doc[point:]
    if doc.count(MARKER)!=1 or doc.count(NEW_LINE)!=1:
        raise RuntimeError("new founder markup missing or repeated")
    footer_at=doc.find('<footer')
    first_div_end=doc.find('</div>',footer_at)
    if footer_at < 0 or first_div_end < footer_at:
        raise RuntimeError("footer brand column topology lost")
    if NEW_LINE not in doc[footer_at:first_div_end]:
        raise RuntimeError("founder not integrated within footer FIRST brand column")
    if OLD_TILE.search(doc) or OLD_STYLE.search(doc):
        raise RuntimeError("old floating founder tile still present")
    return doc.encode("utf-8")

def atomic(path,blob,run):
    temp=path.parent/(".mpw-founder-3d-"+run+"-"+path.name+".tmp")
    fd=os.open(temp,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
    try:
        with os.fdopen(fd,"wb") as out:
            out.write(blob);out.flush();os.fsync(out.fileno())
        os.chmod(temp,0o644)
        os.replace(temp,path)
    finally:
        if temp.exists():temp.unlink()

def runpath(run):
    if not re.fullmatch(r"[0-9]{8,14}",run):raise RuntimeError("invalid release run")
    return BACKUP_ROOT/("run-"+run)

def statewrite(directory,record,run):
    p=directory/("state-"+run+".tmp")
    fd=os.open(p,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
    with os.fdopen(fd,"w") as out:
        json.dump(record,out,sort_keys=True);out.flush();os.fsync(out.fileno())
    os.replace(p,directory/"state.json")

def stateget(directory,run):
    obj=json.loads((directory/"state.json").read_text())
    if obj["run"]!=run or len(obj["files"])!=23:
        raise RuntimeError("unexpected restore manifest")
    return obj

def rollback(run):
    folder=runpath(run)
    state=stateget(folder,run)
    for name,meta in state["files"].items():
        if Path(name).name!=name:raise RuntimeError("invalid backup entry")
        file=FOLDER/name
        raw=(folder/name).read_bytes()
        if sha(raw)!=meta["old"] or file.is_symlink():raise RuntimeError("backup integrity or file type changed")
        current=sha(file.read_bytes())
        if current not in {meta["old"],meta["new"]}:raise RuntimeError("concurrent site modification")
        if current==meta["new"]:atomic(file,raw,run)
    state["phase"]="rolled_back"
    statewrite(folder,state,run)
    print(json.dumps({"status":"MojPlayWin-inline-footer-restored","count":23,"shared_services_modified":False},sort_keys=True))

def install(run):
    originals=paths()
    candidates={}
    for file in originals:
        original=file.read_bytes()
        candidates[file.name]=(original,rewrite(original,file==PROD))
    backup=runpath(run)
    if backup.exists():raise RuntimeError("previous release state exists")
    BACKUP_ROOT.mkdir(mode=0o700,exist_ok=True)
    os.chmod(BACKUP_ROOT,0o700)
    backup.mkdir(mode=0o700)
    state={"run":run,"phase":"armed","files":{}}
    for name,(old,new) in candidates.items():
        dest=backup/name
        fd=os.open(dest,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
        with os.fdopen(fd,"wb") as out:out.write(old);out.flush();os.fsync(out.fileno())
        if sha(dest.read_bytes())!=sha(old):raise RuntimeError("backup verification failure")
        state["files"][name]={"old":sha(old),"new":sha(new)}
    statewrite(backup,state,run)
    watchdog='''import json,hashlib,os,sys,time
from pathlib import Path
time.sleep(360)
folder=Path(sys.argv[1]);site=Path(sys.argv[2])
try:
 s=json.loads((folder/"state.json").read_text())
 if s.get("phase")!="armed":raise SystemExit
 for name,hashes in s["files"].items():
  original=(folder/name).read_bytes()
  target=site/name
  digest=lambda blob:hashlib.sha256(blob).hexdigest()
  if digest(original)!=hashes["old"] or target.is_symlink():continue
  if digest(target.read_bytes())!=hashes["new"]:continue
  temp=site/(".mpw-founder-watchdog-"+name)
  fd=os.open(temp,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
  with os.fdopen(fd,"wb") as f:f.write(original);f.flush();os.fsync(f.fileno())
  os.chmod(temp,0o644);os.replace(temp,target)
 s["phase"]="watchdog_rolled_back"
 (folder/"state.json").write_text(json.dumps(s,sort_keys=True))
except Exception:pass
'''
    wp=backup/"watchdog.py"
    wp.write_text(watchdog);os.chmod(wp,0o600)
    proc=subprocess.Popen([sys.executable,str(wp),str(backup),str(FOLDER)],
        stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True)
    os.kill(proc.pid,0)
    try:
        for name,(_,blob) in candidates.items():
            atomic(FOLDER/name,blob,run)
            if sha((FOLDER/name).read_bytes())!=state["files"][name]["new"]:
                raise RuntimeError("installed checksum mismatch")
    except Exception:
        rollback(run)
        raise
    print(json.dumps({"status":"inline-3d-gold-pending-public-verification",
      "count":23,"root_unchanged_except_founder":True,"passenger_restart":False,
      "child_sites_modified":False,"gold_panel_removed":True},sort_keys=True))

def commit(run):
    folder=runpath(run)
    state=stateget(folder,run)
    if state["phase"]!="armed":raise RuntimeError("release not armed")
    if sha(HT.read_bytes())!=HT_SHA:raise RuntimeError("routing changed during release")
    for name,rec in state["files"].items():
        if sha((FOLDER/name).read_bytes())!=rec["new"]:
            raise RuntimeError("file drift detected before commit")
    state["phase"]="committed"
    statewrite(folder,state,run)
    print(json.dumps({"status":"inline-3d-gold-founder-23-pages-committed",
        "count":23,"private_backups_retained":True,"passenger_restarted":False},sort_keys=True))

if __name__=="__main__":
    try:
        if len(sys.argv)!=3:raise RuntimeError("invalid arguments")
        mode,run=sys.argv[1:]
        if mode=="install":install(run)
        elif mode=="rollback":rollback(run)
        elif mode=="commit":commit(run)
        else:raise RuntimeError("invalid mode")
    except Exception as ex:
        print(json.dumps({"status":"inline-founder-fail-closed",
            "exception_type":type(ex).__name__,
            "production_routing_changed":False},sort_keys=True))
        raise SystemExit(1)
