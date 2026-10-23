#!/usr/bin/env python3
"""Isolated MojPlayWin brand asset installer; no application, DB, or rewrite edits."""
import hashlib, json, os, pwd, re, shutil, stat, sys, tempfile
from pathlib import Path

HOME=Path("/home/zomorod2")
ROOT=HOME/"mojplaywin.com"
ITEMS={
  "header.jpg":"static/site/mojplaywin-header-emblem.jpg",
  "coin.png":"static/site/mojplaywin-coin-logo.420e0d1f954b.png",
  "favicon.ico":"favicon.ico",
  "apple-touch-icon.png":"apple-touch-icon.png",
  "android-chrome-192x192.png":"android-chrome-192x192.png",
  "android-chrome-512x512.png":"android-chrome-512x512.png",
}
MUST_EXIST={"header.jpg","coin.png"}
def sha(data): return hashlib.sha256(data).hexdigest()
def fail(msg): raise RuntimeError(msg)
def validate(run, folder):
    if not re.fullmatch(r"[0-9]{8,22}",run): fail("Invalid run")
    if pwd.getpwuid(os.getuid()).pw_name!="zomorod2": fail("Wrong account")
    if ROOT.is_symlink() or not ROOT.is_dir() or ROOT.resolve()!=ROOT: fail("Wrong docroot")
    h=ROOT/".htaccess"
    if h.is_symlink() or not h.is_file(): fail("Missing route guard")
    # This site serves several protected subsites: never touch routing, PHP, Django or Passenger.
    if not (ROOT/"passenger_wsgi.py").is_file(): fail("Unknown hosting layout")
    stage=HOME/(".mpw-brand-stage-"+run)
    if stage.is_symlink() or stage!=folder or not stage.is_dir(): fail("Untrusted stage")
    for name,rel in ITEMS.items():
        dest=ROOT/rel
        if dest.parent.is_symlink() or not dest.parent.is_dir(): fail("Unsafe destination folder")
        if dest.is_symlink() or (dest.exists() and not dest.is_file()): fail("Unsafe target "+rel)
        if name in MUST_EXIST and (not dest.is_file() or dest.stat().st_size<1000):
            fail("Existing MojPlayWin static brand asset missing: "+rel)
        src=stage/"bundle"/name
        if src.is_symlink() or not src.is_file() or src.stat().st_size<1000:
            fail("Missing output "+name)
        raw=src.read_bytes()
        if name.endswith(".png") and not raw.startswith(b"\x89PNG\r\n\x1a\n"):fail("Invalid PNG")
        if name.endswith(".jpg") and not raw.startswith(b"\xff\xd8"):fail("Invalid JPEG")
        if name.endswith(".ico") and not raw.startswith(b"\x00\x00\x01\x00"):fail("Invalid ICO")
    return stage,HOME/(".mpw-brand-backup-"+run)
def atomic(path, raw, mode):
    fd,tmp=tempfile.mkstemp(prefix=".mpw-brand-",dir=path.parent)
    try:
        os.fchmod(fd,mode)
        with os.fdopen(fd,"wb") as out:
            out.write(raw);out.flush();os.fsync(out.fileno())
        os.replace(tmp,path)
    finally:
        if os.path.lexists(tmp): os.unlink(tmp)
def install(run):
    stage,backup=validate(run,HOME/(".mpw-brand-stage-"+run))
    if backup.exists() or backup.is_symlink():fail("Backup collision")
    backup.mkdir(mode=0o700)
    records={}
    for name,rel in ITEMS.items():
        dest=ROOT/rel; before=dest.read_bytes() if dest.is_file() else None
        after=(stage/"bundle"/name).read_bytes()
        mode=stat.S_IMODE(dest.stat().st_mode) if before is not None else 0o644
        if before is not None:
            with (backup/name).open("xb") as fp:
                fp.write(before);fp.flush();os.fsync(fp.fileno())
            os.chmod(backup/name,0o600)
        records[name]={"path":rel,"existed":before is not None,
                       "old":sha(before) if before is not None else None,
                       "new":sha(after),"mode":mode}
    record={"run":run,"items":records}
    manifest=backup/"manifest.json"
    with manifest.open("x") as f:
        json.dump(record,f);f.flush();os.fsync(f.fileno())
    os.chmod(manifest,0o600)
    written=[]
    try:
        for name,rel in ITEMS.items():
            dest=ROOT/rel; item=records[name]
            if item["existed"] and sha(dest.read_bytes())!=item["old"]:fail("Concurrent edit "+rel)
            if not item["existed"] and dest.exists():fail("Concurrent create "+rel)
            atomic(dest,(stage/"bundle"/name).read_bytes(),item["mode"])
            written.append(name)
            if sha(dest.read_bytes())!=item["new"]:fail("Post-write mismatch "+rel)
    except Exception:
        for name in reversed(written):
            dest=ROOT/records[name]["path"]; item=records[name]
            if dest.is_file() and not dest.is_symlink() and sha(dest.read_bytes())==item["new"]:
                if item["existed"]: atomic(dest,(backup/name).read_bytes(),item["mode"])
                else: dest.unlink()
        raise
    print("MPW_BRAND_INSTALLED="+json.dumps({n:v["new"] for n,v in records.items()},sort_keys=True))
def rollback(run):
    stage,backup=validate(run,HOME/(".mpw-brand-stage-"+run))
    m=backup/"manifest.json"
    if m.is_symlink() or not m.is_file():fail("Backup manifest missing")
    record=json.loads(m.read_text())
    if record["run"]!=run or set(record["items"])!=set(ITEMS):fail("Backup manifest mismatch")
    # Check all targets before touching any of them; never overwrite concurrent edits.
    for name,rel in ITEMS.items():
        item=record["items"][name]; dest=ROOT/rel
        if item["path"]!=rel or not dest.is_file() or dest.is_symlink() or sha(dest.read_bytes())!=item["new"]:
            fail("Rollback refused: target changed "+rel)
        if item["existed"] and sha((backup/name).read_bytes())!=item["old"]:fail("Corrupt backup")
    for name,rel in ITEMS.items():
        item=record["items"][name]; dest=ROOT/rel
        if item["existed"]:atomic(dest,(backup/name).read_bytes(),item["mode"])
        else:dest.unlink()
    print("MPW_BRAND_ROLLBACK=PASS")
if __name__=="__main__":
    if len(sys.argv)!=3 or sys.argv[1] not in ("install","rollback"):fail("Usage: install|rollback run")
    {"install":install,"rollback":rollback}[sys.argv[1]](sys.argv[2])
