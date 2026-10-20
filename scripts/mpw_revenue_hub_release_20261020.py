#!/usr/bin/env python3
"""Fail-closed isolated MojPlayWin static revenue hub publisher/rollback."""
import hashlib, io, json, os, re, shutil, stat, sys, tarfile
from pathlib import Path

ROOT=Path("/home/zomorod2/mojplaywin.com/mpw-editorial")
HOME=Path("/home/zomorod2")
SLUGS=['website-doctor','landing-page-studio','ai-automation','business-spreadsheets','website-templates','social-media-kits','resume-builder','logo-studio','browser-games','marketing-ai','business-calculators','website-care']
EXPECTED={"earn/index.html","earn/catalog.json","earn/sitemap.xml","earn/assets/style.css"}
EXPECTED.update("earn/"+slug+"/index.html" for slug in SLUGS)
def fail(message): raise RuntimeError(message)
def guard():
    if ROOT.is_symlink() or not ROOT.is_dir() or ROOT.resolve()!=ROOT or ROOT.name!="mpw-editorial" or not (ROOT/"index.html").is_file() or not (ROOT.parent/".htaccess").is_file():fail("Unexpected editorial static root")
    if (ROOT/"revenue").is_symlink():fail("Symlinked revenue path")
def paths(run):
    if not re.fullmatch(r"[0-9]{8,20}",run):fail("Invalid release ID")
    return ROOT/"revenue", ROOT/(".revenue-stage-"+run), HOME/(".mpw-revenue-backup-"+run)
def sha(b):return hashlib.sha256(b).hexdigest()
def safe_tree(path):
    if path.is_symlink():fail("Symlinked directory")
    if path.exists():
        for d, dirs, files in os.walk(path,followlinks=False):
            for name in dirs+files:
                if (Path(d)/name).is_symlink():fail("Unexpected symlink in managed earn tree")
def publish(run):
    guard()
    target,stage,backup=paths(run)
    if stage.exists() or stage.is_symlink() or backup.exists() or backup.is_symlink():fail("Release collision")
    if target.exists():
        safe_tree(target)
        if not target.is_dir() or not (target/".mpw-revenue-release.json").is_file():
            fail("Existing /earn/ is not owned by this publisher")
    data=sys.stdin.buffer.read(1500000)
    if len(data)==1500000 or not data:fail("Release archive too large or empty")
    try:
        tf=tarfile.open(fileobj=io.BytesIO(data),mode="r:gz")
        members=tf.getmembers()
        names={m.name.removeprefix("./") for m in members if m.isfile()}
        if names!=EXPECTED:fail("Manifest whitelist mismatch")
        if any(m.issym() or m.islnk() or not (m.isfile() or m.isdir()) for m in members):fail("Unsafe archive entry")
        docs={}
        for m in members:
            if not m.isfile():continue
            name=m.name.removeprefix("./")
            if m.size>220000:fail("Oversized document")
            payload=tf.extractfile(m).read()
            if len(payload)!=m.size:fail("Archive short read")
            payload=payload.replace(b"/earn/",b"/mpw-editorial/revenue/")
            docs[name]=payload
    except (tarfile.TarError, OSError, UnicodeError) as exc:fail("Invalid archive: "+type(exc).__name__)
    if b"https://mojplaywin.com/mpw-editorial/revenue/" not in docs["earn/index.html"]:fail("Missing canonical main hub")
    if docs["earn/index.html"].count(b'/mpw-editorial/revenue/')<12:fail("Insufficient catalog links")
    if b"<urlset" not in docs["earn/sitemap.xml"]:fail("Invalid sitemap")
    stage.mkdir(mode=0o755)
    stage.chmod(0o755)
    try:
        checks={}
        for path,body in docs.items():
            rel=Path(path).relative_to("earn")
            p=stage/rel
            p.parent.mkdir(parents=True,exist_ok=True)
            p.parent.chmod(0o755)
            p.write_bytes(body)
            p.chmod(0o644)
            checks[str(rel)]=sha(body)
        (stage/".mpw-revenue-release.json").write_text(json.dumps({"run":run,"sha256":checks},sort_keys=True)+"\n")
        (stage/".mpw-revenue-release.json").chmod(0o644)
        for rel,digest in checks.items():
            if sha((stage/rel).read_bytes())!=digest:fail("Stage file integrity mismatch")
        had_old=target.exists()
        if had_old:os.replace(target,backup)
        try:os.replace(stage,target)
        except BaseException:
            if had_old and backup.exists():os.replace(backup,target)
            raise
        print("MPW_REVENUE_HUB_PUBLISHED="+json.dumps({"run":run,"files":len(checks),"only_static_earn":True,"payment_flags_modified":False,"old_earn_backed_up":had_old}))
    finally:
        if stage.exists():shutil.rmtree(stage)
def rollback(run):
    guard()
    target,stage,backup=paths(run)
    if not target.is_dir() or target.is_symlink():fail("Missing release target")
    meta=target/".mpw-revenue-release.json"
    if not meta.is_file() or meta.is_symlink():fail("Release ownership marker missing")
    doc=json.loads(meta.read_text())
    if doc.get("run")!=run:fail("Refuse rollback over newer release")
    safe_tree(target)
    for rel,digest in doc["sha256"].items():
        if sha((target/rel).read_bytes())!=digest:fail("Modified target; refuse destructive rollback")
    shutil.rmtree(target)
    if backup.exists():
        if backup.is_symlink():fail("Unsafe backup")
        os.replace(backup,target)
    print("MPW_REVENUE_HUB_ROLLBACK=VERIFIED")
if __name__=="__main__":
    if len(sys.argv)!=3 or sys.argv[1] not in ("publish","rollback"):raise SystemExit("publish|rollback RUN_ID")
    (publish if sys.argv[1]=="publish" else rollback)(sys.argv[2])
