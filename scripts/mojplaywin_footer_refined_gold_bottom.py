#!/usr/bin/env python3
"""Replace intrusive 3D gold footer signature with a refined footer-bottom signoff.

Exactly 23 static MAIN-OWNED MojPlayWin HTML pages: current / root and 22 previews.
Pure CSS and one line within existing footer grid; zero independent boxes.
No shared templates, Passenger, .htaccess, payments, or independent child pages.
Atomic SHA-pinned update with verified private originals and rollback watchdog.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys

ROOT=Path("/home/zomorod2/mojplaywin.com")
FOLDER=ROOT/"design-preview-20261017"
PROD=FOLDER/"production-home-20261017.html"
HT=ROOT/".htaccess"
BACKUP_ROOT=Path("/home/zomorod2/.mpw-founder-refined-footer-backups")
HT_SHA="5886985a2bb92578c26c05b74568a34a99d128eb505827a799773876a5e17a30"
MARKER='data-mpw-bottom-signoff="true"'
EXPECTED={
    "agents.html": "71807755c60b684fb8cc87e42cea41993e47943aa4c480231bdf03833697ab9b",
    "ai.html": "414c9aaa8a98bf11adaac1aa42ac9da231fb542eaa48dae649b585e6a919b650",
    "blockchain.html": "e961117ab033ea4da18051bf1f15e2147a169a0686e8b826de716a4e25ee2ea4",
    "company.html": "466062b827044b9a0dfe806a44c1728ecf178ab162e0df297ccc0bb56b6ac2e7",
    "economy.html": "80fe16198aed1c04f2a5a2e680742426ac2b0497a8c728ba953b357d04081046",
    "index.html": "8d2301700c7dcab76b68277d8b7fab1643ac63a7857a94439a2d99e5a5f9de0b",
    "industry.html": "65af17fcad078c908ed650909a09c0b07ba48fca7156214f55a0b0c096b5ae0b",
    "knowledge.html": "1319e2e8df79e3fa3fbf933b39dd9f93962bc2b70075c2c628068c130ad2f65a",
    "market.html": "2515482c5e89d3cf707ae90d7d2a1a1a181e3f434ecac14b714586484e4f79f1",
    "production-home-20261017.html": "42de5204f6c3ec0a059c66c28090362657176d77b71297582d10301e1cd75fc0",
    "research.html": "ee3811d63eeaeac6a2457cd386c507f42f810fd3c56fcfe14c2d283a68126884",
    "restaurant.html": "3c1ba5345251457ae65679d081f0a0065b62ae088c4bed658804d79d06cb1997",
    "store.html": "784fa0bd7dab5ca6f085651f024a50bf795eefbeb69760fbdd046e858ebd0607",
    "studio.html": "adb25da36d5176fa1300d217876245ba44db982e5aa1a5714e43efbe1e88cd1c",
    "support.html": "d1de416092ba4a6f838a6c3ea202fff7c28d81410b3a286bde5453898461691e",
    "venture_agriculture.html": "cd0f58858c31d5f63e803d9151c3ec01bc6b36c1a4d631bc7e457c844a4e41a3",
    "venture_carpets.html": "b6b4e18886179878081a95e69c1111ac745baa686dab98382cb0d3d6100c90c1",
    "venture_crypto.html": "09ab8d82ce73916cf81da56329a2cc7f83d4100bae4704ecdb4299cbdd9f54f4",
    "venture_ecommerce.html": "7da46f7ec33dd216e800cac09e1adcbfb0d9bcb5d6102e0cd312814e3b391842",
    "venture_fuel_station.html": "954523e1a6a4a371d325f225a8d2baa32eb145bcdf314e3f7012268c1551def3",
    "venture_hospitality.html": "0131541205632971e0831116ced4395e6b757f743f75f5b9a4fd9021088903d4",
    "venture_jewelry_gold.html": "322193cdccd22b23aac47b7837a97a47b1407ea2b744093e6660097d7f82294f",
    "web_engineering.html": "0cf017e0da8df0b96f86346f6f7ab03621b87568ebb2111cf6ab53b56795b8b6"
}
NEW_STYLE="""<style id="mpw-footer-refined-gold-v3">
.mw-site-footer .mpw-footer-bottom-signoff{
  grid-column:1/-1;align-self:end;width:100%;margin:12px 0 0;
  padding:17px 0 2px;border:0;border-top:1px solid rgba(214,174,96,.22);
  border-radius:0;background:transparent!important;box-shadow:none!important;
  display:flex;align-items:center;justify-content:center;text-align:center;
}
.mw-site-footer .mpw-footer-bottom-signoff .mpw-signoff-gold{
  isolation:isolate;position:relative;display:inline-block;
  font-family:ui-sans-serif,system-ui,-apple-system,'Segoe UI',sans-serif;
  font-size:clamp(.94rem,1.3vw,1.14rem);font-weight:650;line-height:1.55;
  letter-spacing:.075em;text-transform:none;
  color:#dfb866;
  background:linear-gradient(180deg,#fcebc0 0%,#e1bc70 49%,#b88737 100%);
  -webkit-background-clip:text;background-clip:text;-webkit-text-fill-color:transparent;
  filter:drop-shadow(0 1px 1px rgba(0,0,0,.42));
}
.mw-site-footer .mpw-footer-bottom-signoff .mpw-signoff-gold::before{
  content:attr(data-emboss);position:absolute;inset:0;z-index:-1;
  transform:translate(.65px,1.25px);-webkit-text-fill-color:#6b471b;
  color:#6b471b;opacity:.58;text-shadow:0 1px 1px rgba(0,0,0,.42);
}
@media(max-width:560px){
 .mw-site-footer .mpw-footer-bottom-signoff{margin-top:14px;padding-top:14px}
 .mw-site-footer .mpw-footer-bottom-signoff .mpw-signoff-gold{letter-spacing:.045em;font-size:.97rem}
}
@media(forced-colors:active){
 .mw-site-footer .mpw-footer-bottom-signoff .mpw-signoff-gold{
   background:none!important;-webkit-text-fill-color:CanvasText;color:CanvasText;
 }
}
</style>"""
SIGNOFF='<div class="mpw-footer-bottom-signoff" data-mpw-bottom-signoff="true"><span class="mpw-signoff-gold" data-emboss="Mojtaba Roozegar">Mojtaba Roozegar</span></div>'
OLD_STYLE=re.compile(r'<style id="mpw-footer-gold-3d-inline-v2">.*?</style>',re.S|re.I)
OLD_LINE=re.compile(r'<p class="mpw-footer-founder-inline" data-mpw-inline-gold-3d="true" aria-label="Mojtaba Roozegar"><strong class="mpw-gold-3d" data-text="Mojtaba Roozegar">Mojtaba Roozegar</strong></p>',re.I)

def sha(data):return hashlib.sha256(data).hexdigest()
def paths():
    if ROOT.is_symlink() or FOLDER.is_symlink() or not ROOT.is_dir() or not FOLDER.is_dir():
        raise RuntimeError("site path unsafe")
    if HT.is_symlink() or sha(HT.read_bytes())!=HT_SHA:
        raise RuntimeError("site rewrite routing drift")
    if BACKUP_ROOT.is_symlink():raise RuntimeError("backup path unsafe")
    out=sorted(p for p in FOLDER.iterdir() if p.name.endswith(".html")
        and p.is_file() and not p.is_symlink()
        and "noindex,nofollow,noarchive" in p.read_text(encoding="utf-8"))
    all_files=[PROD]+out
    if len(all_files)!=23 or set(p.name for p in all_files)!=set(EXPECTED):
        raise RuntimeError("preview route set changed")
    for p in all_files:
        if not p.is_file() or p.is_symlink() or sha(p.read_bytes())!=EXPECTED[p.name]:
            raise RuntimeError("current live file does not match exact preflight hash")
    return all_files

def rewrite(raw,is_prod):
    if not 4000<len(raw)<900000:raise RuntimeError("unrecognized HTML length")
    doc=raw.decode("utf-8")
    if MARKER in doc or doc.count("</head>")!=1 or doc.count("</footer>")!=1:
        raise RuntimeError("HTML topology changed")
    if is_prod:
        if "MJWP_ROOT_CANDIDATE_ONLY_20261017" not in doc or "noindex,nofollow,noarchive" in doc:
            raise RuntimeError("current root identity mismatch")
    else:
        if "noindex,nofollow,noarchive" not in doc:raise RuntimeError("preview identity mismatch")
    doc,style_count=OLD_STYLE.subn(NEW_STYLE,doc)
    doc,line_count=OLD_LINE.subn("",doc)
    if style_count!=1 or line_count!=1:raise RuntimeError("old intrusive signature not unique")
    if 'class="mw-site-footer"' not in doc:raise RuntimeError("main-only footer missing")
    if doc.count("</footer>")!=1:raise RuntimeError("more than one footer closing element")
    doc=doc.replace("</footer>",SIGNOFF+"\n</footer>",1)
    footer_start=doc.find('<footer class="mw-site-footer"')
    footer_end=doc.index('</footer>',footer_start)
    f=doc[footer_start:footer_end]
    if f.count(SIGNOFF)!=1 or f.rfind(SIGNOFF)<f.rfind("</nav>") or f.rfind(SIGNOFF)<f.rfind("mw-legal"):
        raise RuntimeError("signature not in bottom row of main footer")
    if OLD_LINE.search(doc) or OLD_STYLE.search(doc):
        raise RuntimeError("legacy gold tile still exists")
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
    print(json.dumps({"status":"refined-footer-gold-pending-public-verification",
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
    print(json.dumps({"status":"refined-footer-gold-founder-23-pages-committed",
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
