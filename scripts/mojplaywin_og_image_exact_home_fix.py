#!/usr/bin/env python3
"""Exact-file, atomic, fail-closed fix for Moj Play Win OG image on homepage.
Uses existing public 200-OK image. No shared Passenger, DB, other pages changed.
"""
from pathlib import Path
import hashlib
import json
import os
import subprocess
import sys

HOME=Path("/home/zomorod2/mojplaywin.com/design-preview-20261017/production-home-20261017.html")
PRIVATE=Path("/home/zomorod2/.mpw-root-og-image-fix-20261017")
BACKUP=PRIVATE/"old-home.html"
STATE=PRIVATE/"state.json"
GUARD=PRIVATE/"watchdog.py"
ROOT=Path("/home/zomorod2/mojplaywin.com")
ROUTING=Path("/home/zomorod2/.mpw-main-root-route-release-20261017/state.json")
EXPECTED="3e7ad6d898809c267db127287dca54c136d53e422086c5e8a372a45f6b6b2557"
OLD_IMG="https://mojplaywin.com/design-preview-20261017/static/site/mojplaywin-brand.jpg"
NEW_IMG="https://mojplaywin.com/design-preview-20261017/static/site/heroes/platform-home.4dd3ab6a401d.webp"

def sha(data):return hashlib.sha256(data).hexdigest()

def guard():
    if HOME.is_symlink() or not HOME.is_file() or HOME.stat().st_uid!=os.getuid():
        raise RuntimeError("target unsafe")
    if ROOT.is_symlink() or PRIVATE.is_symlink():raise RuntimeError("unexpected symlink")
    rootstate=json.loads(ROUTING.read_text())
    if rootstate.get("status")!="verified_committed" or rootstate.get("mode")!="root":
        raise RuntimeError("main site routing no longer audited")
    if sha((ROOT/".htaccess").read_bytes())!=rootstate.get("candidate_sha"):
        raise RuntimeError("root routing changed")

def atomic(data):
    temp=HOME.with_name(".new-social-image-"+str(os.getpid()))
    fd=os.open(str(temp),os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
    try:
        with os.fdopen(fd,"wb") as f:
            f.write(data);f.flush();os.fsync(f.fileno())
        os.chmod(temp,0o644)
        os.replace(temp,HOME)
    finally:
        if temp.exists():temp.unlink()

def setstate(state):
    temp=PRIVATE/("tmp-"+str(os.getpid()))
    temp.write_text(json.dumps(state,sort_keys=True))
    os.chmod(temp,0o600)
    os.replace(temp,STATE)

def getstate():
    if STATE.is_symlink():raise RuntimeError("state symlink")
    return json.loads(STATE.read_text())

def watcher():
    code="""from pathlib import Path
import hashlib,json,os,time
time.sleep(180)
p=Path('/home/zomorod2/.mpw-root-og-image-fix-20261017')
target=Path('/home/zomorod2/mojplaywin.com/design-preview-20261017/production-home-20261017.html')
try:
    state=json.loads((p/'state.json').read_text())
    if state['status']!='armed':raise SystemExit
    source=(p/'old-home.html').read_bytes()
    if hashlib.sha256(source).hexdigest()!=state['old_sha']:raise SystemExit
    if target.is_symlink() or hashlib.sha256(target.read_bytes()).hexdigest()!=state['new_sha']:raise SystemExit
    temp=target.with_name('.og-watchdog-'+str(os.getpid()))
    fd=os.open(str(temp),os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
    with os.fdopen(fd,'wb') as f:
        f.write(source);f.flush();os.fsync(f.fileno())
    os.chmod(temp,0o644)
    os.replace(temp,target)
    (p/'state.json').write_text(json.dumps({**state,'status':'watchdog_rolled_back'}))
except Exception:
    pass
"""
    GUARD.write_text(code);os.chmod(GUARD,0o600)
    subprocess.Popen([sys.executable,str(GUARD)],stdin=subprocess.DEVNULL,
      stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True,close_fds=True)

def run():
    if len(sys.argv)!=2:raise RuntimeError("operation missing")
    op=sys.argv[1]
    if op=="deploy":
        guard()
        old=HOME.read_bytes()
        if sha(old)!=EXPECTED:raise RuntimeError("source drift")
        source=old.decode("utf-8")
        line='<meta property="og:image" content="'+OLD_IMG+'">'
        if source.count(line)!=1:raise RuntimeError("cannot find exact broken share image")
        original='<meta name="twitter:card" content="summary_large_image">'
        if source.count(original)!=1:raise RuntimeError("expected twitter card missing")
        new=source.replace(line,
            '<meta property="og:image" content="'+NEW_IMG+'">\n'
            '<meta property="og:image:alt" content="Moj Play Win — research, games and digital innovation">',
            1)
        new=new.replace(original,original+'\n<meta name="twitter:image" content="'+NEW_IMG+'">',1)
        if (new.count('class="mpo-orbit-card"')!=18 or
            new.count('id="home-guide-')!=10 or
            '<h1 id="mw-home-title">Moj <em>Play</em> Win</h1>' not in new or
            '<link rel="canonical" href="https://mojplaywin.com/">' not in new):
            raise RuntimeError("homepage preservation failure")
        if not PRIVATE.exists():PRIVATE.mkdir(mode=0o700)
        if PRIVATE.stat().st_mode&0o077 or PRIVATE.stat().st_uid!=os.getuid():raise RuntimeError("unsafe backup dir")
        if STATE.exists() and getstate().get("status")=="armed":raise RuntimeError("earlier attempt still armed")
        if BACKUP.is_symlink() or (BACKUP.exists() and BACKUP.read_bytes()!=old):
            raise RuntimeError("unexpected old backup")
        if not BACKUP.exists():
            with BACKUP.open("xb") as f:f.write(old)
            os.chmod(BACKUP,0o600)
        updated=new.encode()
        state={"old_sha":sha(old),"new_sha":sha(updated),"status":"armed"}
        setstate(state)
        watcher()
        atomic(updated)
        if sha(HOME.read_bytes())!=state["new_sha"]:raise RuntimeError("write verify failed")
        print(json.dumps({"classification":"MOJ_PLAY_WIN_OG_IMAGE_REPLACED",
            "new_sha":state["new_sha"],"old_sha":state["old_sha"],"rollback_seconds":180,
            "site_routes_unchanged":True},sort_keys=True))
    elif op=="rollback":
        st=getstate()
        data=BACKUP.read_bytes()
        if sha(data)!=st["old_sha"]:raise RuntimeError("unsafe rollback source")
        present=sha(HOME.read_bytes())
        if present!=st["old_sha"]:
            if present!=st["new_sha"]:raise RuntimeError("concurrent edit detected")
            atomic(data)
        setstate({**st,"status":"rolled_back"})
        print("MAIN_HOME_OG_IMAGE_PATCH_ROLLED_BACK")
    elif op=="commit":
        guard()
        st=getstate()
        if st["status"]!="armed" or sha(HOME.read_bytes())!=st["new_sha"]:
            raise RuntimeError("unverified image release")
        setstate({**st,"status":"committed"})
        print("MAIN_HOME_OG_IMAGE_PATCH_VERIFIED_COMMITTED")
    else:raise RuntimeError("unknown command")

if __name__=="__main__":
    try:run()
    except Exception as error:
        print("OG_PATCH_BLOCKED_"+type(error).__name__,file=sys.stderr)
        raise SystemExit(3)
