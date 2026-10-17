#!/usr/bin/env python3
"""Founder footer on the EXISTING live main-root static HTML only.

Changes exactly /home/zomorod2/mojplaywin.com/design-preview-20261017/
production-home-20261017.html; no .htaccess edits, shared Django, Passenger,
subsite, checkout, store or other static preview changes.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path("/home/zomorod2/mojplaywin.com")
DOC = ROOT / "design-preview-20261017/production-home-20261017.html"
HT = ROOT / ".htaccess"
PRIV = Path("/home/zomorod2/.mpw-root-founder-20261018")
ORIGINAL_SHA = "a0053ae2940cf7e6ac1f6e2a1b6e61655127971cdd4d3caf5f83af5c6614794a"
HT_SHA = "5886985a2bb92578c26c05b74568a34a99d128eb505827a799773876a5e17a30"
MARKER = "data-mpw-root-founder-20261018"
STYLE = """<style id="mpw-root-founder-style">
.mpw-root-founder{display:flex;justify-content:center;align-items:center;max-width:440px;
margin:24px auto 14px;padding:17px 24px;text-align:center;
border:2px solid #d6ad55;border-radius:16px;
background:linear-gradient(135deg,#0c0b09,#272012 50%,#0d0c0a);
box-shadow:0 12px 30px #0009,inset 0 0 18px #d6ad5540}
.mpw-root-founder strong{color:#f4d68a;font:700 clamp(1.05rem,2vw,1.55rem)/1.3 Georgia,serif;
letter-spacing:.065em;text-shadow:0 1px 0 #6e511d,0 2px 0 #4b370f,0 3px 10px #c8a14570}
</style>"""
PLATE = '<div class="mpw-root-founder" data-mpw-root-founder-20261018="true" aria-label="Founder: Mojtaba Roozegar"><strong>Mojtaba Roozegar</strong></div>'

def sha(value):
    return hashlib.sha256(value).hexdigest()

def safe_paths():
    for p in (ROOT, DOC.parent):
        if p.is_symlink() or not p.is_dir():raise RuntimeError("unsafe root directory")
    if HT.is_symlink() or not HT.is_file() or sha(HT.read_bytes())!=HT_SHA:
        raise RuntimeError("root routing configuration drift")
    if DOC.is_symlink() or not DOC.is_file() or DOC.stat().st_size>900000:
        raise RuntimeError("unsafe dedicated root candidate")
    if PRIV.is_symlink():raise RuntimeError("unsafe private backup location")

def runname(id):
    if not re.fullmatch(r"[0-9]{8,14}",id):
        raise RuntimeError("invalid release number")
    return PRIV/("run-"+id)

def atomic(data,id):
    tmp=DOC.parent/(".mpw-root-founder-"+id+".temporary")
    fd=os.open(str(tmp),os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
    try:
        with os.fdopen(fd,"wb") as out:
            out.write(data);out.flush();os.fsync(out.fileno())
        os.chmod(tmp,0o644)
        os.replace(tmp,DOC)
    finally:
        if tmp.exists():tmp.unlink()

def put_state(folder,data,id):
    p=folder/("state-"+id+".tmp")
    fd=os.open(p,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,"w") as h:
        json.dump(data,h,sort_keys=True)
        h.flush();os.fsync(h.fileno())
    os.replace(p,folder/"state.json")

def read_state(folder,id):
    s=json.loads((folder/"state.json").read_text())
    if s["run"]!=id or s["base_sha"]!=ORIGINAL_SHA or s.get("target_sha") is None:
        raise RuntimeError("unrecognized release state")
    return s

def change(raw):
    if sha(raw)!=ORIGINAL_SHA:
        raise RuntimeError("unexpected current main root candidate")
    s=raw.decode("utf-8")
    if s.count("</head>")!=1 or s.count("</footer>")!=1:
        raise RuntimeError("original main-root HTML structure unexpected")
    for required in ("MJWP_ROOT_CANDIDATE_ONLY_20261017","mpo-orbit-card","data-globe-orbit"):
        if required not in s:raise RuntimeError("original main design not certified")
    if "noindex,nofollow,noarchive" in s or MARKER in s:
        raise RuntimeError("indexability or prior founder patch unexpected")
    new=s.replace("</head>",STYLE+"\n</head>",1).replace("</footer>",PLATE+"\n</footer>",1)
    if new.count(MARKER)!=1 or new.count("<strong>Mojtaba Roozegar</strong>")!=1:
        raise RuntimeError("founder patch not unique")
    return new.encode("utf-8")

def rollback(id):
    safe_paths()
    folder=runname(id)
    state=read_state(folder,id)
    prior=(folder/"original.bin").read_bytes()
    if sha(prior)!=ORIGINAL_SHA:raise RuntimeError("private backup checksum failed")
    current=DOC.read_bytes()
    if sha(current)==state["target_sha"]:
        atomic(prior,id)
    elif sha(current)!=ORIGINAL_SHA:
        raise RuntimeError("concurrent edit; rollback cannot overwrite")
    state["phase"]="rolled_back"
    put_state(folder,state,id)
    print(json.dumps({"result":"LIVE_ROOT_FOUNDER_ROLLBACK_OK","restored_sha":sha(DOC.read_bytes()),
                      "passenger_restarted":False,"subsites_modified":False},sort_keys=True))

def deploy(id):
    safe_paths()
    raw=DOC.read_bytes()
    target=change(raw)
    folder=runname(id)
    if folder.exists():raise RuntimeError("run already exists")
    PRIV.mkdir(mode=0o700,exist_ok=True);os.chmod(PRIV,0o700)
    folder.mkdir(mode=0o700)
    bp=folder/"original.bin"
    fd=os.open(bp,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
    with os.fdopen(fd,"wb") as f:f.write(raw);f.flush();os.fsync(f.fileno())
    if sha(bp.read_bytes())!=ORIGINAL_SHA:raise RuntimeError("backup verification failed")
    state={"run":id,"base_sha":ORIGINAL_SHA,"target_sha":sha(target),"phase":"armed"}
    put_state(folder,state,id)
    # Local independent failsafe: if this CI run vanishes, restore after 150 s.
    watcher = """import json,hashlib,os,sys,time
from pathlib import Path
time.sleep(150)
f=Path(sys.argv[1]);target=Path(sys.argv[2]);id=sys.argv[3]
try:
 s=json.loads((f/'state.json').read_text())
 if s.get('phase')!='armed' or s.get('run')!=id:raise SystemExit
 old=(f/'original.bin').read_bytes()
 current=target.read_bytes()
 sha=lambda v:hashlib.sha256(v).hexdigest()
 if sha(old)!=s['base_sha'] or sha(current)!=s['target_sha']:raise SystemExit
 temp=target.with_name('.mpw-root-watchdog-'+id+'.tmp')
 fd=os.open(temp,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
 with os.fdopen(fd,'wb') as out:out.write(old);out.flush();os.fsync(out.fileno())
 os.chmod(temp,0o644);os.replace(temp,target)
 s['phase']='watchdog_rolled_back'
 (f/'state.json').write_text(json.dumps(s,sort_keys=True))
except Exception:pass
"""
    wp=folder/"watchdog.py"
    wp.write_text(watcher);os.chmod(wp,0o600)
    watch=subprocess.Popen([sys.executable,str(wp),str(folder),str(DOC),id],
          stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
          start_new_session=True)
    os.kill(watch.pid,0)
    try:
        atomic(target,id)
        if sha(DOC.read_bytes())!=sha(target):raise RuntimeError("post-write hash mismatch")
    except Exception:
        rollback(id)
        raise
    print(json.dumps({"result":"LIVE_ROOT_FOUNDER_PENDING_PUBLIC_VERIFICATION",
          "new_sha":sha(target),"changed_only_static_root_file":True,
          "passenger_restarted":False,"protected_subsites_modified":False},sort_keys=True))

def commit(id):
    safe_paths()
    state=read_state(runname(id),id)
    if state["phase"]!="armed" or sha(DOC.read_bytes())!=state["target_sha"]:
        raise RuntimeError("main root was not verified")
    state["phase"]="committed"
    put_state(runname(id),state,id)
    print(json.dumps({"result":"LIVE_ROOT_FOUNDER_COMMITTED","original_backup_retained":True,
          "passenger_restarted":False,"subsites_modified":False},sort_keys=True))

if __name__=="__main__":
    try:
        if len(sys.argv)!=3:raise RuntimeError("bad argument count")
        mode,id=sys.argv[1:]
        if mode=="deploy":deploy(id)
        elif mode=="rollback":rollback(id)
        elif mode=="commit":commit(id)
        else:raise RuntimeError("bad mode")
    except Exception as e:
        print(json.dumps({"result":"LIVE_ROOT_FOUNDER_FAIL_CLOSED","error_class":type(e).__name__},sort_keys=True))
        raise SystemExit(1)
