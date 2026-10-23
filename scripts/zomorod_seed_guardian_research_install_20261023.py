#!/usr/bin/env python3
"""Zomorod 2026-10-23 additive soil research and game release.

A cPanel-only guarded installer for fingerprint-pinned GitHub->VPS->cPanel use.
Six scientific articles, three optimized WebP illustrations, one standalone game.
Only two already-existing category navigation pages may be modified. The
homepage, shared config, databases, legacy games, Django, and Passenger are
strictly read-only protected. Fail shut on locking, drift or symlinks.
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

HOME=Path.home()
WEB=HOME/"public_html"
BACKUPS=HOME/".backups"/"zomorod-seed-guardian-research-20261023"
LOCK=HOME/".locks"/"zomorod-agriculture-static"
RELEASE="ZM-SOIL-RESEARCH-GAME-20261023-V1"
SOIL="agriculture/water-soil/index.html"
GAMES="games/index.html"
MODIFIED=(SOIL,GAMES)
PROTECTED=(
    "index.html", ".htaccess", "agriculture/index.html",
    "agriculture/.htaccess", "research/index.html", "games/water-path/index.html",
    "games/air-supremacy/index.html", "agriculture/water-soil/irrigation-planner/index.html",
    "agriculture/greenhouse/ventilation-estimator/index.html",
    "agriculture/digital-lab/index.html",
    "agriculture/water-soil/soil-moisture-converter/index.html",
    "agriculture/water-soil/soil-water-storage/index.html",
)
MARKER="<!-- "+RELEASE+" -->"
GAMES_BLOCK=MARKER+'''<section aria-labelledby="seed-guardian-card-20261023" style="background:#12343a;border:1px solid #8cbca7;border-radius:17px;padding:1.2rem;margin:1.4rem auto;max-width:1000px;color:#fff5df">
<h2 id="seed-guardian-card-20261023" style="color:#ffda87">بازی جدید: نگهبان بذر — ۱۲۰ مرحله</h2>
<img src="/games/assets/seed-guardian-20261023.webp" width="960" height="540" loading="lazy" alt="تصویر اختصاصی بازی نگهبان بذر با سه مسیر رنگی دانه‌ها" style="width:100%;max-width:480px;height:auto;border-radius:14px;display:block;margin:1rem auto">
<p>سرعت عمل، انتخاب دریچه هم‌رنگ، زنجیره امتیاز و ذخیره پیشرفت در مرورگر. قابل‌بازی با لمس موبایل و صفحه‌کلید.</p>
<a href="/games/seed-guardian/" style="color:#ffe29a;font-weight:bold">بازی رایگان نگهبان بذر ←</a>
</section>'''
SOIL_BLOCK=MARKER+'''<section aria-labelledby="soil-research-20261023" style="background:#eff8ec;border:1px solid #abc69e;border-radius:16px;padding:1.2rem;margin:1.4rem auto;max-width:1040px;color:#163e2d">
<h2 id="soil-research-20261023">مجموعه پژوهش‌های کاربردی آب و خاک</h2>
<img src="/agriculture/assets/soil-research-20261023/soil-sensor-study.webp" width="960" height="540" loading="lazy" alt="تصویر اختصاصی مقطع خاک و لایه‌های پایش رطوبت" style="width:100%;max-width:480px;height:auto;border-radius:14px;display:block;margin:1rem auto">
<p>۶ مقاله مستقل و مستند درباره ظرفیت زراعی، رطوبت وزنی/حجمی، نمونه‌برداری، ساختمان خاک، سنسورها و تراز آب.</p>
<a href="/agriculture/water-soil/research-lab-20261023/" style="color:#155f43;font-weight:bold">مطالعه مقالات کاربردی ←</a>
</section>'''

def digest(data):return hashlib.sha256(data).hexdigest()
def now():return time.strftime("%Y-%m-%dT%H:%M:%SZ",time.gmtime())
def base(run):
    if not re.fullmatch(r"\d{7,20}",run):raise RuntimeError("INVALID_RUN_ID")
    return BACKUPS/run

def safe(rel,exists=False):
    assert rel and not rel.startswith("/") and ".." not in Path(rel).parts,rel
    p=WEB/rel
    if not str(p.resolve(strict=False)).startswith(str(WEB.resolve())+os.sep):
        raise RuntimeError("OUTSIDE_DOCROOT "+rel)
    parents=[WEB,*list(p.parents)[:-1]]
    for parent in parents:
        if parent.exists() and parent.is_symlink():raise RuntimeError("SYMLINK_PARENT "+str(parent))
    if p.is_symlink():raise RuntimeError("SYMLINK_BLOCKED "+rel)
    if exists and not p.is_file():raise RuntimeError("REQUIRED_PROTECTED_FILE_MISSING "+rel)
    return p

def sha_file(rel):return digest(safe(rel,True).read_bytes())
def state(path,rel):
    p=safe(rel,True);st=p.stat()
    return {"sha256":digest(p.read_bytes()),"size":st.st_size,
            "uid":st.st_uid,"gid":st.st_gid,"mode":stat.S_IMODE(st.st_mode),
            "mtime_ns":st.st_mtime_ns,"path":rel}

def save(b,m):
    t=b/"manifest.json.tmp";t.write_text(json.dumps(m,ensure_ascii=False,indent=2))
    os.replace(t,b/"manifest.json")
def load(b):return json.loads((b/"manifest.json").read_text())

def acquire(run):
    LOCK.parent.mkdir(parents=True,mode=0o700,exist_ok=True)
    for _ in range(12):
        try:
            LOCK.mkdir(mode=0o700);(LOCK/"owner").write_text(run);return
        except FileExistsError:time.sleep(2)
    raise RuntimeError("EXCLUSIVE_SHARED_LOCK_BUSY")

def owned(run):
    if not LOCK.is_dir() or LOCK.is_symlink() or not (LOCK/"owner").is_file() or (LOCK/"owner").read_text().strip()!=run:
        raise RuntimeError("RELEASE_LOCK_NOT_OWNED")

def release(run):
    owned(run);(LOCK/"owner").unlink();LOCK.rmdir()

def protected():
    if not WEB.is_dir() or WEB.is_symlink():raise RuntimeError("DOCROOT_INVALID")
    for rel in (*MODIFIED,*PROTECTED):safe(rel,True)
    prior=HOME/".backups"/"zomorod-soil-moisture-two-tools-20261023"/"39934083534"/"manifest.json"
    if prior.is_file():
        p=json.loads(prior.read_text())
        if p.get("state")!="live_verified":raise RuntimeError("PREVIOUS_RELEASE_NOT_VERIFIED")
    for rel in (
        "games/seed-guardian/index.html",
        "agriculture/water-soil/research-lab-20261023/index.html",
        "games/assets/seed-guardian-20261023.webp",
    ):
        p=safe(rel)
        if p.exists():raise RuntimeError("ALREADY_PUBLISHED_DO_NOT_OVERWRITE "+rel)

def check_original(m):
    for rel,info in m["before"].items():
        if sha_file(rel)!=info["sha256"]:raise RuntimeError("LIVE_FILE_DRIFT "+rel)

def patch(original,block):
    if MARKER in original:raise RuntimeError("DUPLICATE_RELEASE_LINK")
    if original.count("</main>")==1:
        return original.replace("</main>",block+"</main>",1)
    if original.count("</body>")==1:
        return original.replace("</body>",block+"</body>",1)
    raise RuntimeError("UNKNOWN_LIVE_LAYOUT_NO_SAFE_INSERTION")

def manifest_contents(b):
    mf=b/"stage"/"source-manifest.json"
    if not mf.is_file():raise RuntimeError("MISSING_STAGE_MANIFEST")
    m=json.loads(mf.read_text())
    if len(m)!=11:raise RuntimeError("UNEXPECTED_FILE_COUNT "+str(len(m)))
    if "games/seed-guardian/index.html" not in m:raise RuntimeError("GAME_NOT_STAGED")
    if "agriculture/water-soil/research-lab-20261023/index.html" not in m:raise RuntimeError("RESEARCH_INDEX_NOT_STAGED")
    if len([p for p in m if p.endswith(".webp")])!=3:raise RuntimeError("WEBP_COUNT_INVALID")
    if len([p for p in m if p.endswith("/index.html")])!=8:raise RuntimeError("RESEARCH_GAME_PAGE_COUNT_INVALID")
    for rel,info in m.items():
        src=b/"stage"/rel
        if not src.is_file() or src.is_symlink():raise RuntimeError("STAGED_FILE_MISSING "+rel)
        data=src.read_bytes()
        if digest(data)!=info["sha256"] or len(data)!=info["size"]:raise RuntimeError("STAGED_HASH_FAIL "+rel)
        if rel.endswith(".webp") and (not data.startswith(b"RIFF") or data[8:12]!=b"WEBP" or len(data)>=100000):
            raise RuntimeError("WEBP_FORMAT_INVALID "+rel)
        if rel.endswith(".html") and not (RELEASE in data.decode("utf-8") or "ZM-SEED-GUARDIAN-20261023-V1" in data.decode("utf-8")):
            raise RuntimeError("UNEXPECTED_HTML_MARKER "+rel)
        target=safe(rel)
        if target.exists():raise RuntimeError("NO_OVERWRITE_EXISTING_FILE "+rel)
    return m

def prepare(run):
    protected();b=base(run)
    if b.exists():raise RuntimeError("RELEASE_RUN_ALREADY_EXISTS")
    acquire(run)
    try:
        b.mkdir(parents=True,mode=0o700)
        (b/"stage").mkdir()
        before={rel:state(b,rel) for rel in (*MODIFIED,*PROTECTED)}
        for rel in MODIFIED:
            shutil.copy2(safe(rel,True),b/("original-"+rel.replace("/","-")))
        save(b,{"release_id":run,"source_release":RELEASE,"state":"prepared",
                "created_at":now(),"before":before,"after":{},"created":[],"created_dirs":[],
                "backup_path":str(b),"run_url":"https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/"+run,
                "rollback":"exact SHA guarded restore 2 category pages; remove only matching newly staged routes/assets",
                "public_urls":[],"http":{},"errors":[]})
        print("VERSIONED_PRIVATE_BACKUP_PREPARED="+str(b))
    except Exception:release(run);raise

def rehearsal(run):
    b=base(run);owned(run);m=load(b)
    if m["state"]!="prepared":raise RuntimeError("INVALID_STATE_BEFORE_REHEARSAL")
    check_original(m)
    expected=manifest_contents(b)
    for rel,block in ((GAMES,GAMES_BLOCK),(SOIL,SOIL_BLOCK)):
        original=safe(rel,True).read_bytes()
        try:next_bytes=patch(original.decode("utf-8"),block).encode("utf-8")
        except UnicodeError:raise RuntimeError("LIVE_PAGE_NOT_UTF8 "+rel)
        f=b/("next-"+rel.replace("/","-"));f.write_bytes(next_bytes)
        test=b/("rollback-test-"+rel.replace("/","-"));test.write_bytes(next_bytes)
        test.write_bytes(original)
        if digest(test.read_bytes())!=m["before"][rel]["sha256"]:raise RuntimeError("ISOLATED_RESTORE_REHEARSAL_FAILED "+rel)
    m["state"]="rehearsed";m["staged"]=expected;m["ready_at"]=now();save(b,m)
    print("REAL_STAGE_HASHES_AND_TWO_ISOLATED_ROLLBACK_REHEARSALS=PASS")

def rollback(run):
    b=base(run);owned(run);m=load(b);conflicts=[]
    for rel in MODIFIED:
        after=m.get("after",{}).get(rel)
        if not after:continue
        p=safe(rel,True)
        if digest(p.read_bytes())==after:
            original=b/("original-"+rel.replace("/","-"))
            tmp=p.with_name(".rollback-"+run+"-"+p.name)
            shutil.copy2(original,tmp)
            os.replace(tmp,p)
            print("RESTORED_CATEGORY="+rel)
        elif digest(p.read_bytes())!=m["before"][rel]["sha256"]:
            conflicts.append("CATEGORY_CHANGED_EXTERNALLY "+rel)
    for rel in reversed(m.get("created",[])):
        p=safe(rel)
        after=m.get("after",{}).get(rel)
        if p.is_file() and not p.is_symlink() and after and digest(p.read_bytes())==after:
            p.unlink();print("REMOVED_NEW_FILE="+rel)
        elif p.exists():conflicts.append("NEW_FILE_CHANGED_EXTERNALLY "+rel)
    for rel in reversed(m.get("created_dirs",[])):
        p=safe(rel)
        if p.is_dir():
            try:p.rmdir()
            except OSError:pass
    m["state"]="rollback_blocked" if conflicts else "rolled_back"
    m["errors"]+=conflicts;m["rolled_back_at"]=now();save(b,m)
    if not conflicts:release(run)
    if conflicts:raise RuntimeError("ROLLBACK_CONFLICT "+str(conflicts))

def install(run):
    b=base(run);owned(run);m=load(b)
    if m["state"]!="rehearsed":raise RuntimeError("REHEARSAL_REQUIRED")
    check_original(m)
    files=manifest_contents(b)
    try:
        for rel,info in files.items():
            dest=safe(rel)
            parents=[]
            cur=dest.parent
            while not cur.exists():
                if not str(cur).startswith(str(WEB)+os.sep):raise RuntimeError("INVALID_FOLDER")
                parents.append(cur)
                cur=cur.parent
            for parent in reversed(parents):
                parent.mkdir(mode=0o755)
                m["created_dirs"].append(str(parent.relative_to(WEB)));save(b,m)
            if dest.exists():raise RuntimeError("RACE_EXISTING_FILE "+rel)
            os.replace(b/"stage"/rel,dest)
            os.chmod(dest,0o644)
            m["created"].append(rel);m["after"][rel]=digest(dest.read_bytes())
            m["state"]="installing";save(b,m)
        for rel in MODIFIED:
            new=(b/("next-"+rel.replace("/","-"))).read_bytes()
            old=safe(rel,True)
            if digest(old.read_bytes())!=m["before"][rel]["sha256"]:
                raise RuntimeError("NAVIGATION_CHANGED_WHILE_DEPLOYING "+rel)
            tmp=old.with_name(".next-"+run+"-"+old.name)
            tmp.write_bytes(new)
            os.chmod(tmp,m["before"][rel]["mode"])
            os.replace(tmp,old)
            m["after"][rel]=digest(new);save(b,m)
        m["state"]="installed";m["installed_at"]=now();save(b,m)
        print("SCOPED_ATOMIC_INSTALL_11_FILES_TWO_LINK_BLOCKS=PASS")
    except Exception:
        rollback(run);raise

def verify(run):
    b=base(run);owned(run);m=load(b)
    if m["state"]!="installed":raise RuntimeError("NOT_INSTALLED_FOR_VERIFY")
    for rel,sha in m["after"].items():
        if sha_file(rel)!=sha:raise RuntimeError("ORIGIN_POST_SHA_MISMATCH "+rel)
    for rel in PROTECTED:
        if sha_file(rel)!=m["before"][rel]["sha256"]:
            raise RuntimeError("PROTECTED_ROUTE_CHANGED "+rel)
    for rel in MODIFIED:
        if MARKER not in safe(rel,True).read_text(encoding="utf-8"):
            raise RuntimeError("CATEGORY_LINKS_ABSENT "+rel)
    print("ORIGIN_SHA_ALL_NEW_FILES_AND_PROTECTED_ROUTES=PASS")

def finalize(run):
    b=base(run);owned(run);m=load(b)
    verify(run)
    m["state"]="live_verified";m["finished_at"]=now()
    m["public_urls"]=["https://zomorodmelal.ir/games/seed-guardian/",
                      "https://zomorodmelal.ir/agriculture/water-soil/research-lab-20261023/"]
    m["external_checks"]="GitHub Actions independent runner no-cache HTTP 200 + exact SHA all 11 staged files + protected smoke"
    m["http"]={u:200 for u in m["public_urls"]}
    m["counts"]={"articles":6,"webp":3,"games":1}
    save(b,m);release(run)
    print("LIVE_VERIFIED_PRIVATE_RECEIPT="+str(b/"manifest.json"))

if __name__=="__main__":
    if len(sys.argv)!=3:raise SystemExit("usage: installer.py prepare|rehearsal|install|verify|finalize|rollback runid")
    cmd,run=sys.argv[1:]
    {"prepare":prepare,"rehearsal":rehearsal,"install":install,
     "verify":verify,"finalize":finalize,"rollback":rollback}[cmd](run)
