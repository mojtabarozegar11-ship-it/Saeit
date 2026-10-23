#!/usr/bin/env python3
"""CPanel-local narrowly scoped Zomorod static publication.

Run only over fingerprint-pinned VPS relay, never in generic Django deploy.
Commands: prepare, rehearsal, apply, verify, finalize, rollback.
"""
from __future__ import annotations
import hashlib
import json
import os
import re
import shutil
import stat
import sys
import time
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path.home()
WEB = ROOT / "public_html"
BASE = ROOT / ".backups" / "zomorod-soil-moisture-two-tools-20261023"
LOCK = ROOT / ".locks" / "zomorod-agriculture-static"
RELEASE = "ZM-SOIL-MOISTURE-TOOLS-20261023-V1"
FOLDER = "agriculture/water-soil/"
ITEMS = (
    FOLDER + "soil-moisture-converter/index.html",
    FOLDER + "soil-water-storage/index.html",
)
CATEGORY = FOLDER + "index.html"
PROTECTED = (
    "index.html", ".htaccess", "agriculture/index.html",
    "agriculture/.htaccess", "games/index.html",
    "games/water-path/index.html", "games/air-supremacy/index.html",
    FOLDER + "irrigation-planner/index.html",
)
MARKER = "<!-- ZM-SOIL-MOISTURE-TOOLS-20261023-V1 -->"
BLOCK = (
    MARKER + '<section class="soil-moisture-tools-20261023" aria-labelledby="soil-moisture-lab-heading" '
    'style="margin:1.2rem auto;padding:1.2rem;border:1px solid #b09a58;border-radius:14px;background:#173e31;color:#fff">'
    '<h2 id="soil-moisture-lab-heading" style="color:#ffe2a1">ابزارهای علمی جدید رطوبت خاک</h2>'
    '<p>تبدیل اندازه‌گیری‌های آزمایشگاهی به رطوبت حجمی و محاسبه ذخیره آب قابل‌استفاده با داده‌های اندازه‌گیری‌شده.</p>'
    '<p><a style="color:#ffe2a1" href="/agriculture/water-soil/soil-moisture-converter/">محاسبه رطوبت وزنی و حجمی خاک</a>'
    ' &nbsp; | &nbsp; '
    '<a style="color:#ffe2a1" href="/agriculture/water-soil/soil-water-storage/">محاسبه ذخیره و کسری آب خاک</a></p></section>'
)

def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def realfile(rel: str, *, needed=True) -> Path:
    p = WEB / rel
    for parent in (WEB, *list(p.parents)[:-1]):
        if parent.exists() and parent.is_symlink():
            raise RuntimeError("SYMLINK_PARENT_BLOCKED " + str(parent))
    if p.is_symlink():
        raise RuntimeError("SYMLINK_FILE_BLOCKED " + rel)
    if needed and not p.is_file():
        raise RuntimeError("MISSING_PROTECTED_FILE " + rel)
    return p

def safe_paths():
    if not WEB.is_dir() or WEB.is_symlink():
        raise RuntimeError("INVALID_DOCROOT")
    if not (WEB / FOLDER).is_dir() or (WEB / FOLDER).is_symlink():
        raise RuntimeError("MISSING_SOIL_CATEGORY")
    for rel in (*PROTECTED, CATEGORY): realfile(rel)
    if any((WEB / r).exists() or (WEB / r).is_symlink() for r in ITEMS):
        raise RuntimeError("NEW_ROUTE_ALREADY_EXISTS_PRESERVE_NO_OVERWRITE")

def snapshot():
    d = {}
    for rel in (*PROTECTED, CATEGORY):
        p = realfile(rel)
        s = p.stat()
        d[rel] = {"sha256":digest(p.read_bytes()),"size":s.st_size,
                  "uid":s.st_uid,"gid":s.st_gid,"mode":stat.S_IMODE(s.st_mode)}
    return d

def place(run):
    if not re.fullmatch(r"\d{7,20}",run):
        raise RuntimeError("INVALID_RELEASE_RUN_ID")
    return BASE / run

def save(base, record):
    dest=base / "manifest.json"
    tmp=base / "manifest.json.tmp"
    tmp.write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding="utf-8")
    os.replace(tmp,dest)

def load(base):
    return json.loads((base/"manifest.json").read_text(encoding="utf-8"))

def claim(run):
    LOCK.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
    for attempt in range(15):
        try:
            LOCK.mkdir(mode=0o700)
            (LOCK/"owner").write_text(run,encoding="ascii")
            return
        except FileExistsError:
            time.sleep(2)
    owner=(LOCK/"owner").read_text(encoding="ascii") if (LOCK/"owner").is_file() else "unknown"
    raise RuntimeError("SHARED_LOCK_BUSY owner="+owner)

def unlock(run):
    if LOCK.is_dir() and not LOCK.is_symlink():
        if (LOCK/"owner").read_text(encoding="ascii").strip()!=run:
            raise RuntimeError("LOCK_NOT_OWNED")
        (LOCK/"owner").unlink()
        LOCK.rmdir()

def check_lock(run):
    if not LOCK.is_dir() or LOCK.is_symlink() or (LOCK/"owner").read_text(encoding="ascii").strip()!=run:
        raise RuntimeError("RELEASE_LOCK_NOT_OWNED")

def protected_unchanged(rec):
    for rel,meta in rec["before"].items():
        p=realfile(rel)
        if digest(p.read_bytes())!=meta["sha256"]:
            raise RuntimeError("PROTECTED_CHANGED_ABORT "+rel)

def prepare(run):
    safe_paths()
    b=place(run)
    if b.exists():raise RuntimeError("BACKUP_ALREADY_EXISTS")
    claim(run)
    try:
        b.mkdir(mode=0o700,parents=True)
        (b/"stage").mkdir()
        original=realfile(CATEGORY)
        shutil.copy2(original,b/"category-before.html")
        rec={"release_id":run,"release_marker":RELEASE,"state":"prepared",
             "created_at":time.strftime("%Y-%m-%dT%H:%M:%SZ",time.gmtime()),
             "docroot_verified":True,"before":snapshot(),"new_files":list(ITEMS),
             "created":[],"after":{},"rollback":"restore category-before.html if after SHA matches; remove only installed matching new tool dirs"}
        save(b,rec)
        print("PREPARE_BACKUP="+str(b))
        print("LOCK_CLAIMED=yes")
    except Exception:
        unlock(run)
        raise

def stage_check(b):
    filelist=json.loads((b/"stage/source-manifest.json").read_text(encoding="utf-8"))
    if set(filelist)!=set(ITEMS):raise RuntimeError("STAGING_UNEXPECTED_MANIFEST")
    for rel,meta in filelist.items():
        p=b/"stage"/rel
        if not p.is_file() or p.is_symlink() or digest(p.read_bytes())!=meta["sha256"]:
            raise RuntimeError("STAGING_HASH_MISMATCH "+rel)
        data=p.read_text(encoding="utf-8")
        if RELEASE not in data or '<html lang="fa" dir="rtl">' not in data:
            raise RuntimeError("STAGING_MARKER_OR_LANG_MISSING")
    return filelist

def candidate(base,original):
    if original.count("</main>")!=1:
        raise RuntimeError("CATEGORY_LAYOUT_UNEXPECTED")
    if MARKER in original:
        raise RuntimeError("CATEGORY_ALREADY_CONTAINS_RELEASE")
    return original.replace("</main>",BLOCK+"</main>",1)

def rehearsal(run):
    b=place(run);check_lock(run)
    rec=load(b);stage_check(b);protected_unchanged(rec)
    original=(b/"category-before.html").read_bytes()
    before=realfile(CATEGORY).read_bytes()
    if digest(original)!=digest(before):
        raise RuntimeError("CATEGORY_BEFORE_MISMATCH")
    proposed=candidate(b,before.decode("utf-8")).encode("utf-8")
    simulation=b/"rollback-rehearsal"
    simulation.mkdir(exist_ok=False)
    (simulation/"category.html").write_bytes(proposed)
    (simulation/"category.html").write_bytes(original)
    if digest((simulation/"category.html").read_bytes())!=rec["before"][CATEGORY]["sha256"]:
        raise RuntimeError("ISOLATED_ROLLBACK_REHEARSAL_FAILED")
    (b/"category-next.html").write_bytes(proposed)
    rec["state"]="rehearsed";rec["candidate_sha256"]=digest(proposed);save(b,rec)
    print("ISOLATED_ROLLBACK_REHEARSAL=PASS")

def rollback(run):
    b=place(run)
    rec=load(b)
    if rec["state"]=="live_verified":
        raise RuntimeError("VERIFIED_RELEASE_ROLLBACK_REQUIRES_SEPARATE_OWNER_AUTHORIZATION")
    check_lock(run)
    issues=[]
    category=realfile(CATEGORY)
    post=rec.get("after",{}).get(CATEGORY)
    if post:
        if digest(category.read_bytes())==post:
            orig=(b/"category-before.html")
            tmp=category.with_name(".soil-moisture-rollback-"+run)
            shutil.copy2(orig,tmp)
            os.replace(tmp,category)
            print("ROLLBACK_CATEGORY=RESTORED")
        elif digest(category.read_bytes())!=rec["before"][CATEGORY]["sha256"]:
            issues.append("CATEGORY_MODIFIED_EXTERNALLY")
    for rel in ITEMS:
        dest=WEB/rel
        expected=rec.get("after",{}).get(rel)
        if expected and dest.is_file() and not dest.is_symlink() and digest(dest.read_bytes())==expected:
            dest.unlink()
            try:dest.parent.rmdir()
            except OSError:pass
            print("ROLLBACK_NEW="+rel)
        elif dest.exists():
            issues.append("NEW_FILE_CHANGED_EXTERNALLY "+rel)
    rec["state"]="rolled_back" if not issues else "rollback_blocked"
    rec["rollback_issues"]=issues
    save(b,rec)
    if not issues:unlock(run)
    if issues:raise RuntimeError("ROLLBACK_CONFLICTS "+",".join(issues))

def apply(run):
    b=place(run);check_lock(run)
    rec=load(b)
    if rec["state"]!="rehearsed":raise RuntimeError("REHEARSAL_MISSING")
    stage_check(b)
    safe_paths();protected_unchanged(rec)
    category=realfile(CATEGORY)
    if digest(category.read_bytes())!=rec["before"][CATEGORY]["sha256"]:
        raise RuntimeError("CATEGORY_CHANGED_BEFORE_APPLY")
    after={}
    try:
        for rel in ITEMS:
            src=b/"stage"/rel
            dst=WEB/rel
            dst.parent.mkdir(mode=0o755,parents=False,exist_ok=False)
            # Move a single staged file into an initially absent, dedicated directory.
            os.replace(src,dst)
            os.chmod(dst,0o644)
            after[rel]=digest(dst.read_bytes())
            rec["created"].append(rel)
            rec["after"]=after.copy();save(b,rec)
        proposed=(b/"category-next.html").read_bytes()
        tmp=category.with_name(".soil-moisture-next-"+run)
        tmp.write_bytes(proposed)
        os.chmod(tmp,rec["before"][CATEGORY]["mode"])
        os.replace(tmp,category)
        after[CATEGORY]=digest(proposed)
        rec["after"]=after.copy();rec["state"]="installed";save(b,rec)
        print("ATOMIC_SCOPED_INSTALL=PASS")
    except Exception:
        # Manifest is persisted after each new file so rollback can be exact.
        rec=load(b)
        if digest(category.read_bytes())==rec.get("candidate_sha256"):
            rec["after"][CATEGORY]=rec["candidate_sha256"]
            save(b,rec)
        rollback(run)
        raise

def verify(run):
    b=place(run);check_lock(run)
    rec=load(b)
    if rec["state"]!="installed":raise RuntimeError("NOT_INSTALLED")
    for rel,sha in rec["after"].items():
        p=realfile(rel)
        if digest(p.read_bytes())!=sha:raise RuntimeError("INSTALLED_HASH_MISMATCH "+rel)
    for rel,meta in rec["before"].items():
        if rel!=CATEGORY and digest(realfile(rel).read_bytes())!=meta["sha256"]:
            raise RuntimeError("PROTECTED_CHANGED_AFTER "+rel)
    print("ORIGIN_SHA256_AND_PROTECTED_ROUTES=PASS")

def finalize(run):
    b=place(run);check_lock(run);rec=load(b)
    if rec["state"]!="installed":raise RuntimeError("NOT_READY_TO_FINALIZE")
    verify(run)
    rec["state"]="live_verified"
    rec["finished_at"]=time.strftime("%Y-%m-%dT%H:%M:%SZ",time.gmtime())
    save(b,rec)
    unlock(run)
    print("LIVE_VERIFIED_BACKUP_RECEIPT="+str(b/"manifest.json"))

if __name__=="__main__":
    if len(sys.argv)!=3:raise SystemExit("usage: installer.py prepare|rehearsal|apply|verify|finalize|rollback runid")
    command,run=sys.argv[1:]
    {"prepare":prepare,"rehearsal":rehearsal,"apply":apply,
     "verify":verify,"finalize":finalize,"rollback":rollback}[command](run)
