#!/usr/bin/env python3
"""One narrowly scoped, auto-reverting Apache .htaccess root-route rewrite.

NEVER writes Passenger, Python application, settings, DB, child sites or media.
Only an exact path .htaccess edit (and private non-web backup files) is allowed.
An independent watchdog reverts within 120 seconds unless verified committed.
"""
from __future__ import annotations
import hashlib
import json
import os
import re
import stat
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path("/home/zomorod2/mojplaywin.com")
HT = ROOT / ".htaccess"
PRIVATE = Path("/home/zomorod2/.mpw-main-root-route-release-20261017")
ORIGINAL = PRIVATE / "original-htaccess.bin"
STATE = PRIVATE / "state.json"
WATCHDOG = PRIVATE / "watchdog.py"
EXPECTED = "4f261f4563494f7ba8e9947e3ebcaa915815b5ffc451ad7348f3620300a695fd"
PROD_NAME = "production-home-20261017.html"
PREVIEW = ROOT / "design-preview-20261017"
MARKER = "mpw-approved-artifact-39034323161"
CANARY = "__mpw_root_canary_20261017__"
LABEL = "MJWP_ONE_ROOT_ROUTE_ONLY_20261017"

def digest(buf):
    return hashlib.sha256(buf).hexdigest()

def paths_ok():
    if ROOT.is_symlink() or not ROOT.is_dir() or HT.is_symlink() or not HT.is_file():
        raise RuntimeError("no safe main docroot or htaccess")
    if ROOT.stat().st_uid != os.getuid() or HT.stat().st_uid != os.getuid():
        raise RuntimeError("ownership changed")
    if PRIVATE.is_symlink():
        raise RuntimeError("unsafe release private directory")
    if not PREVIEW.is_dir() or PREVIEW.is_symlink():
        raise RuntimeError("approved preview missing")
    for file in (PREVIEW / "_mpw_release_marker.txt", PREVIEW / PROD_NAME):
        if file.is_symlink() or not file.is_file():
            raise RuntimeError("approved root design file missing")
    if (PREVIEW / "_mpw_release_marker.txt").read_text().strip() != MARKER:
        raise RuntimeError("preview identity mismatch")
    text = (PREVIEW / PROD_NAME).read_text(encoding="utf-8")
    if ("mpo-orbit-card" not in text or "data-globe-orbit" not in text or
        "noindex,nofollow,noarchive" in text or
        "/design-preview-20261017/static/" not in text or
        "MJWP_ROOT_CANDIDATE_ONLY_20261017" not in text):
        raise RuntimeError("unapproved production candidate")

def atomic_write(data):
    temp = ROOT / (".htaccess.mpw-private-temp-" + str(os.getpid()))
    fd = os.open(str(temp), os.O_WRONLY|os.O_CREAT|os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temp,0o644)
        os.replace(temp,HT)
    finally:
        if temp.exists():temp.unlink()

def private_setup():
    if not PRIVATE.exists():
        PRIVATE.mkdir(mode=0o700)
    if PRIVATE.stat().st_uid != os.getuid() or PRIVATE.stat().st_mode & 0o077:
        raise RuntimeError("release private folder not private")

def read_state():
    if STATE.is_symlink() or not STATE.is_file():
        raise RuntimeError("missing guarded release state")
    return json.loads(STATE.read_text())

def state_save(value):
    tmp = PRIVATE / ("state."+str(os.getpid())+".tmp")
    if tmp.exists() or tmp.is_symlink():raise RuntimeError("stale temp state")
    tmp.write_text(json.dumps(value,sort_keys=True),encoding="utf-8")
    os.chmod(tmp,0o600)
    os.replace(tmp,STATE)

def backup():
    private_setup()
    original = HT.read_bytes()
    if digest(original) != EXPECTED:
        raise RuntimeError("root htaccess changed since safe audited baseline")
    if ORIGINAL.is_symlink() or (ORIGINAL.exists() and ORIGINAL.read_bytes()!=original):
        raise RuntimeError("unexpected pre-existing backup")
    if not ORIGINAL.exists():
        with ORIGINAL.open("xb") as output:
            output.write(original)
        os.chmod(ORIGINAL,0o600)
    return original

def candidate(original, mode):
    if mode == "canary":
        rule = "RewriteCond %{HTTPS} on\nRewriteRule ^" + CANARY + "$ /design-preview-20261017/_mpw_release_marker.txt [END]"
    elif mode == "root":
        rule = "RewriteCond %{HTTPS} on\nRewriteRule ^$ /design-preview-20261017/"+PROD_NAME+" [END]"
    elif mode == "probe-root":
        # Probe ONLY an exact root query, never ordinary traffic.
        rule = ("RewriteCond %{REQUEST_URI} ^/$\n"
                "RewriteCond %{QUERY_STRING} ^__mpw_root_probe_20261017=exact$\n"
                "RewriteRule ^.*$ /design-preview-20261017/_mpw_release_marker.txt [END,QSD]")
    else:raise RuntimeError("bad mode")
    source=original.decode("utf-8")
    rows=source.splitlines(keepends=True)
    found=[i for i,x in enumerate(rows) if re.match(r"^\s*RewriteEngine\s+On\s*$",x,re.I)]
    if len(found)!=1:
        raise RuntimeError("unexpected Apache rewrite engine topology")
    i=found[0]+1
    rows.insert(i,"# "+LABEL+" "+mode+"\n"+rule+"\n")
    return "".join(rows).encode("utf-8")

def watcher_spawn():
    # Isolated independent process; no network, and no other file writes.
    code = """import json,hashlib,os,time
from pathlib import Path
time.sleep(120)
p=Path('/home/zomorod2/.mpw-main-root-route-release-20261017')
h=Path('/home/zomorod2/mojplaywin.com/.htaccess')
try:
    state=json.loads((p/'state.json').read_text())
    if state.get('status')!='armed':raise SystemExit
    base=(p/'original-htaccess.bin').read_bytes()
    if hashlib.sha256(base).hexdigest()!=state['original_sha']:raise SystemExit
    data=h.read_bytes()
    if hashlib.sha256(data).hexdigest()!=state['candidate_sha']:raise SystemExit
    temp=h.with_name('.htaccess.mpw-watchdog-'+str(os.getpid()))
    fd=os.open(str(temp),os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,'wb') as out:
        out.write(base);out.flush();os.fsync(out.fileno())
    os.chmod(temp,0o644)
    os.replace(temp,h)
    (p/'state.json').write_text(json.dumps({**state,'status':'watchdog_rolled_back'}))
except Exception:
    pass
"""
    WATCHDOG.write_text(code)
    os.chmod(WATCHDOG,0o600)
    subprocess.Popen([sys.executable,str(WATCHDOG)],stdin=subprocess.DEVNULL,
       stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True,close_fds=True)

def arm(mode):
    paths_ok()
    original=backup()
    if STATE.exists() and not STATE.is_symlink():
        old=read_state()
        if old.get("status")=="armed":
            raise RuntimeError("previous release attempt still armed")
    data=candidate(original,mode)
    value={"mode":mode,"status":"armed","original_sha":digest(original),"candidate_sha":digest(data)}
    state_save(value)
    watcher_spawn()
    atomic_write(data)
    if digest(HT.read_bytes())!=value["candidate_sha"]:
        raise RuntimeError("atomic update failed")
    print("EXACT_"+mode.upper()+"_RULE_ARMED_AUTO_ROLLBACK_120S",flush=True)

def rollback():
    private_setup()
    state=read_state()
    original=ORIGINAL.read_bytes()
    if digest(original)!=EXPECTED or state["original_sha"]!=EXPECTED:
        raise RuntimeError("backup not authenticated")
    current=HT.read_bytes()
    if digest(current)==EXPECTED:
        state_save({**state,"status":"rolled_back"})
        print("HTACCESS_ORIGINAL_PRESERVED",flush=True)
        return
    if digest(current)!=state["candidate_sha"]:
        raise RuntimeError("do not overwrite concurrent configuration changes")
    atomic_write(original)
    state_save({**state,"status":"rolled_back"})
    print("HTACCESS_EXACT_ROLLBACK_VERIFIED",flush=True)

def commit_release():
    private_setup()
    state=read_state()
    if state["mode"]!="root" or state["status"]!="armed":
        raise RuntimeError("no valid production root candidate")
    if digest(HT.read_bytes())!=state["candidate_sha"]:
        raise RuntimeError("root config is not candidate")
    state_save({**state,"status":"verified_committed"})
    print("ROOT_REWRITE_COMMITTED_BACKUP_RETAINED",flush=True)

def main():
    if len(sys.argv)!=2:raise SystemExit(2)
    mode=sys.argv[1]
    if mode in ("canary","root","probe-root"):arm(mode)
    elif mode=="rollback":rollback()
    elif mode=="commit":commit_release()
    else:raise RuntimeError("invalid operation")

if __name__=="__main__":
    try:main()
    except Exception as exc:
        print("ROUTE_OPERATION_FAILED_"+type(exc).__name__,file=sys.stderr)
        raise SystemExit(3)
