#!/usr/bin/env python3
"""Atomic Moj Play Win-only live sitemap augmentation.
A single exact GET /sitemap.xml rule routes to vetted PHP that dynamically
preserves the original Django XML and appends just three public URLs.
No shared Passenger restart, Django code change, subsite or checkout writes.
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
PHP=ROOT/"design-preview-20261017/_mpw_sitemap_three_indexable_20261017.php"
PRIVATE=Path("/home/zomorod2/.mpw-dynamic-sitemap-three-20261017")
BACKUP=PRIVATE/"original-htaccess"
STATE=PRIVATE/"state.json"
WATCH=PRIVATE/"watchdog.py"
EXPECTED_SHA="38362ca9da6229886809e68ce0b88d1b68e4baaef4fa343f0b1d8f0158ba8559"
PREV=Path("/home/zomorod2/.mpw-three-more-canonicals-only-20261017/state.json")
MARKER="MPW_DYNAMIC_SITEMAP_THREE_20261017"
URI="/design-preview-20261017/_mpw_sitemap_three_indexable_20261017.php"

def sha(raw:bytes)->str:return hashlib.sha256(raw).hexdigest()

def verify(php_hash:str):
    if not re.fullmatch(r"[0-9a-f]{64}",php_hash):raise RuntimeError("bad reviewed PHP sha")
    if ROOT.is_symlink() or not ROOT.is_dir() or PRIVATE.is_symlink():
        raise RuntimeError("unexpected directory symlink")
    for p in (HT,PHP,PREV):
        if p.is_symlink() or not p.is_file():
            raise RuntimeError("required trusted file absent or symlink")
    state=json.loads(PREV.read_text())
    if state.get("status")!="verified_committed" or state.get("new_sha")!=EXPECTED_SHA:
        raise RuntimeError("previous nine-route release is not confirmed")
    if sha(HT.read_bytes())!=EXPECTED_SHA:raise RuntimeError("live server config changed")
    if sha(PHP.read_bytes())!=php_hash:raise RuntimeError("PHP bridge differs from vetted source")

def rule(mode:str)->str:
    if mode not in ("canary","production"):raise RuntimeError("unsupported mode")
    out=[
      "# "+MARKER+" "+mode,
      "RewriteCond %{REQUEST_METHOD} ^GET$",
      r"RewriteCond %{REQUEST_URI} ^/sitemap\.xml$",
      r"RewriteCond %{QUERY_STRING} !(^|&)__mpw_sitemap_passthru=1(&|$)",
    ]
    if mode=="canary":
        out.append(r"RewriteCond %{QUERY_STRING} (^|&)__mpw_sitemap_probe=20261017(&|$)")
    out.append("RewriteRule ^.*$ "+URI+" [END,QSD,E=cache-control:no-cache]")
    return "\n".join(out)+"\n"

def candidate(old:bytes,mode:str)->bytes:
    raw=old.decode("utf-8")
    lines=raw.splitlines(keepends=True)
    indices=[i for i,s in enumerate(lines) if re.fullmatch(r"\s*RewriteEngine\s+On\s*",s,re.I)]
    if len(indices)!=1 or MARKER in raw:
        raise RuntimeError("unexpected host rewrite configuration")
    lines.insert(indices[0]+1,rule(mode))
    new="".join(lines).encode("utf-8")
    if new.replace(rule(mode).encode("utf-8"),b"",1)!=old:
        raise RuntimeError("existing rewrite bytes not preserved")
    if new.count(MARKER.encode("utf-8"))!=1 or new.count(URI.encode("utf-8"))!=1:
        raise RuntimeError("multiple sitemap rules")
    return new

def atomic(data:bytes):
    temp=HT.with_name(".mpw-sitemap-"+str(os.getpid()))
    fd=os.open(str(temp),os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    try:
        with os.fdopen(fd,"wb") as out:
            out.write(data);out.flush();os.fsync(out.fileno())
        os.chmod(temp,0o644)
        os.replace(temp,HT)
    finally:
        if temp.exists():temp.unlink()

def save(state):
    temp=PRIVATE/("sitemap-state-"+str(os.getpid()))
    fd=os.open(str(temp),os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,"w") as out:
        json.dump(state,out,sort_keys=True);out.flush();os.fsync(out.fileno())
    os.replace(temp,STATE)

def read():
    if STATE.is_symlink() or not STATE.is_file():raise RuntimeError("release state missing")
    return json.loads(STATE.read_text())

def watchdog():
    src="""from pathlib import Path
import hashlib,json,os,time
time.sleep(180)
p=Path('/home/zomorod2/.mpw-dynamic-sitemap-three-20261017')
ht=Path('/home/zomorod2/mojplaywin.com/.htaccess')
try:
    s=json.loads((p/'state.json').read_text())
    if s.get('status')!='armed':raise SystemExit
    old=(p/'original-htaccess').read_bytes()
    if hashlib.sha256(old).hexdigest()!=s['old_sha']:raise SystemExit
    if ht.is_symlink() or hashlib.sha256(ht.read_bytes()).hexdigest()!=s['new_sha']:raise SystemExit
    temp=ht.with_name('.mpw-sitemap-watchdog-'+str(os.getpid()))
    fd=os.open(str(temp),os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,'wb') as out:
        out.write(old);out.flush();os.fsync(out.fileno())
    os.chmod(temp,0o644)
    os.replace(temp,ht)
    (p/'state.json').write_text(json.dumps({**s,'status':'watchdog_reverted'},sort_keys=True))
except Exception:pass
"""
    WATCH.write_text(src,encoding="utf-8")
    os.chmod(WATCH,0o600)
    subprocess.Popen([sys.executable,str(WATCH)],stdin=subprocess.DEVNULL,
       stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True,close_fds=True)

def arm(mode:str,php_hash:str):
    verify(php_hash)
    original=HT.read_bytes()
    if not PRIVATE.exists():PRIVATE.mkdir(mode=0o700)
    if PRIVATE.stat().st_uid!=os.getuid() or PRIVATE.stat().st_mode&0o077:
        raise RuntimeError("private backup directory not secure")
    if STATE.exists() and read().get("status")=="armed":
        raise RuntimeError("previous release still armed")
    if BACKUP.is_symlink() or (BACKUP.exists() and BACKUP.read_bytes()!=original):
        raise RuntimeError("untrusted previous backup")
    if not BACKUP.exists():
        fd=os.open(str(BACKUP),os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        with os.fdopen(fd,"wb") as out:
            out.write(original);out.flush();os.fsync(out.fileno())
    new=candidate(original,mode)
    state={"status":"armed","mode":mode,"old_sha":EXPECTED_SHA,
           "new_sha":sha(new),"php_sha":php_hash}
    save(state)
    watchdog()
    atomic(new)
    if sha(HT.read_bytes())!=state["new_sha"]:
        raise RuntimeError("sitemap rule postwrite mismatch")
    print(json.dumps({"classification":"MOJ_PLAY_WIN_SITEMAP_AUGMENTATION_ARMED",
      "mode":mode,"old_sha":EXPECTED_SHA,"new_sha":state["new_sha"],
      "single_main_only_rule":True,"watchdog_seconds":180},sort_keys=True),flush=True)

def rollback():
    s=read()
    old=BACKUP.read_bytes()
    if sha(old)!=s["old_sha"]:raise RuntimeError("original backup damaged")
    live=sha(HT.read_bytes())
    if live not in (s["old_sha"],s["new_sha"]):raise RuntimeError("concurrent server config change")
    if live==s["new_sha"]:atomic(old)
    save({**s,"status":"rolled_back"})
    print("MOJ_PLAY_WIN_SITEMAP_ORIGINAL_NINE_RULE_CONFIG_RESTORED",flush=True)

def commit(php_hash:str):
    verify_after=read()
    if verify_after["mode"]!="production" or verify_after["status"]!="armed":
        raise RuntimeError("only armed production can commit")
    if sha(HT.read_bytes())!=verify_after["new_sha"] or php_hash!=verify_after["php_sha"]:
        raise RuntimeError("content drift during acceptance")
    if sha(PHP.read_bytes())!=php_hash:
        raise RuntimeError("reviewed sitemap PHP no longer matches")
    save({**verify_after,"status":"verified_committed"})
    print("MOJ_PLAY_WIN_DYNAMIC_SITEMAP_THREE_ADDITIONS_COMMITTED",flush=True)

if __name__=="__main__":
    try:
        cmd=sys.argv[1]
        if cmd in ("canary","production"):arm(cmd,sys.argv[2])
        elif cmd=="rollback":rollback()
        elif cmd=="commit":commit(sys.argv[2])
        else:raise RuntimeError("unsupported mode")
    except Exception as e:
        print("SITEMAP_RELEASE_REFUSED_"+type(e).__name__+"_"+str(e)[:150],file=sys.stderr)
        raise SystemExit(3)
