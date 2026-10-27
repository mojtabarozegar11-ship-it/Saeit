#!/usr/bin/env python3
"""Append verified MojPlayWin thematic collections to existing canonical sitemap."""
import hashlib
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import tempfile

ROOT=Path("/home/zomorod2/mojplaywin.com")
SITEMAP=ROOT/"design-preview-20261017/_mpw_sitemap_three_indexable_20261017.php"
BACKUP_ROOT=Path("/home/zomorod2/.mpw-architecture-backups")
MARKER="// MPW_EDITORIAL_COLLECTIONS_SITEMAP_20261027"
ANCHOR="// MPW_MAIN_NAV_SITEMAP_20261026: indexable navigational destinations"
SLUGS=("about","ventures-hospitality","agents","ventures-agriculture",
"ventures-jewelry-gold","industry","ventures-ecommerce","services","research",
"ventures-currency-crypto","ventures-carpets","company","studio",
"ventures-cafe-restaurant","knowledge","ventures-fuel-station","economy","market")
ROUTES=tuple("/mpw-editorial/collections/"+slug+"/index.html" for slug in SLUGS)

def sha(b):return hashlib.sha256(b).hexdigest()

def php_lint(data):
    fd,path=tempfile.mkstemp(prefix="mpw-sitemap-check-",suffix=".php",dir=str(BACKUP_ROOT))
    try:
        with os.fdopen(fd,"wb") as f:f.write(data)
        p=subprocess.run(["php","-l",path],capture_output=True,text=True,timeout=20)
        if p.returncode:raise RuntimeError("PHP lint rejected sitemap: "+p.stderr[-200:])
    finally:
        if os.path.exists(path):os.unlink(path)

def validate():
    if not SITEMAP.is_file() or SITEMAP.is_symlink():raise RuntimeError("Invalid exact sitemap")
    missing=[route for route in ROUTES if not (ROOT/route.lstrip("/")).is_file()]
    if missing:raise RuntimeError("Missing published collections: "+",".join(missing))
    raw=SITEMAP.read_bytes()
    text=raw.decode("utf-8")
    if text.count(ANCHOR)!=1:raise RuntimeError("Sitemap anchor mismatch")
    if text.count(MARKER)>1:raise RuntimeError("Duplicate insert marker")
    if MARKER in text:
        if not all(route in text for route in ROUTES):raise RuntimeError("Incomplete existing sitemap block")
        return raw,raw
    pattern=re.compile(re.escape(ANCHOR)+r"\s*\n\$paths = array_merge\(\$paths, \[[^\n]+\]\);")
    hits=list(pattern.finditer(text))
    if len(hits)!=1:raise RuntimeError("Cannot locate canonical navigation append block")
    insertion="\n"+MARKER+"\n$paths = array_merge($paths, ["+", ".join("'"+r+"'" for r in ROUTES)+"]);"
    m=hits[0]
    changed=(text[:m.end()]+insertion+text[m.end():]).encode("utf-8")
    if any(changed.decode().count(route)!=1 for route in ROUTES):
        raise RuntimeError("Sitemap duplicate route")
    php_lint(changed)
    return raw,changed

def write_atomic(path,data,mode):
    fd,tmp=tempfile.mkstemp(prefix=".mpw-map-arch-",dir=path.parent)
    try:
        os.fchmod(fd,mode)
        with os.fdopen(fd,"wb") as f:
            f.write(data);f.flush();os.fsync(f.fileno())
        os.replace(tmp,path)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)

def backup_path(run_id):
    if not re.fullmatch(r"\d{6,20}",run_id):raise RuntimeError("Invalid run ID")
    return BACKUP_ROOT/("sitemap-collections-"+run_id)

def main():
    action=sys.argv[1] if len(sys.argv)>1 else "preflight"
    if action=="selftest":
        assert len(ROUTES)==18 and len(set(ROUTES))==18
        assert all(p.endswith("/index.html") for p in ROUTES)
        print("MPW_MAP_COLLECTIONS_SELFTEST_OK",len(ROUTES))
        return
    if action=="preflight":
        raw,changed=validate()
        print("MPW_MAP_COLLECTIONS_PREFLIGHT_OK",len(raw),len(changed),len(ROUTES))
        return
    run_id=sys.argv[2]
    backup=backup_path(run_id)
    if action=="publish":
        raw,changed=validate()
        if raw==changed:
            print("MPW_MAP_COLLECTIONS_ALREADY_PRESENT")
            return
        backup.parent.mkdir(mode=0o700,exist_ok=True)
        if backup.exists():raise RuntimeError("Backup collision")
        backup.mkdir(mode=0o700)
        backup.chmod(0o700)
        write_atomic(backup/"sitemap.before.php",raw,0o600)
        (backup/"sha.before").write_text(sha(raw))
        (backup/"sha.after").write_text(sha(changed))
        if sha(SITEMAP.read_bytes())!=sha(raw):raise RuntimeError("Sitemap drift before publication")
        write_atomic(SITEMAP,changed,stat.S_IMODE(SITEMAP.stat().st_mode))
        print("MPW_MAP_COLLECTIONS_PUBLISHED",len(ROUTES),sha(changed)[:20])
    elif action=="rollback":
        if not backup.is_dir():raise RuntimeError("Missing rollback backup")
        before=(backup/"sitemap.before.php").read_bytes()
        expected=(backup/"sha.after").read_text().strip()
        if sha(SITEMAP.read_bytes())!=expected:raise RuntimeError("Changed sitemap: refusing rollback")
        if sha(before)!=(backup/"sha.before").read_text().strip():raise RuntimeError("Corrupt backup")
        write_atomic(SITEMAP,before,stat.S_IMODE(SITEMAP.stat().st_mode))
        print("MPW_MAP_COLLECTIONS_ROLLED_BACK")
    else:raise RuntimeError("Invalid mode")
if __name__=="__main__":main()
