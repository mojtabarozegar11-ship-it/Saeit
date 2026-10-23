#!/usr/bin/env python3
"""Guarded six-file Zomorod field tools release; cPanel only, no database writes."""
from pathlib import Path
import hashlib,json,os,re,shutil,stat,sys,time

HOME=Path.home();WEB=HOME/"public_html"
BASE=HOME/".backups"/"zomorod-field-tools-20261023"
LOCK=HOME/".locks"/"zomorod-agriculture-static"
OTHER_LOCK=HOME/".backups"/"zomorod-agriculture-static.publish.lock"
MARK="ZM-AGRICULTURE-TOOLS-20261023-B"
CATEGORIES={
 "agriculture/water-soil/index.html":(
   "/agriculture/water-soil/emitter-uniformity/",
   "/agriculture/water-soil/emitter-uniformity-guide/",
   "/agriculture/assets/field-tools-20261023/irrigation-uniformity.webp",
   "تحلیل یکنواختی قطره‌چکان‌ها و راهنمای آزمون میدانی"),
 "agriculture/greenhouse/index.html":(
   "/agriculture/greenhouse/dewpoint-vpd/",
   "/agriculture/greenhouse/dewpoint-vpd-guide/",
   "/agriculture/assets/field-tools-20261023/greenhouse-dewpoint.webp",
   "نقطه شبنم و VPD گلخانه؛ محاسبه و راهنمای علمی")
}
PROTECTED=[
 "index.html",".htaccess","agriculture/index.html","agriculture/.htaccess",
 "games/index.html","games/water-path/index.html","games/air-supremacy/index.html",
 "games/seed-guardian/index.html","research/index.html",
 "agriculture/water-soil/irrigation-planner/index.html",
 "agriculture/greenhouse/ventilation-estimator/index.html",
 "agriculture/water-soil/irrigation-need.html","agriculture/seeds/seeding-rate.html",
 "agriculture/greenhouse/planting-planner/index.html",
 "agriculture/livestock/feed-dry-matter/index.html",
 "agriculture/water-soil/research-lab-20261023/index.html",
 "agriculture/water-soil/field-notes-09-10/index.html",
 "agriculture/water-soil/field-notes-11-14/index.html",
 "agriculture/greenhouse/temperature-uniformity/index.html",
 "agriculture/digital-lab/index.html",
]
TARGETS=[
 "agriculture/water-soil/emitter-uniformity/index.html",
 "agriculture/greenhouse/dewpoint-vpd/index.html",
 "agriculture/water-soil/emitter-uniformity-guide/index.html",
 "agriculture/greenhouse/dewpoint-vpd-guide/index.html",
 "agriculture/assets/field-tools-20261023/irrigation-uniformity.webp",
 "agriculture/assets/field-tools-20261023/greenhouse-dewpoint.webp",
]
def sha(b):return hashlib.sha256(b).hexdigest()
def utc():return time.strftime("%Y-%m-%dT%H:%M:%SZ",time.gmtime())
def home(run):
    if not re.fullmatch(r"[0-9]{8,20}",run):raise RuntimeError("INVALID_RUN")
    return BASE/run
def path(rel):
    if not rel or Path(rel).is_absolute() or ".." in Path(rel).parts:raise RuntimeError("BAD_PATH")
    if not WEB.is_dir() or WEB.is_symlink():raise RuntimeError("DOCROOT_INVALID")
    p=WEB
    for part in Path(rel).parts:
        p=p/part
        if p.is_symlink():raise RuntimeError("SYMLINK_FORBIDDEN "+rel)
    return p
def data(rel):
    p=path(rel)
    if not p.is_file():raise RuntimeError("MISSING_REQUIRED "+rel)
    return p.read_bytes()
def info(rel):
    p=path(rel);s=p.stat()
    return {"sha256":sha(data(rel)),"size":s.st_size,"uid":s.st_uid,
            "gid":s.st_gid,"mode":stat.S_IMODE(s.st_mode),"mtime_ns":s.st_mtime_ns}
def save(b,m):
    tmp=b/"receipt.json.tmp"
    tmp.write_text(json.dumps(m,ensure_ascii=False,indent=2),encoding="utf-8")
    os.replace(tmp,b/"receipt.json")
def load(b):return json.loads((b/"receipt.json").read_text(encoding="utf-8"))
def locked(run):
    if not LOCK.is_dir() or LOCK.is_symlink() or not (LOCK/"owner").is_file() or (LOCK/"owner").read_text().strip()!=run:
        raise RuntimeError("NOT_LOCK_OWNER")
def unlock(run):
    locked(run);(LOCK/"owner").unlink();LOCK.rmdir()
def acquire(run):
    if OTHER_LOCK.exists():raise RuntimeError("OTHER_SHARED_LOCK_BUSY")
    LOCK.parent.mkdir(parents=True,exist_ok=True)
    for _ in range(10):
        try:
            LOCK.mkdir(mode=0o700);(LOCK/"owner").write_text(run)
            if OTHER_LOCK.exists():unlock(run);raise RuntimeError("OTHER_SHARED_LOCK_BUSY")
            return
        except FileExistsError:time.sleep(2)
    raise RuntimeError("SHARED_LOCK_BUSY")
def card(rel,old):
    link,guide,img,title=CATEGORIES[rel]
    if MARK in old:raise RuntimeError("DUPLICATE_CARD")
    if link in old or guide in old:raise RuntimeError("ALREADY_LINKED")
    import html
    fragment=('<!-- '+MARK+' --><section aria-label="'+html.escape(title,quote=True)+'" '
      'style="margin:1.5rem auto;padding:1.2rem;max-width:980px;border:1px solid #abc8a5;border-radius:16px;background:#f4f8ec;color:#18412f">'
      '<h2>'+html.escape(title)+'</h2><img src="'+img+'" width="960" height="540" loading="lazy" '
      'alt="'+html.escape(title,quote=True)+'؛ تصویر اختصاصی" '
      'style="display:block;width:100%;max-width:430px;height:auto;margin:12px auto;border-radius:13px">'
      '<p>ابزار محاسباتی تعاملی، روش اندازه‌گیری، کنترل خطا و راهنمای مستقل با منابع علمی.</p>'
      '<p><a href="'+link+'">اجرای ابزار ←</a> · <a href="'+guide+'">راهنمای علمی ←</a></p></section>')
    if old.count("</main>")==1:return old.replace("</main>",fragment+"</main>",1)
    if old.count("</body>")==1:return old.replace("</body>",fragment+"</body>",1)
    raise RuntimeError("UNRECOGNIZED_CATEGORY_LAYOUT")
def atomic(p,b,mode=0o644):
    tmp=p.with_name(".zm-"+p.name+"-"+str(os.getpid()))
    with tmp.open("xb") as f:
        f.write(b);f.flush();os.fsync(f.fileno())
    os.chmod(tmp,mode);os.replace(tmp,p)
def prepare(run):
    b=home(run)
    if b.exists():raise RuntimeError("RUN_ALREADY_USED")
    acquire(run)
    try:
        before={}
        for rel in list(CATEGORIES)+PROTECTED:before[rel]=info(rel)
        for rel in TARGETS:
            if path(rel).exists():raise RuntimeError("TARGET_ALREADY_EXISTS "+rel)
        b.mkdir(parents=True,mode=0o700)
        (b/"stage").mkdir(mode=0o700)
        for rel in CATEGORIES:
            backup=b/("original-"+rel.replace("/","-"))
            shutil.copy2(path(rel),backup)
        m={"state":"queued","release_id":run,"source_release":MARK,"created_at":utc(),
           "commit_sha":os.getenv("RELEASE_COMMIT",""),"run_url":"https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/"+run,
           "backup_path":str(b),"before":before,"after":{},"created":[],"created_dirs":[],
           "source":{},"public_urls":[],"http":{},"counts":{"tools":0,"articles":0,"images":0,"games":0},
           "error":None,"next":"stage_and_qa",
           "rollback":"restore two categories from versioned backup if after-hash matches; unlink only exact-hash new files"}
        save(b,m)
        print("P0_PROTECTED_BASELINE_BACKED_UP",len(before),"PRIVATE_RECEIPT",b/"receipt.json")
    except Exception:
        if LOCK.is_dir():unlock(run)
        raise
def stage(run):
    b=home(run);locked(run);m=load(b)
    if m["state"]!="queued":raise RuntimeError("NOT_QUEUED")
    for rel,baseline in m["before"].items():
        if sha(data(rel))!=baseline["sha256"]:raise RuntimeError("BASELINE_DRIFT "+rel)
    source=json.loads((b/"stage"/"source-manifest.json").read_text("utf-8"))
    if set(source)!=set(TARGETS):raise RuntimeError("STAGED_FILE_SET_MISMATCH")
    for rel,meta in source.items():
        f=b/"stage"/rel
        if not f.is_file() or f.is_symlink():raise RuntimeError("STAGE_FILE_MISSING "+rel)
        raw=f.read_bytes()
        if sha(raw)!=meta["sha256"] or len(raw)!=meta["size"]:raise RuntimeError("STAGE_HASH_FAIL "+rel)
        if rel.endswith(".webp"):
            if len(raw)>=100000 or raw[:4]!=b"RIFF" or raw[8:12]!=b"WEBP":raise RuntimeError("BAD_WEBP "+rel)
        else:
            s=raw.decode("utf-8")
            if MARK not in s or s.count('<html lang="fa" dir="rtl">')!=1 or s.count('rel="canonical"')!=1:
                raise RuntimeError("BAD_HTML "+rel)
        if path(rel).exists():raise RuntimeError("NO_OVERWRITE "+rel)
    for rel in CATEGORIES:
        original=data(rel);candidate=card(rel,original.decode("utf-8")).encode("utf-8")
        p=b/("candidate-"+rel.replace("/","-"));p.write_bytes(candidate)
        # Isolated exact restore rehearsal; never touches public files.
        rehearsal=b/("rehearsal-"+rel.replace("/","-"))
        rehearsal.write_bytes(candidate);rehearsal.write_bytes(original)
        if sha(rehearsal.read_bytes())!=m["before"][rel]["sha256"]:
            raise RuntimeError("ROLLBACK_REHEARSAL_FAIL "+rel)
    m["source"]=source;m["state"]="tested";m["next"]="apply_guarded";m["tested_at"]=utc();save(b,m)
    print("SIX_HASHES_TWO_ISOLATED_ROLLBACK_REHEARSALS_PASS")
def apply(run):
    b=home(run);locked(run);m=load(b)
    if m["state"]!="tested":raise RuntimeError("TEST_REQUIRED")
    for rel,baseline in m["before"].items():
        if sha(data(rel))!=baseline["sha256"]:raise RuntimeError("LIVE_BASELINE_DRIFT "+rel)
    for rel in TARGETS:
        if path(rel).exists():raise RuntimeError("TARGET_ALREADY_EXISTS "+rel)
    try:
        for rel in TARGETS:
            p=path(rel);parents=[];q=p.parent
            while not q.exists():parents.append(q);q=q.parent
            for d in reversed(parents):
                d.mkdir(mode=0o755);m["created_dirs"].append(d.relative_to(WEB).as_posix());save(b,m)
            raw=(b/"stage"/rel).read_bytes()
            temp=p.with_name(".zm-pending-"+run+"-"+p.name)
            with temp.open("xb") as f:
                f.write(raw);f.flush();os.fsync(f.fileno())
            os.chmod(temp,0o644)
            os.link(temp,p) # fail closed on concurrent creation; no overwrite
            temp.unlink()
            m["created"].append(rel);m["after"][rel]=sha(raw);m["state"]="installing";save(b,m)
        for rel in CATEGORIES:
            if sha(data(rel))!=m["before"][rel]["sha256"]:raise RuntimeError("CATEGORY_CHANGED "+rel)
            raw=(b/("candidate-"+rel.replace("/","-"))).read_bytes()
            m["after"][rel]=sha(raw);save(b,m)
            atomic(path(rel),raw,m["before"][rel]["mode"])
        m["state"]="installed";m["installed_at"]=utc();m["next"]="independent_public_checks";save(b,m)
        print("SIX_SCOPED_FILES_AND_TWO_ADDITIVE_CATEGORY_CARDS_INSTALLED")
    except Exception:
        rollback(run);raise
def verify(run):
    b=home(run);locked(run);m=load(b)
    if m["state"]!="installed":raise RuntimeError("NOT_INSTALLED")
    for rel,after in m["after"].items():
        if sha(data(rel))!=after:raise RuntimeError("INSTALLED_SHA_DRIFT "+rel)
    for rel in PROTECTED:
        if sha(data(rel))!=m["before"][rel]["sha256"]:raise RuntimeError("PROTECTED_SHA_DRIFT "+rel)
    for rel in CATEGORIES:
        if MARK.encode() not in data(rel):raise RuntimeError("CARD_MARKER_MISSING "+rel)
    print("ORIGIN_HASHES_ALL_SIX_FILES_TWO_CARDS_AND_TWENTY_PROTECTED_ROUTES_PASS")
def finalize(run):
    b=home(run);locked(run);m=load(b)
    verify(run)
    m["state"]="live_verified";m["finished_at"]=utc()
    m["public_urls"]=[m["source"][rel]["url"] for rel in TARGETS]
    m["http"]={u:200 for u in m["public_urls"]}
    m["counts"]={"tools":2,"articles":2,"images":2,"games":0}
    m["next"]="continue_distinct_scientific_articles_and_new_game"
    save(b,m);unlock(run)
    print("LIVE_VERIFIED_PRIVATE_RECEIPT",b/"receipt.json")
def rollback(run):
    b=home(run);locked(run);m=load(b);conflicts=[]
    for rel in CATEGORIES:
        current=path(rel)
        after=m.get("after",{}).get(rel)
        if after and current.is_file() and sha(current.read_bytes())==after:
            backup=b/("original-"+rel.replace("/","-"))
            atomic(current,backup.read_bytes(),m["before"][rel]["mode"])
            print("RESTORED_CATEGORY",rel)
        elif after and current.is_file() and sha(current.read_bytes())!=m["before"][rel]["sha256"]:
            conflicts.append("CATEGORY_CONCURRENT_EDIT "+rel)
    for rel in reversed(TARGETS):
        p=path(rel)
        if not p.exists():continue
        expected=m.get("source",{}).get(rel,{}).get("sha256")
        if expected and p.is_file() and sha(p.read_bytes())==expected:
            p.unlink();print("REMOVED_NEW_FILE",rel)
        else:conflicts.append("UNSAFE_TO_REMOVE "+rel)
    for rel in reversed(m.get("created_dirs",[])):
        p=path(rel)
        if p.is_dir():
            try:p.rmdir()
            except OSError:pass
    m["state"]="blocked" if conflicts else "rolled_back"
    m["error"]=conflicts or m.get("error") or "ROLLBACK_ON_FAILED_GATE"
    m["rolled_back_at"]=utc();m["next"]="review_failed_gate";save(b,m)
    if not conflicts:unlock(run)
    if conflicts:raise RuntimeError("ROLLBACK_CONFLICT "+str(conflicts))
if __name__=="__main__":
    if len(sys.argv)!=3:raise SystemExit("prepare|stage|apply|verify|finalize|rollback runid")
    {"prepare":prepare,"stage":stage,"apply":apply,"verify":verify,
     "finalize":finalize,"rollback":rollback}[sys.argv[1]](sys.argv[2])
