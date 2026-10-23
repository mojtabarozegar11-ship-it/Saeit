#!/usr/bin/env python3
"""Scoped and reversible Zomorod release. Runs on cPanel only, never on GitHub."""
import hashlib
import html
import json
import os
import shutil
import sys
import urllib.request
from pathlib import Path

WEB = Path.home() / "public_html"
RELEASES = Path.home() / ".backups" / "zomorod-hourly-water-20261023"
MARK = "ZM-HOURLY-WATER-RELEASE-20261023-V2"
ROUTES = {
    "irrigation-planner/index.html": "agriculture/water-soil/irrigation-planner/index.html",
    "ventilation-estimator/index.html": "agriculture/greenhouse/ventilation-estimator/index.html",
    "water-path-game/index.html": "games/water-path/index.html",
}
PARENTS = [
    "agriculture/water-soil/index.html",
    "agriculture/greenhouse/index.html",
]
PROTECTED = [
    "index.html", ".htaccess", "agriculture/index.html", "agriculture/.htaccess",
    "mohammad/index.html", "ghanadi/index.html", "amozeshgah/index.html",
]
GAMES_INDEX = """<!doctype html><html lang="fa" dir="rtl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>بازی‌های زمرد ملل</title><meta name="description" content="بازی‌های آموزشی و فکری تحت وب زمرد ملل"><style>body{margin:0;background:#252b19;color:#f5eed9;font:16px/2 Tahoma,Arial}main{max-width:880px;padding:30px;margin:auto}a,h1{color:#ebcf87}.card{background:#344329;border:1px solid #9d8852;border-radius:15px;padding:22px}:focus-visible{outline:3px solid white}</style></head><body><main><h1>بازی‌های زمرد ملل</h1><article class="card"><h2>مسیر آب: نجات مزرعه</h2><p>پازل ده‌مرحله‌ای اتصال لوله‌های آب؛ قابل اجرا با لمس، کیبورد و دارای ذخیره پیشرفت.</p><a href="/games/water-path/">اجرای بازی مسیر آب</a></article><p><a href="/agriculture/">بازگشت به کشاورزی</a></p></main><!-- ZM-HOURLY-WATER-RELEASE-20261023-V2 --></body></html>"""
CARDS = {
    PARENTS[0]: """<section class="zm-hourly-addon" aria-labelledby="zm-water-tool" style="margin:22px auto;padding:18px;max-width:1050px;border:1px solid #d6bc71;border-radius:15px;background:#303b28"><h2 id="zm-water-tool" style="color:#f1d78f">ابزار رایگان محاسبه نیاز آب آبیاری</h2><p>برآورد نیاز خالص و ناخالص و دبی روزانه بر اساس مساحت، تبخیرتعرق، بارش مؤثر و راندمان؛ همراه راهنمای کاربردی و محدودیت‌ها.</p><a href="/agriculture/water-soil/irrigation-planner/">اجرای محاسبه‌گر آبیاری</a><p><a href="/games/water-path/">بازی آموزشی مسیر آب</a></p></section>""",
    PARENTS[1]: """<section class="zm-hourly-addon" aria-labelledby="zm-greenhouse-tool" style="margin:22px auto;padding:18px;max-width:1050px;border:1px solid #d6bc71;border-radius:15px;background:#303b28"><h2 id="zm-greenhouse-tool" style="color:#f1d78f">ابزار رایگان برآورد تهویه گلخانه</h2><p>محاسبه دبی نظری دفع گرمای محسوس و نرخ تعویض هوا با ورودی‌های دما، بار گرمایی و حجم گلخانه؛ همراه محدودیت‌های طراحی.</p><a href="/agriculture/greenhouse/ventilation-estimator/">اجرای برآوردگر تهویه گلخانه</a></section>""",
}
def sha(data):
    return hashlib.sha256(data).hexdigest()

def safe(rel):
    p = WEB / rel
    if WEB.is_symlink() or not WEB.is_dir():
        raise RuntimeError("Invalid document root")
    node = WEB
    for part in Path(rel).parts:
        node = node / part
        if node.is_symlink():
            raise RuntimeError("Symlink in target: " + rel)
    return p

def read_required(rel):
    p=safe(rel)
    if not p.is_file() or p.stat().st_size < (1 if rel.endswith(".htaccess") else 100):
        raise RuntimeError("Protected file missing/empty: "+rel)
    return p.read_bytes()

def atomic(dest, data):
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp=dest.with_name(dest.name+".zm-release-tmp")
    with tmp.open("xb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(tmp,dest)

def backup_dir(runid):
    if not runid.isdigit() or len(runid)>22:
        raise RuntimeError("Invalid run id")
    return RELEASES/runid

def manifest_path(base):
    return base/"manifest.json"

def load(base):
    return json.loads(manifest_path(base).read_text())

def store(base,m):
    temp=base/"manifest.new"
    temp.write_text(json.dumps(m,ensure_ascii=False,indent=2))
    os.replace(temp,manifest_path(base))

def prepare(runid):
    base=backup_dir(runid)
    if base.exists():
        raise RuntimeError("Run already prepared")
    original={}
    for rel in PROTECTED+PARENTS:
        original[rel]=sha(read_required(rel))
    if b"PassengerEnabled off" not in read_required("agriculture/.htaccess"):
        raise RuntimeError("Agriculture is not safely isolated from Passenger")
    for rel in ROUTES.values():
        if safe(rel).exists():
            raise RuntimeError("Target exists, overwrite refused: "+rel)
    if safe("games/index.html").exists() or safe("games/.htaccess").exists():
        raise RuntimeError("Games root not isolated; no safe new games hub")
    if safe("games").exists() and not safe("games").is_dir():
        raise RuntimeError("Games directory is occupied")
    if shutil.disk_usage(WEB).free < 15*1024*1024:
        raise RuntimeError("Insufficient safe free space")
    base.mkdir(parents=True,mode=0o700)
    (base/"before").mkdir()
    (base/"stage").mkdir()
    for rel in PARENTS:
        dst=base/"before"/rel
        dst.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(safe(rel),dst)
    manifest={"run_id":runid,"state":"prepared","immutable":original,"created":[],"modified":[],"hashes":{}}
    store(base,manifest)
    print("RELEASE_BACKUP_READY=PASS",flush=True)

def assert_unmodified(m, rel):
    if sha(read_required(rel))!=m["immutable"][rel]:
        raise RuntimeError("Concurrent modification of "+rel)

def apply(runid):
    base=backup_dir(runid);m=load(base)
    if m["state"]!="prepared":
        raise RuntimeError("Not in prepared state")
    stage=base/"stage"
    for src,rel in ROUTES.items():
        s=stage/src
        if not s.is_file():
            raise RuntimeError("Stage missing "+src)
        content=s.read_bytes()
        if len(content)<1400 or b"<html" not in content or b"</html>" not in content:
            raise RuntimeError("Invalid page "+src)
        if src.startswith("irrigation") and b"ZM-HOURLY-20261023-WATER-TOOL" not in content: raise RuntimeError("Bad irrigation source")
        if src.startswith("ventilation") and b"ZM-HOURLY-20261023-GREENHOUSE-TOOL" not in content: raise RuntimeError("Bad greenhouse source")
        if src.startswith("water-path") and b"ZM-WATER-PATH-20261023-V2" not in content: raise RuntimeError("Bad game source")
    for rel in PROTECTED+PARENTS:
        assert_unmodified(m,rel)
    if safe("games/index.html").exists() or safe("games/.htaccess").exists():
        raise RuntimeError("Games root was modified")
    m["state"]="installing";store(base,m)
    for src,rel in ROUTES.items():
        dest=safe(rel)
        if dest.exists():raise RuntimeError("Collision "+rel)
        content=(stage/src).read_bytes()
        atomic(dest,content);m["created"].append(rel);m["hashes"][rel]=sha(content);store(base,m)
    for rel,content in {"games/index.html":GAMES_INDEX,"games/.htaccess":"PassengerEnabled off\nDirectoryIndex index.html\n","games/water-path/.htaccess":"PassengerEnabled off\nDirectoryIndex index.html\n"}.items():
        dest=safe(rel)
        if dest.exists():raise RuntimeError("Collision "+rel)
        data=content.encode()
        atomic(dest,data);m["created"].append(rel);m["hashes"][rel]=sha(data);store(base,m)
    for rel in PARENTS:
        source=read_required(rel)
        marker=("<!-- "+MARK+" -->").encode()
        if marker in source:raise RuntimeError("Already inserted "+rel)
        if source.count(b"</main>")!=1:raise RuntimeError("Unsafe page layout "+rel)
        addon=(marker+CARDS[rel].encode())
        updated=source.replace(b"</main>",addon+b"</main>",1)
        if updated.replace(addon,b"",1)!=source:raise RuntimeError("Non-additive page modification")
        m["modified"].append(rel);store(base,m)
        atomic(safe(rel),updated);m["hashes"][rel]=sha(updated);store(base,m)
    m["state"]="installed";store(base,m)
    print("SCOPED_FILES_INSTALLED=PASS",flush=True)

def verify(runid):
    base=backup_dir(runid);m=load(base)
    if m["state"]!="installed":raise RuntimeError("Not installed")
    for rel,digest in m["hashes"].items():
        if not safe(rel).is_file() or sha(safe(rel).read_bytes())!=digest:
            raise RuntimeError("Installed file differs: "+rel)
    for rel in PROTECTED:
        assert_unmodified(m,rel)
    urls=[
        ("/agriculture/water-soil/irrigation-planner/","ZM-HOURLY-20261023-WATER-TOOL"),
        ("/agriculture/greenhouse/ventilation-estimator/","ZM-HOURLY-20261023-GREENHOUSE-TOOL"),
        ("/games/water-path/","ZM-WATER-PATH-20261023-V2"),
        ("/games/",MARK),
        ("/agriculture/water-soil/",MARK),
        ("/agriculture/greenhouse/",MARK),
    ]
    for route,needle in urls:
        req=urllib.request.Request("https://zomorodmelal.ir"+route+"?zm_release="+runid,headers={"Cache-Control":"no-cache,no-store","User-Agent":"ZomorodScopedRelease/1"})
        with urllib.request.urlopen(req,timeout=25) as response:
            body=response.read(500000)
            if response.status!=200 or needle.encode() not in body:
                raise RuntimeError("Public verification failed: "+route)
        print("PUBLIC_VERIFIED "+route+" HTTP=200",flush=True)
    for route in ["/","/agriculture/","/mohammad/","/ghanadi/","/amozeshgah/"]:
        req=urllib.request.Request("https://zomorodmelal.ir"+route+"?zm_smoke="+runid,headers={"Cache-Control":"no-cache"})
        with urllib.request.urlopen(req,timeout=25) as response:
            if response.status!=200:raise RuntimeError("Protected URL down "+route)
    m["state"]="verified";store(base,m)
    print("ZOMOROD_PUBLIC_RELEASE=PASS",flush=True)

def rollback(runid):
    base=backup_dir(runid)
    if not manifest_path(base).is_file():
        print("NO_RELEASE_TO_ROLLBACK",flush=True);return
    m=load(base)
    if m["state"]=="rolled_back":
        print("ALREADY_ROLLED_BACK",flush=True);return
    for rel in reversed(m.get("modified",[])):
        original=(base/"before"/rel).read_bytes()
        dest=safe(rel)
        current=dest.read_bytes() if dest.exists() else b""
        if current!=original and (sha(current)==m["hashes"].get(rel) or MARK.encode() in current):
            atomic(dest,original)
        elif current!=original:
            print("CONFLICT_REQUIRES_MANUAL_RECOVERY="+rel,flush=True)
    for rel in reversed(m.get("created",[])):
        dest=safe(rel)
        if dest.is_file() and sha(dest.read_bytes())==m["hashes"].get(rel):
            dest.unlink()
    for directory in ["games/water-path","games","agriculture/water-soil/irrigation-planner","agriculture/greenhouse/ventilation-estimator"]:
        try:safe(directory).rmdir()
        except OSError:pass
    m["state"]="rolled_back";store(base,m)
    print("SCOPED_ROLLBACK=COMPLETE",flush=True)

def main():
    if len(sys.argv)!=3 or sys.argv[1] not in ("prepare","apply","verify","rollback"):
        raise SystemExit("Usage: installer.py prepare|apply|verify|rollback RUN_ID")
    globals()[sys.argv[1]](sys.argv[2])
if __name__=="__main__":
    main()
