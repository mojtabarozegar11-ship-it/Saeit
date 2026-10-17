#!/usr/bin/env python3
"""Main-site footer ACTUAL LAST LINE: move gold name into existing copyright bar.

The original .mpx-bottom-bar was a sibling AFTER </footer>, so previous signature
was physically one line too high. Move the existing copyright bar inside footer
without changing its copyright strings, then add the founder as the final span.
23 pinned static main-owned pages only; protected sites, Django, Passenger,
products/payment, and .htaccess never touched.
"""
from pathlib import Path
import hashlib
import json
import os
import re
import subprocess
import sys

ROOT=Path("/home/zomorod2/mojplaywin.com")
FOLDER=ROOT/"design-preview-20261017"
PROD=FOLDER/"production-home-20261017.html"
HT=ROOT/".htaccess"
BACKUP_ROOT=Path("/home/zomorod2/.mpw-founder-copyright-final-backups")
HT_SHA="5886985a2bb92578c26c05b74568a34a99d128eb505827a799773876a5e17a30"
MARKER='data-mpw-copyright-founder="true"'
EXPECTED={
  "agents.html": "c0f2bc33c6ada9a4f0ec7a29bb73cf8161bb9b9e302c807f778e7551bfb05b19",
  "ai.html": "5dd48b9d83f10c411a44a6ea90a922791fab2ece95a8782555af0410d783c92a",
  "blockchain.html": "60c6800fe8e9cac7afc113d7133f86d190b6669beca1a6de73778e2c4ec37d6a",
  "company.html": "37f0604640c63201a6d94ec78f3c2f50dc41c7af7afc4ac8ccf2ff9da27a898f",
  "economy.html": "ebe10d9e5bf8e54ddccd4b6f8e1d98f710dea3d5c266897fc9a66578aef71cc1",
  "index.html": "c286420b91a6a457ec8c55e292431f4ceab8d778e8755624e8fe752b0a3afc01",
  "industry.html": "7cb20861397e5e78455f518ed97a4c491daf1c8ed7485f234366091e6b46e2b3",
  "knowledge.html": "dd186b132c9a8d530e56695c0871db2e74973ac566e426c4dcf6f8ebbc956c73",
  "market.html": "546fc4219639391ca87950157b1ab8e81e55db0a152d974ccff03cd1dc1a8341",
  "production-home-20261017.html": "8e2aaf8d383ab059a21db0be4ba7cb529081e0734c271f6ece42df3f0a1f56da",
  "research.html": "1075d620bf80e3f78c71fb7685f578bc94578a049fd185502c159370b165f6e5",
  "restaurant.html": "1e1cd3ce99abaf6adb7a61a1f60c02f76b15a04445b0b26d9a8ef150095dc52d",
  "store.html": "9d34a96d8ee5d1940b7316497553c763efa05c7b66aaf7c38f001793014fd431",
  "studio.html": "60c75d531046131ae4a1eceb6cb9aafe0858b7508e2cbd72c31444e058875a4a",
  "support.html": "db876c15d98cffa40ac55f2adb30b8f75a8c47d9365af0eeb6c0201035b8ef9e",
  "venture_agriculture.html": "e0479f90acb6e272925db8b437d9def63bf70b48d070e71896d349f9f4b5774c",
  "venture_carpets.html": "64bb29e2f2705b158b063e6ab9f1f914af3140273fc7d5d6254fae4cd6f63d74",
  "venture_crypto.html": "7ba02262f381d16af78ed4d17859d3738d5ccee5ec29fc22c5d3056f976c8cdd",
  "venture_ecommerce.html": "a4da5e08add7e928bdaf7a4c3f88e1f2a4a10d3d7d4db0887bd9b6807627dea8",
  "venture_fuel_station.html": "78cb526d01db6f57d5f9409e0b6a0f6a2978d1acd0d663a47fb883461a3c0885",
  "venture_hospitality.html": "eb492f352ac9c04aa93f2b902f3acdea433bc83789e0a441324fc7b3290a058a",
  "venture_jewelry_gold.html": "8673f4115c0219fe37016a7c3fe298ee76d17abe8c6f128b6d586a22d8cea131",
  "web_engineering.html": "b2291c7615ba80f5c2245bce0325bb823099535be15091c60fcd8253ce80a2e6"
}
NEW_STYLE="""<style id="mpw-copyright-final-gold-v4">
.mw-site-footer>.mpx-bottom-bar{
 grid-column:1/-1!important;grid-row:auto!important;align-self:end;
 width:100%;max-width:none;margin:14px 0 0!important;padding:13px 0 4px!important;
 display:flex!important;align-items:center;justify-content:center;gap:.55rem 1.5rem;
 flex-wrap:wrap;min-width:0;border:0;border-top:1px solid rgba(201,162,82,.20);
 background:transparent!important;box-shadow:none!important;border-radius:0;
 color:rgba(237,224,196,.76);font-size:.81rem;line-height:1.45;text-align:center;
}
.mw-site-footer>.mpx-bottom-bar>.mpw-copyright-founder{
 margin:0!important;padding:0!important;border:0!important;box-shadow:none!important;
 background:transparent!important;color:#dfb866;font:650 .91rem/1.4 system-ui,-apple-system,'Segoe UI',sans-serif;
 white-space:nowrap;letter-spacing:.025em;text-shadow:0 1px 1px rgba(0,0,0,.35);
}
@media(max-width:600px){
 .mw-site-footer>.mpx-bottom-bar{gap:6px 12px;padding-bottom:8px!important}
 .mw-site-footer>.mpx-bottom-bar>.mpw-copyright-founder{flex-basis:100%}
}
@media(forced-colors:active){.mw-site-footer>.mpx-bottom-bar>.mpw-copyright-founder{color:CanvasText!important}}
</style>"""
OLD_STYLE=re.compile(r'<style id="mpw-footer-refined-gold-v3">.*?</style>',re.S|re.I)
OLD_SIGNOFF=re.compile(r'<div class="mpw-footer-bottom-signoff" data-mpw-bottom-signoff="true"><span class="mpw-signoff-gold" data-emboss="Mojtaba Roozegar">Mojtaba Roozegar</span></div>',re.I)
FINAL='<span class="mpw-copyright-founder" data-mpw-copyright-founder="true">Mojtaba Roozegar</span>'
BAR=re.compile(r'(?P<sign><div class="mpw-footer-bottom-signoff" data-mpw-bottom-signoff="true">.*?</div>)\s*</footer>\s*(?P<bar><div class="mpx-bottom-bar">(?P<copyright>.*?)</div>)',re.S|re.I)

def sha(data):return hashlib.sha256(data).hexdigest()
def paths():
    if ROOT.is_symlink() or FOLDER.is_symlink() or not ROOT.is_dir() or not FOLDER.is_dir():
        raise RuntimeError("unexpected main site directory")
    if HT.is_symlink() or sha(HT.read_bytes())!=HT_SHA:
        raise RuntimeError("routing changed; no safe publication")
    if BACKUP_ROOT.is_symlink():raise RuntimeError("backup root symlink")
    pages=sorted(p for p in FOLDER.iterdir() if p.name.endswith(".html")
        and p.is_file() and not p.is_symlink()
        and "noindex,nofollow,noarchive" in p.read_text("utf-8"))
    files=[PROD]+pages
    if len(files)!=23 or set(p.name for p in files)!=set(EXPECTED):
        raise RuntimeError("main-only HTML scope changed")
    for p in files:
        if not p.is_file() or p.is_symlink() or sha(p.read_bytes())!=EXPECTED[p.name]:
            raise RuntimeError("current live file sha mismatch; refuse overwrite")
    return files

def rewrite(raw,isprod):
    if not 4000<len(raw)<900000:raise RuntimeError("unexpected page size")
    doc=raw.decode("utf-8")
    if MARKER in doc or doc.count("</head>")!=1 or doc.count("</footer>")!=1:
        raise RuntimeError("footer already changed")
    if isprod:
        if "MJWP_ROOT_CANDIDATE_ONLY_20261017" not in doc or "noindex,nofollow,noarchive" in doc:
            raise RuntimeError("production page identity mismatch")
    else:
        if "noindex,nofollow,noarchive" not in doc:
            raise RuntimeError("preview page identity mismatch")
    doc,n=OLD_STYLE.subn(NEW_STYLE,doc)
    if n!=1:raise RuntimeError("old style absent/duplicate")
    m=BAR.search(doc)
    if m is None or len(list(BAR.finditer(doc)))!=1:
        raise RuntimeError("bottom copyright bar not exactly after original footer")
    copyright=m.group("copyright")
    if copyright.count("<span>")!=2 or copyright.count("</span>")!=2:
        raise RuntimeError("copyright two original spans changed")
    if "© 2022 MojPlayWin. All rights reserved." not in copyright:
        raise RuntimeError("copyright original text changed")
    # Other main pages have their own approved second copyright span;
    # retain every original character from BOTH spans without requiring
    # homepage-specific prose on other sections.
    if not OLD_SIGNOFF.fullmatch(m.group("sign")):
        raise RuntimeError("old founder signoff not unique")
    # The bar belongs to the footer, not one line underneath it.
    # Its original two spans stay byte-for-byte unchanged, new founder is last.
    old_bar=m.group("bar")
    new_bar=old_bar[:-6]+FINAL+"</div>"
    doc=doc[:m.start()]+new_bar+"\n</footer>"+doc[m.end():]
    if doc.count(MARKER)!=1 or doc.count("mpx-bottom-bar")<1:
        raise RuntimeError("new final line not installed")
    if OLD_SIGNOFF.search(doc) or OLD_STYLE.search(doc):
        raise RuntimeError("outdated higher founder line remains")
    f=re.search(r'<footer\b[^>]*class="mw-site-footer"[^>]*>(.*?)</footer>',doc,re.I|re.S)
    if f is None or f.group(1).count(FINAL)!=1:
        raise RuntimeError("gold name not inside actual footer")
    if not f.group(1).rstrip().endswith(new_bar):
        raise RuntimeError("copyright bar not the final footer row")
    if re.search(r'</footer>\s*<div class="mpx-bottom-bar">',doc):
        raise RuntimeError("copyright bar incorrectly outside footer")
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
    print(json.dumps({"status":"copyright-final-gold-pending-public-verification",
      "count":23,"root_unchanged_except_founder":True,"passenger_restart":False,
      "child_sites_modified":False,"old_gold_panel_removed":True},sort_keys=True))

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
    print(json.dumps({"status":"copyright-final-gold-founder-23-pages-committed",
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
        # Only internally authored, fixed fail-closed codes; never expose paths,
        # names of customers or raw exception data in action logs.
        codes={
          "unexpected main site directory", "routing changed; no safe publication",
          "backup root symlink", "main-only HTML scope changed",
          "current live file sha mismatch; refuse overwrite", "unexpected page size",
          "footer already changed", "production page identity mismatch",
          "preview page identity mismatch", "old style absent/duplicate",
          "bottom copyright bar not exactly after original footer",
          "copyright two original spans changed", "copyright original text changed",
          "copyright mission line changed", "old founder signoff not unique",
          "new final line not installed", "outdated higher founder line remains",
          "gold name not inside actual footer", "copyright bar not the final footer row",
          "copyright bar incorrectly outside footer", "previous release state exists"
        }
        safe_code=str(ex) if str(ex) in codes else "OTHER_FAIL_CLOSED"
        print(json.dumps({"status":"inline-founder-fail-closed",
            "exception_type":type(ex).__name__,"reason_code":safe_code,
            "production_routing_changed":False},sort_keys=True))
        raise SystemExit(1)
