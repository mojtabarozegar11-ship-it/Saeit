#!/usr/bin/env python3
"""Publish solely a previously absent index.html, or remove on failed acceptance.

Passenger, .htaccess, other routes, all sub-sites, DB, app assets untouched.
The independent private watchdog removes the exact candidate on timeout.
"""
from __future__ import annotations
import hashlib
import json
import os
import stat
import subprocess
import sys
from pathlib import Path

ROOT=Path("/home/zomorod2/mojplaywin.com")
DEST=ROOT/"index.html"
PREVIEW=ROOT/"design-preview-20261017"
SOURCE=PREVIEW/"production-home-20261017.html"
PRIVATE=Path("/home/zomorod2/.mpw-index-only-release-20261017")
STATE=PRIVATE/"state.json"
WATCHDOG=PRIVATE/"guard.py"
HT=ROOT/".htaccess"
BASE_HT="4f261f4563494f7ba8e9947e3ebcaa915815b5ffc451ad7348f3620300a695fd"

def sha(x):return hashlib.sha256(x).hexdigest()
def check():
    if ROOT.is_symlink() or not ROOT.is_dir() or HT.is_symlink() or HT.read_bytes() is None:
        raise RuntimeError("main docroot or config unsafe")
    if sha(HT.read_bytes())!=BASE_HT:raise RuntimeError("htaccess differs from audited original")
    if SOURCE.is_symlink() or not SOURCE.is_file():raise RuntimeError("approved source absent")
    if PREVIEW.is_symlink() or (PREVIEW/"_mpw_release_marker.txt").read_text().strip()!="mpw-approved-artifact-39034323161":
        raise RuntimeError("preview origin changed")
    source=SOURCE.read_bytes()
    for fragment in (b"MJWP_ROOT_CANDIDATE_ONLY_20261017", b'data-globe-orbit="continuous"', b'class="mpo-orbit-card"',b"/design-preview-20261017/static/"):
        if fragment not in source:raise RuntimeError("unverified original design")
    if b"noindex,nofollow,noarchive" in source:raise RuntimeError("bad SEO")
    if len(source)<90000 or len(source)>300000:raise RuntimeError("unexpected source size")
    return source

def state_load():
    if STATE.is_symlink() or not STATE.is_file():raise RuntimeError("no independent release state")
    return json.loads(STATE.read_text())

def state_write(value):
    tmp=PRIVATE/("status-"+str(os.getpid())+".tmp")
    if tmp.exists() or tmp.is_symlink():raise RuntimeError("unsafe private state")
    tmp.write_text(json.dumps(value,sort_keys=True))
    os.chmod(tmp,0o600)
    os.replace(tmp,STATE)

def deploy():
    data=check()
    if DEST.exists() or DEST.is_symlink():
        raise RuntimeError("root index already exists; NEVER overwrite")
    if PRIVATE.is_symlink():raise RuntimeError("private directory symlinked")
    if not PRIVATE.exists():PRIVATE.mkdir(mode=0o700)
    if PRIVATE.stat().st_mode & 0o077 or PRIVATE.stat().st_uid!=os.getuid():
        raise RuntimeError("private directory permissions")
    if STATE.exists() and state_load().get("status")=="armed":
        raise RuntimeError("previous index release still active")
    expected=sha(data)
    state_write({"status":"armed","candidate_sha":expected,"prior_index_absent":True,"old_htaccess_sha":BASE_HT})
    guard="""import hashlib,json,os,time
from pathlib import Path
time.sleep(120)
private=Path('/home/zomorod2/.mpw-index-only-release-20261017')
target=Path('/home/zomorod2/mojplaywin.com/index.html')
try:
    state=json.loads((private/'state.json').read_text())
    if state.get('status')!='armed':raise SystemExit
    if target.is_symlink() or not target.is_file():raise SystemExit
    if hashlib.sha256(target.read_bytes()).hexdigest()!=state['candidate_sha']:raise SystemExit
    target.unlink()
    (private/'state.json').write_text(json.dumps({**state,'status':'watchdog_removed'}))
except Exception:
    pass
"""
    WATCHDOG.write_text(guard)
    os.chmod(WATCHDOG,0o600)
    subprocess.Popen([sys.executable,str(WATCHDOG)],stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,close_fds=True,start_new_session=True)
    tmp=ROOT/(".mpw-new-index-"+str(os.getpid()))
    fd=os.open(str(tmp),os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    try:
        with os.fdopen(fd,"wb") as f:
            f.write(data);f.flush();os.fsync(f.fileno())
        os.chmod(tmp,0o644)
        if DEST.exists() or DEST.is_symlink():raise RuntimeError("index creation race")
        os.link(tmp,DEST)
    finally:
        if tmp.exists():tmp.unlink()
    if sha(DEST.read_bytes())!=expected:raise RuntimeError("index content verification failed")
    print("NEW_EXACT_MAIN_INDEX_ARMED_120_SECOND_AUTO_RESTORE",flush=True)

def rollback():
    state=state_load()
    if DEST.is_symlink():raise RuntimeError("safety: index became symlink")
    if DEST.exists():
        if not DEST.is_file() or sha(DEST.read_bytes())!=state["candidate_sha"]:
            raise RuntimeError("index changed concurrently; refuse removal")
        DEST.unlink()
    state_write({**state,"status":"rolled_back"})
    print("NEW_INDEX_REMOVED_OR_ABSENT_ORIGINAL_PASSENGER_PRESERVED",flush=True)

def commit():
    state=state_load()
    if state["status"]!="armed" or DEST.is_symlink() or not DEST.is_file():
        raise RuntimeError("no guarded index release")
    if sha(DEST.read_bytes())!=state["candidate_sha"] or sha(HT.read_bytes())!=BASE_HT:
        raise RuntimeError("index or Apache config invalid")
    state_write({**state,"status":"committed"})
    print("MAIN_INDEX_ROOT_RELEASE_COMMITTED_NO_PASSENGER_RESTART",flush=True)

def main():
    if len(sys.argv)!=2:raise SystemExit(2)
    action=sys.argv[1]
    if action=="deploy":deploy()
    elif action=="rollback":rollback()
    elif action=="commit":commit()
    else:raise RuntimeError("unknown operation")

if __name__=="__main__":
    try:main()
    except Exception as e:
        print("EXACT_MAIN_INDEX_OPERATION_FAILED_"+type(e).__name__,file=sys.stderr)
        raise SystemExit(3)
