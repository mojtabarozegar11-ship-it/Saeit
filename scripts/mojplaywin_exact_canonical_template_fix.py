#!/usr/bin/env python3
"""Scoped Moj Play Win canonical fix: two child templates, one new local base.

Never modify the shared base.html, Passenger, Django Python code, other brands,
personal/child sites, database, checkout, or existing URLs.
Independent watchdog restores exact source bytes within 180 seconds if uncommitted.
"""
from __future__ import annotations
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

APP = Path("/home/zomorod2/Saeit-staging")
TPL = APP / "core/templates"
BASE = TPL / "base.html"
CHILD_DIR = TPL / "mojplaywin"
LOCAL_BASE = CHILD_DIR / "canonical_base.html"
STORE = CHILD_DIR / "store.html"
SECTION = CHILD_DIR / "section.html"
STATE_DIR = Path("/home/zomorod2/.mpw-canonical-only-20261017")
STATE = STATE_DIR / "state.json"
GUARD = STATE_DIR / "watchdog.py"
EXPECTED_PREFIX = {
    "base": "14bdb42e58032a20",
    "store": "8e0df19a94921d74",
    "section": "6f6e42bd97541813",
}
OLD_TAG = '{% extends "base.html" %}'
NEW_TAG = '{% extends "mojplaywin/canonical_base.html" %}'
EXPECTED_CANONICAL = '<link rel="canonical" href="https://mojplaywin.com{{ request.path }}">'

def digest(data):
    return hashlib.sha256(data).hexdigest()

def check_path(path):
    if path.is_symlink() or not path.is_file() or path.stat().st_uid != os.getuid():
        raise RuntimeError("unexpected file path or owner")

def atomic(path, data, must_be_absent=False):
    tmp = path.with_name(".canonical-only-"+str(os.getpid()))
    fd = os.open(str(tmp),os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    try:
        with os.fdopen(fd,"wb") as out:
            out.write(data);out.flush();os.fsync(out.fileno())
        os.chmod(tmp,0o644)
        if must_be_absent:
            if path.exists() or path.is_symlink():raise RuntimeError("new canonical base exists already")
            os.link(tmp,path)
        else:
            if path.is_symlink():raise RuntimeError("destination became symlink")
            os.replace(tmp,path)
    finally:
        if tmp.exists():tmp.unlink()

def private_write(path,data):
    if path.is_symlink():raise RuntimeError("backup link unsafe")
    if path.exists():
        if path.read_bytes()!=data:raise RuntimeError("existing backup mismatched")
        return
    fd=os.open(str(path),os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,"wb") as out:
        out.write(data);out.flush();os.fsync(out.fileno())

def state_load():
    if STATE.is_symlink() or not STATE.is_file():raise RuntimeError("release state absent")
    return json.loads(STATE.read_text())

def state_save(state):
    tmp=STATE_DIR/("state-"+str(os.getpid()))
    fd=os.open(str(tmp),os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,"w") as out:
        json.dump(state,out,sort_keys=True);out.flush();os.fsync(out.fileno())
    os.replace(tmp,STATE)

def prepare():
    if APP.is_symlink() or TPL.is_symlink() or CHILD_DIR.is_symlink():
        raise RuntimeError("unsafe app layout")
    for p in (BASE,STORE,SECTION):check_path(p)
    if LOCAL_BASE.exists() or LOCAL_BASE.is_symlink():
        raise RuntimeError("refuse overwrite any existing canonical base")
    b=BASE.read_bytes()
    st=STORE.read_bytes()
    sec=SECTION.read_bytes()
    for key,data in (("base",b),("store",st),("section",sec)):
        if not digest(data).startswith(EXPECTED_PREFIX[key]):
            raise RuntimeError("production source SHA drift: "+key)
    if not st.decode().startswith(OLD_TAG) or not sec.decode().startswith(OLD_TAG):
        raise RuntimeError("existing template inheritance changed")
    shared=b.decode("utf-8")
    # Existing shared parent contains exactly one canonical for Zomorod.
    matcher=re.compile(r'<link\s+rel=["\']canonical["\']\s+href=["\']https://zomorodmelal\.ir[^"\']*["\']\s*/?>',re.I)
    hits=list(matcher.finditer(shared))
    if len(hits)!=1:raise RuntimeError("exactly one shared-base canonical expected")
    patched=shared[:hits[0].start()]+EXPECTED_CANONICAL+shared[hits[0].end():]
    if (patched.count('rel="canonical"')!=1 or
            '<link rel="canonical" href="https://zomorodmelal.ir' in patched):
        raise RuntimeError("new page-specific canonical has a conflict")
    if len(patched)-len(shared)>40 or len(patched)-len(shared)<-110:
        raise RuntimeError("new base unexpectedly diverges from protected shared base")
    return b,st,sec,patched.encode("utf-8")

def watchdog():
    script="""from pathlib import Path
import json,hashlib,os,time
time.sleep(180)
p=Path('/home/zomorod2/.mpw-canonical-only-20261017')
base=Path('/home/zomorod2/Saeit-staging/core/templates/mojplaywin')
try:
    state=json.loads((p/'state.json').read_text())
    if state.get('status')!='armed':raise SystemExit
    for name in ('store','section'):
        target=base/(name+'.html')
        original=(p/(name+'.html')).read_bytes()
        if hashlib.sha256(original).hexdigest()!=state['old_'+name]:raise SystemExit
        if target.is_symlink() or hashlib.sha256(target.read_bytes()).hexdigest()!=state['new_'+name]:raise SystemExit
        tmp=target.with_name('.canonical-watchdog-'+name+str(os.getpid()))
        fd=os.open(str(tmp),os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        with os.fdopen(fd,'wb') as out:
            out.write(original);out.flush();os.fsync(out.fileno())
        os.chmod(tmp,0o644)
        os.replace(tmp,target)
    new=base/'canonical_base.html'
    if not new.is_symlink() and new.is_file() and hashlib.sha256(new.read_bytes()).hexdigest()==state['new_base']:
        new.unlink()
    (p/'state.json').write_text(json.dumps({**state,'status':'watchdog_rolled_back'}))
except Exception:
    pass
"""
    GUARD.write_text(script)
    os.chmod(GUARD,0o600)
    subprocess.Popen([sys.executable,str(GUARD)],stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,
         stderr=subprocess.DEVNULL,start_new_session=True,close_fds=True)

def deploy():
    old_base,old_store,old_section,new_base=prepare()
    if STATE_DIR.is_symlink():raise RuntimeError("backup folder symlinked")
    if not STATE_DIR.exists():STATE_DIR.mkdir(mode=0o700)
    if STATE_DIR.stat().st_uid!=os.getuid() or STATE_DIR.stat().st_mode&0o077:
        raise RuntimeError("private backup folder wrong owner/mode")
    if STATE.exists() and state_load().get("status")=="armed":
        raise RuntimeError("previous armed attempt")
    private_write(STATE_DIR/"store.html",old_store)
    private_write(STATE_DIR/"section.html",old_section)
    new_store=old_store.decode().replace(OLD_TAG,NEW_TAG,1).encode()
    new_section=old_section.decode().replace(OLD_TAG,NEW_TAG,1).encode()
    state={
       "status":"armed","new_base":digest(new_base),
       "old_store":digest(old_store),"old_section":digest(old_section),
       "new_store":digest(new_store),"new_section":digest(new_section),
       "shared_base_sha":digest(old_base),
       "scope":"mojplaywin-page-templates-only"
    }
    state_save(state)
    watchdog()
    atomic(LOCAL_BASE,new_base,must_be_absent=True)
    atomic(STORE,new_store)
    atomic(SECTION,new_section)
    for file,key in ((LOCAL_BASE,"new_base"),(STORE,"new_store"),(SECTION,"new_section")):
        if digest(file.read_bytes())!=state[key]:
            raise RuntimeError("atomic file verification failed")
    if digest(BASE.read_bytes())!=state["shared_base_sha"]:
        raise RuntimeError("shared base unexpectedly changed")
    print(json.dumps({"classification":"MOJ_PLAY_WIN_LOCAL_BASE_TEMPLATES_ARMED",
          "rollback_seconds":180,"new_page_base_created":True,
          "modified_main_only_child_templates":2,"shared_base_changed":False,
          "passenger_restarted":False},sort_keys=True),flush=True)

def rollback():
    state=state_load()
    for key,path in (("store",STORE),("section",SECTION)):
        check_path(path)
        current=digest(path.read_bytes())
        if current not in (state["old_"+key],state["new_"+key]):
            raise RuntimeError("concurrent modification: "+key)
        backup=(STATE_DIR/(key+".html")).read_bytes()
        if digest(backup)!=state["old_"+key]:raise RuntimeError("tampered backup: "+key)
        if current!=state["old_"+key]:atomic(path,backup)
    if LOCAL_BASE.is_symlink():raise RuntimeError("new base became symlink")
    if LOCAL_BASE.exists():
        if digest(LOCAL_BASE.read_bytes())!=state["new_base"]:
            raise RuntimeError("new base modified by another operation")
        LOCAL_BASE.unlink()
    state_save({**state,"status":"rolled_back"})
    print("MOJ_PLAY_WIN_TWO_TEMPLATES_ORIGINAL_RESTORED_AND_NEW_BASE_REMOVED",flush=True)

def commit():
    state=state_load()
    if state["status"]!="armed":raise RuntimeError("commit requires armed state")
    for file,key in ((LOCAL_BASE,"new_base"),(STORE,"new_store"),(SECTION,"new_section")):
        if file.is_symlink() or not file.is_file() or digest(file.read_bytes())!=state[key]:
            raise RuntimeError("not deployed as expected")
    if digest(BASE.read_bytes())!=state["shared_base_sha"]:
        raise RuntimeError("shared parent base unexpectedly modified")
    state_save({**state,"status":"verified_committed"})
    print("MOJ_PLAY_WIN_CANONICAL_EXACT_TEMPLATE_ONLY_RELEASE_COMMITTED",flush=True)

if __name__=="__main__":
    try:
        if len(sys.argv)!=2:raise RuntimeError("action required")
        action=sys.argv[1]
        if action=="deploy":deploy()
        elif action=="rollback":rollback()
        elif action=="commit":commit()
        else:raise RuntimeError("unknown action")
    except Exception as e:
        print("CANONICAL_SAFE_TEMPLATE_OPERATION_FAILED_"+type(e).__name__,file=sys.stderr)
        raise SystemExit(3)
