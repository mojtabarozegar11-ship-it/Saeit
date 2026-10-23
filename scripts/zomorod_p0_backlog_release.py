#!/usr/bin/env python3
"""Scoped and reversible P0 release: four previously prepared tools only."""
import hashlib
import html
import json
import os
import shutil
import sys
import urllib.request
from pathlib import Path

WEB = Path.home() / "public_html"
RELEASES = Path.home() / ".backups" / "zomorod-p0-backlog"
MARK = "ZM-P0-FOUR-TOOLS-20261023-V1"
ROUTES = {
    "irrigation-need/index.html": "agriculture/water-soil/irrigation-need.html",
    "irrigation-need/irrigation-need.svg": "agriculture/water-soil/irrigation-need.svg",
    "seeding-rate/index.html": "agriculture/seeds/seeding-rate.html",
    "seeding-rate/seeding-rate.svg": "agriculture/seeds/seeding-rate.svg",
    "planting-planner/index.html": "agriculture/greenhouse/planting-planner/index.html",
    "planting-planner/illustration.svg": "agriculture/greenhouse/planting-planner/illustration.svg",
    "planting-planner/app.js": "agriculture/greenhouse/planting-planner/app.js",
    "feed-dry-matter/index.html": "agriculture/livestock/feed-dry-matter/index.html",
    "feed-dry-matter/illustration.svg": "agriculture/livestock/feed-dry-matter/illustration.svg",
    "feed-dry-matter/app.js": "agriculture/livestock/feed-dry-matter/app.js",
}
PARENTS = [
    "agriculture/water-soil/index.html",
    "agriculture/seeds/index.html",
    "agriculture/greenhouse/index.html",
    "agriculture/livestock/index.html",
]
PROTECTED = [
    "index.html", ".htaccess", "agriculture/index.html", "agriculture/.htaccess",
    "mohammad/index.html", "ghanadi/index.html", "amozeshgah/index.html",
]
CARDS = {
    "agriculture/water-soil/index.html": "<section class=\"zm-p0-tool-card\" aria-label=\"ابزار رایگان نیاز آب آبیاری\" style=\"margin:22px auto;padding:18px;max-width:1050px;border:1px solid #d6bc71;border-radius:15px;background:#303b28;color:#f5efdc\"><h2 style=\"color:#f1d78f\">نیاز آب آبیاری</h2><img src=\"/agriculture/water-soil/irrigation-need.svg\" width=\"680\" height=\"360\" alt=\"تصویر راهنمای اختصاصی نیاز آب آبیاری\" loading=\"lazy\" style=\"width:100%;max-width:420px;height:auto;display:block\"><p>برآورد نیاز خالص و ناخالص آب آبیاری از تبخیرتعرق، ضریب گیاهی و راندمان سامانه؛ همراه ۵۰ راهنمای کوتاه و منابع مطالعاتی.</p><a href=\"/agriculture/water-soil/irrigation-need.html\" style=\"color:#f1d78f;font-weight:bold\">اجرای ابزار و مطالعه راهنماها ←</a></section>",
    "agriculture/seeds/index.html": "<section class=\"zm-p0-tool-card\" aria-label=\"ابزار رایگان مقدار بذر مورد نیاز\" style=\"margin:22px auto;padding:18px;max-width:1050px;border:1px solid #d6bc71;border-radius:15px;background:#303b28;color:#f5efdc\"><h2 style=\"color:#f1d78f\">مقدار بذر مورد نیاز</h2><img src=\"/agriculture/seeds/seeding-rate.svg\" width=\"680\" height=\"360\" alt=\"تصویر راهنمای اختصاصی مقدار بذر مورد نیاز\" loading=\"lazy\" style=\"width:100%;max-width:420px;height:auto;display:block\"><p>محاسبه مقدار بذر و خرید بر اساس تراکم، وزن هزار دانه، خلوص و جوانه‌زنی؛ همراه ۵۰ راهنمای کوتاه و منابع مطالعاتی.</p><a href=\"/agriculture/seeds/seeding-rate.html\" style=\"color:#f1d78f;font-weight:bold\">اجرای ابزار و مطالعه راهنماها ←</a></section>",
    "agriculture/greenhouse/index.html": "<section class=\"zm-p0-tool-card\" aria-label=\"ابزار رایگان برنامه‌ریز کشت گلخانه\" style=\"margin:22px auto;padding:18px;max-width:1050px;border:1px solid #d6bc71;border-radius:15px;background:#303b28;color:#f5efdc\"><h2 style=\"color:#f1d78f\">برنامه‌ریز کشت گلخانه</h2><img src=\"/agriculture/greenhouse/planting-planner/illustration.svg\" width=\"680\" height=\"360\" alt=\"تصویر راهنمای اختصاصی برنامه‌ریز کشت گلخانه\" loading=\"lazy\" style=\"width:100%;max-width:420px;height:auto;display:block\"><p>برآورد ظرفیت کشت، تعداد نشا و سینی در گلخانه با ورودی‌های واقعی؛ همراه ۵۰ راهنمای کوتاه و منابع مطالعاتی.</p><a href=\"/agriculture/greenhouse/planting-planner/\" style=\"color:#f1d78f;font-weight:bold\">اجرای ابزار و مطالعه راهنماها ←</a></section>",
    "agriculture/livestock/index.html": "<section class=\"zm-p0-tool-card\" aria-label=\"ابزار رایگان مقایسه هزینه خوراک دام\" style=\"margin:22px auto;padding:18px;max-width:1050px;border:1px solid #d6bc71;border-radius:15px;background:#303b28;color:#f5efdc\"><h2 style=\"color:#f1d78f\">مقایسه هزینه خوراک دام</h2><img src=\"/agriculture/livestock/feed-dry-matter/illustration.svg\" width=\"680\" height=\"360\" alt=\"تصویر راهنمای اختصاصی مقایسه هزینه خوراک دام\" loading=\"lazy\" style=\"width:100%;max-width:420px;height:auto;display:block\"><p>مقایسه هزینه ماده خشک دو خوراک و بودجه گله برای تصمیم اولیه خرید؛ همراه ۵۰ راهنمای کوتاه و منابع مطالعاتی.</p><a href=\"/agriculture/livestock/feed-dry-matter/\" style=\"color:#f1d78f;font-weight:bold\">اجرای ابزار و مطالعه راهنماها ←</a></section>"
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
        raise RuntimeError("Not prepared")
    stage=base/"stage"
    for src,rel in ROUTES.items():
        s=stage/src
        if not s.is_file() or s.is_symlink():
            raise RuntimeError("Missing or unsafe staged file "+src)
        content=s.read_bytes()
        if src.endswith("index.html"):
            if len(content)<1400 or b"<html" not in content or b"</html>" not in content:
                raise RuntimeError("Invalid page "+src)
            if content.count(b'<details class="guide">')!=50:
                raise RuntimeError("Guides count mismatch "+src)
            if b'dir="rtl"' not in content or b'<form' not in content:
                raise RuntimeError("Noninteractive or non-RTL tool "+src)
        elif src.endswith(".svg"):
            if len(content)>200000 or b"<svg" not in content:
                raise RuntimeError("Unsafe SVG "+src)
        elif src.endswith(".js"):
            if len(content)<200 or b"calculate" not in content:
                raise RuntimeError("Broken calculator JS "+src)
    for rel in PROTECTED+PARENTS:
        assert_unmodified(m,rel)
    m["state"]="installing";store(base,m)
    for src,rel in ROUTES.items():
        dest=safe(rel)
        if dest.exists():
            raise RuntimeError("Collision "+rel)
        content=(stage/src).read_bytes()
        atomic(dest,content)
        m["created"].append(rel);m["hashes"][rel]=sha(content);store(base,m)
    for rel in PARENTS:
        source=read_required(rel)
        marker=("<!-- "+MARK+" -->").encode()
        if marker in source: raise RuntimeError("Already inserted "+rel)
        if source.count(b"</main>")!=1: raise RuntimeError("Unsafe page layout "+rel)
        addon=marker+CARDS[rel].encode()
        updated=source.replace(b"</main>",addon+b"</main>",1)
        if updated.replace(addon,b"",1)!=source: raise RuntimeError("Non-additive content change")
        m["modified"].append(rel);store(base,m)
        atomic(safe(rel),updated);m["hashes"][rel]=sha(updated);store(base,m)
    m["state"]="installed";store(base,m)
    print("P0_FOUR_SCOPED_TOOLS_INSTALLED=PASS",flush=True)

def verify(runid):
    base=backup_dir(runid);m=load(base)
    if m["state"]!="installed":raise RuntimeError("Not installed")
    for rel,digest in m["hashes"].items():
        if not safe(rel).is_file() or sha(safe(rel).read_bytes())!=digest:
            raise RuntimeError("Hash mismatch "+rel)
    for rel in PROTECTED: assert_unmodified(m,rel)
    urls=[
        ("/agriculture/water-soil/irrigation-need.html","irrigation-need.html"),
        ("/agriculture/seeds/seeding-rate.html","seeding-rate.html"),
        ("/agriculture/greenhouse/planting-planner/","zm-hourly-greenhouse-20261022-02"),
        ("/agriculture/livestock/feed-dry-matter/","zm-hourly-livestock-20261022-02"),
    ]
    for route,needle in urls:
        request=urllib.request.Request("https://zomorodmelal.ir"+route+"?zm_p0="+runid,headers={"Cache-Control":"no-cache,no-store","User-Agent":"ZomorodP0Release/1"})
        with urllib.request.urlopen(request,timeout=25) as response:
            body=response.read(150000)
            if response.status!=200 or needle.encode() not in body:
                raise RuntimeError("Public tool verification failed "+route)
        print("PUBLIC_TOOL_VERIFIED "+route+" HTTP=200",flush=True)
    for rel in list(ROUTES.values()):
        if rel.endswith(".svg") or rel.endswith(".js"):
            request=urllib.request.Request("https://zomorodmelal.ir/"+rel+"?zm_p0="+runid,headers={"Cache-Control":"no-cache"})
            with urllib.request.urlopen(request,timeout=25) as response:
                if response.status!=200: raise RuntimeError("Public asset down "+rel)
            print("PUBLIC_ASSET_VERIFIED "+rel+" HTTP=200",flush=True)
    for rel in PARENTS:
        url="https://zomorodmelal.ir/"+rel.removesuffix("index.html")
        request=urllib.request.Request(url+"?zm_p0="+runid,headers={"Cache-Control":"no-cache"})
        with urllib.request.urlopen(request,timeout=25) as response:
            body=response.read(250000)
            if response.status!=200 or MARK.encode() not in body:
                raise RuntimeError("Card not visible "+rel)
        print("PUBLIC_CARD_VERIFIED "+url+" HTTP=200",flush=True)
    for route in ["/","/agriculture/","/mohammad/","/ghanadi/","/amozeshgah/"]:
        with urllib.request.urlopen("https://zomorodmelal.ir"+route+"?zm_smoke="+runid,timeout=25) as response:
            if response.status!=200:raise RuntimeError("Previously working route down "+route)
    m["state"]="verified";store(base,m)
    print("ZOMOROD_P0_PUBLIC_RELEASE=PASS",flush=True)

def rollback(runid):
    base=backup_dir(runid)
    if not manifest_path(base).is_file():
        print("NO_RELEASE_TO_ROLLBACK",flush=True);return
    m=load(base)
    if m["state"]=="rolled_back":
        print("ALREADY_ROLLED_BACK",flush=True);return
    conflict=False
    for rel in reversed(m.get("modified",[])):
        backup=(base/"before"/rel).read_bytes()
        dest=safe(rel);current=dest.read_bytes() if dest.exists() else b""
        if current!=backup and (sha(current)==m["hashes"].get(rel) or MARK.encode() in current):
            atomic(dest,backup)
        elif current!=backup:
            conflict=True;print("CONFLICT_NEEDS_MANUAL_RECOVERY="+rel,flush=True)
    for rel in reversed(m.get("created",[])):
        dest=safe(rel)
        if dest.is_file() and sha(dest.read_bytes())==m["hashes"].get(rel):
            dest.unlink()
        elif dest.exists():
            conflict=True;print("CONFLICT_NEEDS_MANUAL_RECOVERY="+rel,flush=True)
    for directory in ["agriculture/greenhouse/planting-planner","agriculture/livestock/feed-dry-matter"]:
        try:safe(directory).rmdir()
        except OSError:pass
    m["state"]="rollback_conflict" if conflict else "rolled_back";store(base,m)
    print("P0_ROLLBACK="+("CONFLICT" if conflict else "COMPLETE"),flush=True)

def main():
    if len(sys.argv)!=3 or sys.argv[1] not in ("prepare","apply","verify","rollback"):
        raise SystemExit("Usage: installer.py prepare|apply|verify|rollback RUN_ID")
    globals()[sys.argv[1]](sys.argv[2])
if __name__=="__main__":
    main()
