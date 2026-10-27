#!/usr/bin/env python3
"""Register one verified common editorial policy in the MojPlayWin XML sitemap."""
from pathlib import Path
import hashlib
import os
import re
import stat
import subprocess
import sys
import tempfile

ROOT=Path("/home/zomorod2/mojplaywin.com")
SITE_MAP=ROOT/"design-preview-20261017/_mpw_sitemap_three_indexable_20261017.php"
TARGET="/mpw-editorial/editorial-standards/index.html"
ANCHOR="// MPW_EDITORIAL_COLLECTIONS_SITEMAP_20261027"
MARKER="// MPW_EDITORIAL_EVIDENCE_POLICY_SITEMAP_20261027"
PRIVATE=Path("/home/zomorod2/.mpw-architecture-backups")

def digest(data):return hashlib.sha256(data).hexdigest()

def validated():
    target=ROOT/TARGET.lstrip("/")
    if target.is_symlink() or not target.is_file() or b'Research and evidence standards' not in target.read_bytes():
        raise RuntimeError("Policy target not published correctly")
    if SITE_MAP.is_symlink() or not SITE_MAP.is_file():raise RuntimeError("Unexpected sitemap target")
    raw=SITE_MAP.read_bytes()
    source=raw.decode("utf-8")
    if source.count(ANCHOR)!=1:raise RuntimeError("Missing validated sitemap anchor")
    if MARKER in source:
        if source.count(MARKER)!=1 or source.count(TARGET)!=1:raise RuntimeError("Damaged existing policy map")
        return raw,raw
    inserted="\n"+MARKER+"\n$paths = array_merge($paths, ['"+TARGET+"']);"
    patched=source.replace(ANCHOR,ANCHOR+inserted,1)
    if patched.count(TARGET)!=1 or patched.count(MARKER)!=1:raise RuntimeError("Bad sitemap insertion")
    fd,tmp=tempfile.mkstemp(prefix="mpw-editorial-policy-",suffix=".php",dir=PRIVATE)
    try:
        with os.fdopen(fd,"wb") as f:f.write(patched.encode("utf-8"))
        lint=subprocess.run(["php","-l",tmp],capture_output=True,text=True,timeout=20)
        if lint.returncode:raise RuntimeError("PHP validation failed "+lint.stderr[-200:])
    finally:
        if os.path.exists(tmp):os.unlink(tmp)
    return raw,patched.encode("utf-8")

def atom(path,data,mode):
    fd,tmp=tempfile.mkstemp(prefix=".mpw-policy-sitemap-",dir=path.parent)
    try:
        os.fchmod(fd,mode)
        with os.fdopen(fd,"wb") as f:f.write(data);f.flush();os.fsync(f.fileno())
        os.replace(tmp,path)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)

def backup_path(run_id):
    if not re.fullmatch(r"\d{6,20}",run_id):raise ValueError("Invalid run ID")
    return PRIVATE/("editorial-policy-sitemap-"+run_id)

def main():
    action=sys.argv[1] if len(sys.argv)>1 else "preflight"
    if action=="selftest":
        assert TARGET.endswith("/index.html") and "SITEMAP" in MARKER
        print("MPW_POLICY_SITEMAP_SELFTEST_OK");return
    if action=="preflight":
        before,after=validated()
        print("MPW_POLICY_SITEMAP_PREFLIGHT_OK",len(before),len(after));return
    backup=backup_path(sys.argv[2])
    if action=="publish":
        before,after=validated()
        if before==after:print("MPW_POLICY_SITEMAP_ALREADY_REGISTERED");return
        if backup.exists():raise RuntimeError("Backup collision")
        backup.mkdir(mode=0o700)
        backup.chmod(0o700)
        atom(backup/"before.php",before,0o600)
        (backup/"after.sha").write_text(digest(after))
        if digest(SITE_MAP.read_bytes())!=digest(before):raise RuntimeError("Concurrent sitemap update")
        atom(SITE_MAP,after,stat.S_IMODE(SITE_MAP.stat().st_mode))
        print("MPW_POLICY_SITEMAP_PUBLISHED",TARGET,digest(after)[:20])
    elif action=="rollback":
        before=(backup/"before.php").read_bytes()
        after_hash=(backup/"after.sha").read_text().strip()
        if digest(SITE_MAP.read_bytes())!=after_hash:raise RuntimeError("Sitemap changed since release")
        atom(SITE_MAP,before,stat.S_IMODE(SITE_MAP.stat().st_mode))
        print("MPW_POLICY_SITEMAP_ROLLED_BACK")
    else:raise RuntimeError("Unsupported mode")
if __name__=="__main__":main()
