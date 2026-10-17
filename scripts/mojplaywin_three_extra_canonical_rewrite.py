#!/usr/bin/env python3
"""Main-host six exact canonical URLs -> vetted standalone PHP body filter.

Only modifies /home/zomorod2/mojplaywin.com/.htaccess.
Never writes shared Django/Passenger/WSGI, other virtual host, checkout or DB.
Old .htaccess bytes retained in a private, independently rollbackable folder.
An independent watchdog reverts within 180s unless public verification commits.
"""
from __future__ import annotations
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT=Path("/home/zomorod2/mojplaywin.com")
HT=ROOT/".htaccess"
PHP=ROOT/"design-preview-20261017/_mpw_three_extra_canonical_20261017.php"
PRIVATE=Path("/home/zomorod2/.mpw-three-more-canonicals-only-20261017")
BACKUP=PRIVATE/"original-htaccess"
STATE=PRIVATE/"state.json"
WATCH=PRIVATE/"watchdog.py"
BASE_SHA="fbfa01e3d0f694b3b65782fe957d6d943302c6dea2374803ad6a91976164128a"
MARKER="MPW_THREE_MORE_CANONICAL_ONLY_20261017"
TARGET="/design-preview-20261017/_mpw_three_extra_canonical_20261017.php"
ROUTES={
    "market":"/market/",
    "industry":"/industry/",
    "economy":"/economy/",
}

def sha(x:bytes)->str:return hashlib.sha256(x).hexdigest()

def validate(expected_php_sha):
    six_state=Path("/home/zomorod2/.mpw-six-canonicals-only-20261017/state.json")
    if six_state.is_symlink() or not six_state.is_file():
        raise RuntimeError("previous six-route release state unavailable")
    old=json.loads(six_state.read_text())
    if old.get("status")!="verified_committed" or old.get("mode")!="production" or old.get("new_sha")!=BASE_SHA:
        raise RuntimeError("prior six-route release unexpectedly changed")
    if not re.fullmatch("[0-9a-f]{64}",expected_php_sha):
        raise RuntimeError("expected source sha invalid")
    for obj in (HT,PHP):
        if obj.is_symlink() or not obj.is_file() or obj.stat().st_uid!=os.getuid():
            raise RuntimeError("unsafe target or source")
    if ROOT.is_symlink() or not ROOT.is_dir() or PRIVATE.is_symlink():
        raise RuntimeError("directory symlink")
    if sha(PHP.read_bytes())!=expected_php_sha:
        raise RuntimeError("staged PHP content not exactly reviewed GitHub version")

def current_config():
    current=HT.read_bytes()
    if sha(current)!=BASE_SHA:raise RuntimeError("production htaccess no longer matches audit: no writes")
    return current

def directives(mode):
    if mode not in ("canary","production"):raise RuntimeError("bad rewrite mode")
    blocks=[]
    for slug,original_path in ROUTES.items():
        if mode=="canary" and slug!="market":continue
        tests=[
          "RewriteCond %{REQUEST_METHOD} ^GET$",
          "RewriteCond %{REQUEST_URI} ^"+re.escape(original_path)+"$",
          "RewriteCond %{QUERY_STRING} !(^|&)__mpw_canon_passthru=1(&|$)",
        ]
        if mode=="canary":
            tests.append("RewriteCond %{QUERY_STRING} (^|&)__mpw_canon_probe=20261017(&|$)")
        tests.append("RewriteRule ^.*$ "+TARGET+"?__mpw_canon_route="+slug+" [END,QSA,E=cache-control:no-cache]")
        blocks.append("\n".join(tests))
    return "# "+MARKER+" "+mode+"\n"+"\n".join(blocks)+"\n"

def build(original,mode):
    raw=original.decode("utf-8")
    lines=raw.splitlines(keepends=True)
    found=[i for i,line in enumerate(lines) if re.fullmatch(r"\s*RewriteEngine\s+On\s*",line,re.I)]
    if len(found)!=1:raise RuntimeError("RewriteEngine configuration not unique")
    if MARKER in raw:raise RuntimeError("marker already present")
    lines.insert(found[0]+1,directives(mode))
    new="".join(lines).encode("utf-8")
    if not new.startswith(original.splitlines(keepends=True)[0]):
        raise RuntimeError("rewrite prefix unexpected")
    if new.count(MARKER.encode())!=1 or new.count(TARGET.encode())!=(1 if mode=="canary" else 3):
        raise RuntimeError("exact route count mismatch")
    # Removing only the inserted block must recover the original byte-for-byte.
    if new.replace(directives(mode).encode(),b"",1)!=original:
        raise RuntimeError("unrelated server rewrite would be modified")
    return new

def atomic(data):
    temp=ROOT/(".htaccess.mpw-six-only-"+str(os.getpid()))
    fd=os.open(str(temp),os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
    try:
        with os.fdopen(fd,"wb") as out:
            out.write(data);out.flush();os.fsync(out.fileno())
        os.chmod(temp,0o644)
        os.replace(temp,HT)
    finally:
        if temp.exists():temp.unlink()

def state_read():
    if STATE.is_symlink() or not STATE.is_file():raise RuntimeError("missing protected state")
    return json.loads(STATE.read_text())

def state_write(item):
    tmp=PRIVATE/("release-state-"+str(os.getpid()))
    fd=os.open(str(tmp),os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,"w") as out:
        json.dump(item,out,sort_keys=True);out.flush();os.fsync(out.fileno())
    os.replace(tmp,STATE)

def schedule_watchdog():
    watchdog="""from pathlib import Path
import hashlib,json,os,time
time.sleep(180)
private=Path('/home/zomorod2/.mpw-three-more-canonicals-only-20261017')
target=Path('/home/zomorod2/mojplaywin.com/.htaccess')
try:
    st=json.loads((private/'state.json').read_text())
    if st.get('status')!='armed':raise SystemExit
    original=(private/'original-htaccess').read_bytes()
    if hashlib.sha256(original).hexdigest()!=st['old_sha']:raise SystemExit
    if target.is_symlink() or hashlib.sha256(target.read_bytes()).hexdigest()!=st['new_sha']:raise SystemExit
    temp=target.with_name('.htaccess.mpw-canon-watchdog-'+str(os.getpid()))
    fd=os.open(str(temp),os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,'wb') as out:
        out.write(original);out.flush();os.fsync(out.fileno())
    os.chmod(temp,0o644)
    os.replace(temp,target)
    (private/'state.json').write_text(json.dumps({**st,'status':'watchdog_restored'},sort_keys=True))
except Exception:
    pass
"""
    WATCH.write_text(watchdog,encoding="utf-8")
    os.chmod(WATCH,0o600)
    subprocess.Popen([sys.executable,str(WATCH)],stdin=subprocess.DEVNULL,
       stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,close_fds=True,start_new_session=True)

def arm(mode,php_sha):
    validate(php_sha)
    original=current_config()
    if not PRIVATE.exists():PRIVATE.mkdir(mode=0o700)
    if PRIVATE.stat().st_uid!=os.getuid() or PRIVATE.stat().st_mode&0o077:
        raise RuntimeError("private backup storage unsafe")
    if STATE.exists() and state_read().get("status")=="armed":
        raise RuntimeError("previous operation remains armed")
    if BACKUP.is_symlink() or (BACKUP.exists() and BACKUP.read_bytes()!=original):
        raise RuntimeError("old backup does not match exact current base")
    if not BACKUP.exists():
        fd=os.open(str(BACKUP),os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        with os.fdopen(fd,"wb") as out:
            out.write(original);out.flush();os.fsync(out.fileno())
    new=build(original,mode)
    st={"status":"armed","mode":mode,"old_sha":BASE_SHA,
        "new_sha":sha(new),"php_sha":php_sha,"allowed_paths":list(ROUTES.values())}
    state_write(st)
    schedule_watchdog()
    atomic(new)
    if sha(HT.read_bytes())!=st["new_sha"]:raise RuntimeError("post-write checksum mismatch")
    print(json.dumps({"classification":"MOJ_PLAY_WIN_THREE_EXTRA_CANONICAL_REWRITE_ARMED",
        "mode":mode,"rules":1 if mode=="canary" else 3,
        "old_sha":BASE_SHA,"new_sha":st["new_sha"],
        "auto_revert_seconds":180,"shared_passenger_unchanged":True},sort_keys=True),flush=True)

def rollback():
    st=state_read()
    backup=BACKUP.read_bytes()
    if sha(backup)!=st["old_sha"]:raise RuntimeError("backup invalid")
    now=sha(HT.read_bytes())
    if now not in (st["old_sha"],st["new_sha"]):
        raise RuntimeError("concurrent .htaccess change; refuse overwrite")
    if now==st["new_sha"]:atomic(backup)
    state_write({**st,"status":"rolled_back"})
    print("THREE_EXTRA_CANONICAL_REWRITE_EXACT_BACKUP_RESTORED",flush=True)

def commit(php_sha):
    validate(php_sha)
    st=state_read()
    if st["mode"]!="production" or st["status"]!="armed":
        raise RuntimeError("production can only commit armed six-route release")
    if sha(HT.read_bytes())!=st["new_sha"] or st["php_sha"]!=php_sha:
        raise RuntimeError("release bytes drift before commit")
    state_write({**st,"status":"verified_committed"})
    print("MOJ_PLAY_WIN_THREE_EXTRA_CANONICAL_REWRITE_LIVE_COMMITTED",flush=True)

def main():
    if len(sys.argv)<2:raise RuntimeError("missing operation")
    action=sys.argv[1]
    if action in ("canary","production","commit"):
        if len(sys.argv)!=3:raise RuntimeError("reviewed PHP source SHA required")
        if action=="commit":commit(sys.argv[2])
        else:arm(action,sys.argv[2])
    elif action=="rollback":
        rollback()
    else:raise RuntimeError("unsupported operation")

if __name__=="__main__":
    try:main()
    except Exception as e:
        print("THREE_EXTRA_CANONICAL_RELEASE_BLOCKED_"+type(e).__name__+"_"+str(e)[:140],file=sys.stderr)
        raise SystemExit(3)
