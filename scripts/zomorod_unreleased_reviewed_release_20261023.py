#!/usr/bin/env python3
"""Additive, auditable release of existing non-draft Zomorod pages.
Only four new HTML routes and three agriculture category pages are in scope.
"""
import hashlib
import html
import json
import os
import re
import sys
import time
import urllib.request
from pathlib import Path

HOME=Path.home()
WEB=HOME/"public_html"
BACKUPS=HOME/".backups"/"zomorod-unreleased-reviewed-20261023"
LOCK=HOME/".backups"/"zomorod-agriculture-static.publish.lock"
MARK="ZM-EXISTING-REVIEWED-SOURCES-20261023-V1"
TARGETS=[
 "agriculture/water-soil/field-notes-09-10/index.html",
 "agriculture/water-soil/field-notes-11-14/index.html",
 "agriculture/greenhouse/temperature-uniformity/index.html",
 "agriculture/digital-lab/index.html",
]
LINK_PAGES={
 "agriculture/water-soil/index.html":[
 ("/agriculture/water-soil/field-notes-09-10/","راهنمای فنی ۹ و ۱۰: ذخیره آب ریشه و آستانه آبیاری"),
 ("/agriculture/water-soil/field-notes-11-14/","راهنمای فنی ۱۱ تا ۱۴: محاسبه و کنترل خطای آبیاری")],
 "agriculture/greenhouse/index.html":[
 ("/agriculture/greenhouse/temperature-uniformity/","آزمون میدانی یکنواختی دمای گلخانه")],
 "agriculture/index.html":[
 ("/agriculture/digital-lab/","آزمایشگاه ۲۱ ابزار دیجیتال و برنامه‌ریزی فنی")]
}
PROTECTED=[
 "index.html",".htaccess","agriculture/.htaccess","games/index.html",
 "games/water-path/index.html","games/air-supremacy/index.html",
 "research/index.html","agriculture/water-soil/irrigation-planner/index.html",
 "agriculture/greenhouse/ventilation-estimator/index.html",
]
ROOT=Path(__file__).resolve().parents[1]
EXTRA_NOTES="""# راهنمای فنی ۹ و ۱۰ — ذخیره آب ریشه و آستانه آبیاری

این متن ترجمه آموزشی یادداشت‌های فنی قبلی است. مثال‌ها فرضی‌اند و توصیه اختصاصی برای مزرعه نیستند. روش: FAO Irrigation and Drainage Paper 56 (Allen et al., 1998): https://www.fao.org/4/X0490E/X0490E00.htm .

## ۹. محاسبه آب قابل استفاده گیاه در ناحیه ریشه
**مسئله:** یک عدد رطوبت حجمی به‌تنهایی نشان نمی‌دهد چه مقدار آب قابل استفاده گیاه در خاک ذخیره شده است.

**روش:** ظرفیت زراعی (FC) و نقطه پژمردگی دائم (PWP) را برای لایه‌های مؤثر خاک تعیین کنید. در یک لایه یکنواخت، کل آب قابل‌استفاده (میلی‌متر) = اختلاف کسر حجمی FC و PWP × عمق ریشه (متر) × ۱۰۰۰. لایه‌های متفاوت را جداگانه محاسبه و جمع کنید.

**مثال:** FC برابر ۰٫۳۰، PWP برابر ۰٫۱۶ و عمق ریشه ۰٫۴۰ متر است. ذخیره قابل‌استفاده = (۰٫۳۰ − ۰٫۱۶) × ۰٫۴۰ × ۱۰۰۰ = ۵۶ میلی‌متر. این ظرفیت ذخیره است، نه نیاز آب امروز.

**آزمون:** اختلاف رطوبت اندازه‌گیری‌شده را در عمق‌های مختلف با محاسبه مقایسه و خطای حسگر را ثبت کنید.

**محدودیت:** تغییر عمق ریشه، شوری، لایه سخت، ناهمگنی خاک و رطوبت غیریکنواخت بر آب قابل‌استخراج اثر می‌گذارند. مقادیر FC و PWP باید برای خاک واقعی معتبر باشند.

## ۱۰. تعیین آستانه شروع آبیاری
**مسئله:** تخلیه کامل آب قابل‌استفاده می‌تواند تنش غیرضروری برای محصول ایجاد کند.

**روش:** سهم مجاز تخلیه را متناسب با محصول، رشد و شرایط تبخیری بر اساس شواهد محلی انتخاب کنید. حاصل‌ضرب این سهم در آب قابل‌استفاده ناحیه ریشه، آستانه نظری تخلیه است. داده تبخیرتعرق محصول، بارش مؤثر و رطوبت آغازین را پایش کنید.

**مثال:** ذخیره قابل‌استفاده ۵۶ میلی‌متر و سهم مجاز فرضی ۰٫۵۰، آستانه ۲۸ میلی‌متر می‌دهد. در صورت مصرف خالص ثابت ۴ میلی‌متر در روز، از ظرفیت زراعی تا آستانه حدود ۷ روز طول می‌کشد؛ فقط اگر ورودی و خروجی دیگری وجود نداشته باشد.

**آزمون:** زمان رسیدن به آستانه را با داده رطوبت واقعی، بارندگی و آبیاری مقایسه و انحراف را مستند کنید.

**محدودیت:** عدد ۰٫۵۰ مثال است نه حد عمومی. بارش، زهکشی، شوری، یکنواختی شبکه و تغییر عمق ریشه نتیجه را تغییر می‌دهند.
"""

def digest(data):
    return hashlib.sha256(data).hexdigest()

def checkrun(run):
    if re.fullmatch(r"[0-9]{7,15}",run) is None:
        raise RuntimeError("invalid release run identifier")
    return BACKUPS/run

def securepath(rel):
    p=WEB
    for item in Path(rel).parts:
        if item in (".","..","") or item.startswith("/"):
            raise RuntimeError("unsafe path")
        p=p/item
        if p.is_symlink():
            raise RuntimeError("release symlink prohibited: "+rel)
    return p

def sourcefile(rel):
    p=securepath(rel)
    if not p.is_file():
        raise RuntimeError("missing existing site file: "+rel)
    return p.read_bytes()

def atomic(p,data):
    p.parent.mkdir(parents=True,exist_ok=True)
    t=p.with_name(p.name+".zm-"+str(os.getpid())+".tmp")
    with t.open("xb") as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())
    os.replace(t,p)

def save(base,manifest):
    temp=base/"manifest.json.tmp"
    temp.write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding="utf-8")
    os.replace(temp,base/"manifest.json")

def load(base):
    return json.loads((base/"manifest.json").read_text(encoding="utf-8"))

def paragraph(text):
    val=html.escape(text)
    val=re.sub(r"\*\*(.+?)\*\*",lambda m:"<strong>"+m.group(1)+"</strong>",val)
    val=re.sub(r"https://[^\s<]+",lambda m:'<a href="'+m.group(0).rstrip(".,;")+'" rel="noopener">'+m.group(0).rstrip(".,;")+"</a>"+m.group(0)[len(m.group(0).rstrip(".,;")):],val)
    return val

def mdpage(md,title,route,back):
    if "DRAFT_DO_NOT_PUBLISH" in md or "pending detailed review" in md.lower():
        raise RuntimeError("editorial hold: "+route)
    blocks=[]
    buf=[]
    def flush():
        if buf:
            blocks.append("<p>"+paragraph(" ".join(buf))+"</p>")
            buf.clear()
    for line in md.splitlines():
        line=line.strip()
        if not line:
            flush()
        elif line.startswith("## "):
            flush()
            blocks.append("<h2>"+html.escape(line[3:])+"</h2>")
        elif line.startswith("# "):
            flush()
        else:buf.append(line)
    flush()
    css="""*{box-sizing:border-box}body{background:#f5f7ef;color:#173d2d;font:17px/2 Tahoma,Arial,sans-serif;margin:0}
header{background:linear-gradient(120deg,#163e31,#276c4d);color:#fff;padding:30px 20px}
main{max-width:920px;margin:auto;padding:20px}h1{font-size:clamp(24px,4vw,38px);line-height:1.6;margin:0}
h2{color:#155e42;font-size:clamp(20px,3vw,26px);margin:28px 0 10px}
p{background:white;border:1px solid #dce7d9;border-radius:11px;padding:13px 17px;margin:12px 0}
a{color:#165d48}a:focus-visible{outline:3px solid #d6a957;outline-offset:3px}
.nav{padding:8px 0;color:#f3e1a0}.nav a{color:#fbe5ad}
footer{border-top:1px solid #d2e0d5;text-align:center;padding:18px}
@media(max-width:600px){body{font-size:16px}main{padding:14px}header{padding:20px 14px}}"""
    return ('<!doctype html><html lang="fa" dir="rtl"><head><meta charset="utf-8">'
      '<meta name="viewport" content="width=device-width,initial-scale=1">'
      '<meta name="description" content="'+html.escape(title,quote=True)+'؛ راهنمای آموزشی همراه با روش محاسبه، آزمون و محدودیت‌ها.">'
      '<title>'+html.escape(title)+' | زمرد ملل</title>'
      '<link rel="canonical" href="https://zomorodmelal.ir/'+route+'">'
      '<style>'+css+'</style></head><body>'
      '<!-- '+MARK+' -->'
      '<header><div style="max-width:920px;margin:auto"><div class="nav"><a href="'+back+'">بازگشت به بخش تخصصی</a></div>'
      '<h1>'+html.escape(title)+'</h1></div></header>'
      '<main><p>نسخه آموزشی و پژوهشی؛ برای تصمیم عملی، داده مزرعه و نظر متخصص لازم است.</p>'
      +"\n".join(blocks)+'</main><footer>شرکت کشت‌وصنعت زمرد ملل · <a href="/agriculture/">کشاورزی</a></footer></body></html>').encode("utf-8")

def render(stage):
    if stage.exists():
        raise RuntimeError("stage directory already exists")
    stage.mkdir(parents=True)
    s=ROOT/"content"/"zomorod-hourly-20261023"
    src11=(s/"irrigation-field-notes-11-14.md").read_text("utf-8")
    srcgreen=(s/"greenhouse-temperature-uniformity-guide.md").read_text("utf-8")
    origenglish=(s/"irrigation-field-notes-09-10.md").read_text("utf-8")
    if not all(x in origenglish for x in ["56 mm","28 mm","FAO"]):
        raise RuntimeError("09/10 research source changed; translation unreviewed")
    expected={
       TARGETS[0]:mdpage(EXTRA_NOTES,"ذخیره آب ریشه و آستانه آبیاری: یادداشت‌های ۹ و ۱۰","agriculture/water-soil/field-notes-09-10/","/agriculture/water-soil/"),
       TARGETS[1]:mdpage(src11,"مدیریت آبیاری و کنترل خطا: یادداشت‌های ۱۱ تا ۱۴","agriculture/water-soil/field-notes-11-14/","/agriculture/water-soil/"),
       TARGETS[2]:mdpage(srcgreen,"آزمون یکنواختی دما و تهویه گلخانه","agriculture/greenhouse/temperature-uniformity/","/agriculture/greenhouse/"),
    }
    lab=(ROOT/"content"/"zomorod-it-products-20261019"/"index.html").read_text("utf-8")
    match=re.search(r'<script id="catalog" type="application/json">([\s\S]*?)</script>',lab)
    if not match:raise RuntimeError("digital lab catalog absent")
    catalog=json.loads(match.group(1))
    slugs=[x.get("slug") for x in catalog]
    if len(catalog)!=21 or len(set(slugs))!=21 or any(not re.fullmatch("[a-z0-9-]+",x) for x in slugs):
        raise RuntimeError("21 independent catalog modes not present")
    nav='<nav aria-label="فهرست ابزارهای دیجیتال" style="display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:8px;padding:18px;background:#133328;border:1px solid #c5dfbc55;border-radius:18px;margin:20px 0">'
    for item in catalog:
        nav+=('<a style="border:1px solid #cab572;border-radius:10px;padding:7px 12px" href="/agriculture/digital-lab/?tool='+item["slug"]+'">'+html.escape(item["title"])+'</a>')
    nav+="</nav>"
    if lab.count("</main>")!=1 or lab.count("</head>")!=1:
        raise RuntimeError("source digital lab markup changed")
    lab=lab.replace("</head>",'<link rel="canonical" href="https://zomorodmelal.ir/agriculture/digital-lab/"></head>',1)
    lab=lab.replace("</main>",nav+'</main>',1)
    lab=lab.replace("<body>",'<body><!-- '+MARK+' -->',1)
    expected[TARGETS[3]]=lab.encode("utf-8")
    for rel,data in expected.items():
        if MARK.encode() not in data or len(data)<1200:
            raise RuntimeError("rendered page invalid "+rel)
        p=stage/rel;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(data)
    manifest={rel:{"sha256":digest(data),"bytes":len(data)} for rel,data in expected.items()}
    (stage/"source-manifest.json").write_text(json.dumps(manifest,indent=2,ensure_ascii=False),encoding="utf-8")
    print("RENDER_SOURCE_READY=PASS targets=4 modes=21")
    for rel,data in expected.items():print("STAGED_SOURCE",rel,len(data),digest(data)[:16])

def locked(run):
    if not LOCK.is_file() or LOCK.is_symlink() or LOCK.read_text().strip()!=run:
        raise RuntimeError("exclusive release lock missing or owned by other run")

def prepare(run):
    b=checkrun(run)
    if not WEB.is_dir() or WEB.is_symlink():raise RuntimeError("docroot invalid")
    if b.exists():raise RuntimeError("release identifier already exists")
    immutable={rel:digest(sourcefile(rel)) for rel in PROTECTED}
    pages={rel:digest(sourcefile(rel)) for rel in LINK_PAGES}
    for rel in TARGETS:
        if securepath(rel).exists():raise RuntimeError("target already present; no overwrite: "+rel)
    LOCK.parent.mkdir(parents=True,exist_ok=True)
    try:
        with LOCK.open("x") as f:f.write(run+"\n")
    except FileExistsError:raise RuntimeError("another publisher holds exclusive cPanel lock")
    try:
        b.mkdir(parents=True,mode=0o700)
        (b/"stage").mkdir()
        for rel in LINK_PAGES:
            dest=b/"before"/rel;dest.parent.mkdir(parents=True,exist_ok=True)
            dest.write_bytes(sourcefile(rel))
        manifest={"state":"prepared","run":run,"immutable":immutable,"baseline":pages,
                  "installed":{},"source_sha":{},"created":[],"modified":[]}
        save(b,manifest)
    except BaseException:
        if LOCK.is_file() and LOCK.read_text().strip()==run:LOCK.unlink()
        raise
    print("PRODUCTION_BACKUP_PREPARED=PASS run="+run+" protected="+str(len(immutable))+" editable="+str(len(pages)))

def link_render(old,links):
    if old.count(b"</main>")!=1 or old.count(b"<main")!=1 or MARK.encode() in old:
        raise RuntimeError("ambiguous live category page; abort")
    content='<section aria-label="منابع کاربردی تکمیلی" style="border:1px solid #ba9c59;border-radius:14px;padding:14px;margin:20px 0;background:#123e2c;color:#fff">'
    content+='<strong style="color:#f2d38e">منابع و ابزارهای کاربردی تکمیلی</strong><ul>'
    for url,title in links:
        content+='<li><a style="color:#fae7b6" href="'+url+'">'+html.escape(title)+'</a></li>'
    content+='</ul></section><!-- '+MARK+' -->'
    return old.replace(b"</main>",content.encode("utf-8")+b"</main>",1)

def apply(run):
    b=checkrun(run);locked(run);m=load(b)
    if m["state"]!="prepared":raise RuntimeError("release is not prepared")
    for rel,oldhash in {**m["immutable"],**m["baseline"]}.items():
        if digest(sourcefile(rel))!=oldhash:raise RuntimeError("changed since backup: "+rel)
    expected=json.loads((b/"stage"/"source-manifest.json").read_text("utf-8"))
    if sorted(expected)!=sorted(TARGETS):raise RuntimeError("stage source list mismatch")
    for rel in TARGETS:
        staged=b/"stage"/rel
        if staged.is_symlink() or not staged.is_file():raise RuntimeError("missing staged candidate "+rel)
        data=staged.read_bytes()
        if digest(data)!=expected[rel]["sha256"] or len(data)!=expected[rel]["bytes"]:
            raise RuntimeError("staged source hash mismatch "+rel)
        if MARK.encode() not in data:raise RuntimeError("source release marker missing "+rel)
        if securepath(rel).exists():raise RuntimeError("destination collision "+rel)
    m["source_sha"]={rel:expected[rel]["sha256"] for rel in TARGETS}
    m["state"]="installing";save(b,m)
    for rel in TARGETS:
        p=securepath(rel);p.parent.mkdir(parents=True,exist_ok=True)
        temp=p.with_name(p.name+".unreleased-"+run+".tmp")
        with temp.open("xb") as f:
            f.write((b/"stage"/rel).read_bytes());f.flush();os.fsync(f.fileno())
        os.link(temp,p)
        temp.unlink()
        m["installed"][rel]=expected[rel]["sha256"]
        m["created"].append(rel);save(b,m)
    for rel,links in LINK_PAGES.items():
        original=sourcefile(rel)
        if digest(original)!=m["baseline"][rel]:raise RuntimeError("category concurrent modification "+rel)
        new=link_render(original,links)
        m["installed"][rel]=digest(new)
        m["modified"].append(rel);save(b,m)
        atomic(securepath(rel),new)
    m["state"]="installed";save(b,m)
    print("EXISTING_CONTENT_ATOMIC_ADDITIVE_INSTALL=PASS routes=4 category_links=3")

def verify(run):
    b=checkrun(run);locked(run);m=load(b)
    if m["state"]!="installed":raise RuntimeError("not installed")
    for rel,hs in m["installed"].items():
        if digest(sourcefile(rel))!=hs:raise RuntimeError("installed hash mismatch "+rel)
    for rel,hs in m["immutable"].items():
        if digest(sourcefile(rel))!=hs:raise RuntimeError("protected file changed "+rel)
    for rel in TARGETS:
        url="https://zomorodmelal.ir/"+rel[:-10] + "?release="+run
        for attempt in range(3):
            try:
                req=urllib.request.Request(url,headers={"Cache-Control":"no-cache","User-Agent":"ZomorodIndependentReleaseQA/1"})
                with urllib.request.urlopen(req,timeout=22) as resp:
                    data=resp.read(200000)
                    if resp.status==200 and digest(data)==m["source_sha"][rel]:break
            except Exception:
                pass
            time.sleep(2)
        else:raise RuntimeError("public HTML hash not verified: "+rel)
        print("LIVE_ROUTE_SHA256_PASS",url)
    for rel in LINK_PAGES:
        req=urllib.request.Request("https://zomorodmelal.ir/"+rel.replace("index.html","")+"?release="+run,
                                   headers={"Cache-Control":"no-cache"})
        with urllib.request.urlopen(req,timeout=25) as resp:
            if resp.status!=200 or MARK.encode() not in resp.read(150000):
                raise RuntimeError("new navigation link not public "+rel)
        print("LIVE_CATEGORY_LINK_PASS",rel)
    print("PUBLIC_EXISTING_CONTENT_ALL_ROUTES=PASS")

def finalize(run):
    b=checkrun(run);locked(run);m=load(b)
    if m["state"]!="installed":raise RuntimeError("can only finalize installed")
    for rel,hs in m["installed"].items():
        if digest(sourcefile(rel))!=hs:raise RuntimeError("live changed before finalize")
    m["state"]="live_verified";m["finished_epoch"]=int(time.time());save(b,m)
    LOCK.unlink()
    print("ZOMOROD_EXISTING_SOURCE_RELEASE_VERIFIED=PASS",run)

def rollback(run):
    b=checkrun(run)
    f=b/"manifest.json"
    if not f.is_file():return
    m=load(b)
    if m["state"]=="live_verified":
        raise RuntimeError("manual recovery required for finalized release")
    for rel in reversed(m.get("modified",[])):
        p=securepath(rel)
        backup=b/"before"/rel
        if p.is_file() and digest(p.read_bytes())==m["installed"].get(rel) and backup.is_file():
            atomic(p,backup.read_bytes())
            print("ROLLBACK_RESTORED",rel)
    for rel in TARGETS:
        p=securepath(rel)
        if p.is_file() and digest(p.read_bytes())==m.get("source_sha",{}).get(rel):
            p.unlink();print("ROLLBACK_REMOVED_NEW",rel)
    m["state"]="rolled_back";save(b,m)
    if LOCK.is_file() and LOCK.read_text().strip()==run:LOCK.unlink()
    print("SCOPED_ROLLBACK_COMPLETE=PASS")

if __name__=="__main__":
    if len(sys.argv)!=3 or sys.argv[1] not in ("render","prepare","apply","verify","finalize","rollback"):
        raise SystemExit("Usage: script.py render STAGE_DIR | prepare/apply/verify/finalize/rollback RUN_ID")
    mode,arg=sys.argv[1:]
    render(Path(arg)) if mode=="render" else globals()[mode](arg)
