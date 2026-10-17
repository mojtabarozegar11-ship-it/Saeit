#!/usr/bin/env python3
"""Only the already-independent MojPlayWin design-preview static HTML footer.

Never edits /, /store/, Django, .htaccess, Passenger, WSGI, customer files,
wallets, child sites, product records, or shared templates.
Each original preview file has a private SHA-verified rollback backup.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys

ROOT=Path("/home/zomorod2/mojplaywin.com/design-preview-20261017")
BACKUPS=Path("/home/zomorod2/.mpw-preview-founder-backups")
COUNT=22
MARKER="data-mpw-preview-founder-20261018"
STYLE='''<style id="mpw-preview-founder-style">
.mpw-preview-founder{display:flex;justify-content:center;align-items:center;margin:22px auto 12px;padding:18px 24px;max-width:440px;border:2px solid #d6ad55;border-radius:16px;background:linear-gradient(135deg,#100f0b,#272012 50%,#0c0b09);box-shadow:0 10px 30px #0009,inset 0 0 14px #d6ad5530;text-align:center}
.mpw-preview-founder strong{color:#f4d68a;font:700 clamp(1.05rem,2vw,1.55rem)/1.3 Georgia,serif;letter-spacing:.065em;text-shadow:0 1px 0 #6e511d,0 2px 0 #4b370f,0 3px 10px #c8a14570}
</style>'''
PLAQUE='''<div class="mpw-preview-founder" data-mpw-preview-founder-20261018="true" aria-label="Founder: Mojtaba Roozegar"><strong>Mojtaba Roozegar</strong></div>'''
def sha(b):return hashlib.sha256(b).hexdigest()
def check(run):
    if not re.fullmatch(r"[0-9]{8,14}",run):raise RuntimeError("run identifier")
    if not ROOT.is_dir() or ROOT.is_symlink():raise RuntimeError("independent preview path missing or unsafe")
    if BACKUPS.is_symlink():raise RuntimeError("backup root unsafe")
    return BACKUPS/("run-"+run)
def pages():
    if any(f.is_symlink() for f in ROOT.iterdir()):raise RuntimeError("preview root contains symlink")
    candidates=sorted(x for x in ROOT.iterdir() if x.name.endswith(".html"))
    files=[]
    for path in candidates:
        if not path.is_file() or path.is_symlink() or path.stat().st_size>800000:
            raise RuntimeError("preview HTML type/size")
        if "noindex" in path.read_text(encoding="utf-8").lower():
            files.append(path)
    if len(files)!=COUNT or (ROOT/"index.html") not in files or (ROOT/"store.html") not in files:
        raise RuntimeError("expected exactly 22 nonindexable independent preview pages")
    return files
def transform(raw):
    html=raw.decode("utf-8","strict")
    if MARKER in html:raise RuntimeError("founder plaque already installed")
    if html.lower().count("</head>")!=1 or html.lower().count("</footer>")!=1:
        raise RuntimeError("preview HTML footer/head structure")
    if 'noindex' not in html.lower():raise RuntimeError("preview requires noindex")
    html=html.replace("</head>",STYLE+"\n</head>",1)
    html=html.replace("</footer>",PLAQUE+"\n</footer>",1)
    if html.count(MARKER)!=1 or "Mojtaba Roozegar" not in html:
        raise RuntimeError("footer patch invalid")
    return html.encode("utf-8")
def atomic(path,b,run):
    tmp=path.parent/(".mpw-preview-foundersafe-"+run+"-"+path.name)
    fd=os.open(tmp,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
    try:
        with os.fdopen(fd,"wb") as f:f.write(b);f.flush();os.fsync(f.fileno())
        os.chmod(tmp,0o644)
        os.replace(tmp,path)
    finally:
        if tmp.exists():tmp.unlink()
def rollback(run):
    backup=check(run)
    if backup.is_symlink() or not backup.is_dir():raise RuntimeError("backup missing")
    manifest=json.loads((backup/"manifest.json").read_text())
    if manifest["run"]!=run or len(manifest["files"])!=COUNT:raise RuntimeError("manifest mismatch")
    for name,info in manifest["files"].items():
        if Path(name).name!=name:raise RuntimeError("backup entry path unsafe")
        target=ROOT/name
        old=(backup/name).read_bytes()
        if sha(old)!=info["before"]:raise RuntimeError("backup integrity")
        present=target.read_bytes()
        if sha(present) not in (info["before"],info["after"]):
            raise RuntimeError("concurrent preview changes, rollback blocked")
        if sha(present)==info["after"]:atomic(target,old,run)
    print(json.dumps({"operation":"preview_only_founder_rollback","original_preview_pages_restored":COUNT,"child_sites_changed":False,"root_site_changed":False}))
def deploy(run):
    backup=check(run)
    files=pages()
    planned={}
    for p in files:
        old=p.read_bytes();new=transform(old)
        planned[p.name]=(old,new)
    if backup.exists():raise RuntimeError("backup collision")
    BACKUPS.mkdir(mode=0o700,exist_ok=True)
    os.chmod(BACKUPS,0o700)
    backup.mkdir(mode=0o700)
    manifest={"run":run,"files":{}}
    for name,(old,new) in planned.items():
        p=backup/name
        fd=os.open(p,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
        with os.fdopen(fd,"wb") as f:f.write(old);f.flush();os.fsync(f.fileno())
        if sha(p.read_bytes())!=sha(old):raise RuntimeError("backup write verification")
        manifest["files"][name]={"before":sha(old),"after":sha(new)}
    mp=backup/"manifest.json"
    mp.write_text(json.dumps(manifest,sort_keys=True))
    os.chmod(mp,0o600)
    try:
        for name,(_,new) in planned.items():
            atomic(ROOT/name,new,run)
            if sha((ROOT/name).read_bytes())!=sha(new):raise RuntimeError("preview post-write sha")
    except Exception:
        rollback(run)
        raise
    print(json.dumps({"operation":"preview_only_founder_installed","pages":COUNT,"source_root_modified":False,"root_site_changed":False,"child_sites_changed":False,"passenger_restart":False,"verification_pending":True}))
if __name__=="__main__":
    try:
        if len(sys.argv)!=3:raise RuntimeError("arguments")
        _,mode,run=sys.argv
        if mode=="deploy":deploy(run)
        elif mode=="rollback":rollback(run)
        else:raise RuntimeError("mode")
    except Exception as ex:
        print(json.dumps({"operation":"preview_footer_no_go","error_class":type(ex).__name__,"root_site_changed":False,"child_sites_changed":False}))
        raise SystemExit(1)
