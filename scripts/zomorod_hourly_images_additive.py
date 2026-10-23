#!/usr/bin/env python3
"""Generate and deploy three scoped, original WebP cards on cPanel, with rollback."""
import hashlib,io,json,os,shutil,sys,urllib.request
from pathlib import Path

WEB=Path.home()/"public_html"
RELEASES=Path.home()/".backups"/"zomorod-water-images-20261023"
DIR="agriculture/assets/zomorod-water-20261023"
NAMES=["zomorod-irrigation.webp","zomorod-greenhouse.webp","zomorod-water-path.webp"]
PAGES=["agriculture/water-soil/index.html","agriculture/greenhouse/index.html","games/index.html"]
PROTECTED=["index.html",".htaccess","agriculture/index.html","agriculture/.htaccess","mohammad/index.html","ghanadi/index.html","amozeshgah/index.html"]
OLDMARK=b"ZM-HOURLY-WATER-RELEASE-20261023-V2"
NEW=b"ZM-HOURLY-WEBP-CARDS-20261023-V1"

def h(b):return hashlib.sha256(b).hexdigest()
def path(rel):
    p=WEB
    for segment in Path(rel).parts:
        p=p/segment
        if p.is_symlink():raise RuntimeError("Symlink blocked: "+rel)
    return p
def read(rel):
    p=path(rel)
    if not p.is_file():raise RuntimeError("File missing "+rel)
    return p.read_bytes()
def root(runid):
    if not runid.isdigit():raise RuntimeError("Invalid run ID")
    return RELEASES/runid
def put(p,data):
    p.parent.mkdir(parents=True,exist_ok=True)
    t=p.with_name(p.name+".zm-image.tmp")
    with t.open("xb") as f:
        f.write(data);f.flush();os.fsync(f.fileno())
    os.replace(t,p)
def save(base,m):
    (base/"manifest.tmp").write_text(json.dumps(m,indent=2,ensure_ascii=False))
    os.replace(base/"manifest.tmp",base/"manifest.json")
def load(base):return json.loads((base/"manifest.json").read_text())

def generate():
    from PIL import Image,ImageDraw
    assets=[]
    themes=[("irrigation",(25,64,45)),("greenhouse",(40,74,56)),("water-path",(22,72,88))]
    for i,(name,bg) in enumerate(themes):
        im=Image.new("RGB",(384,240),bg);d=ImageDraw.Draw(im)
        d.rounded_rectangle((12,12,372,228),radius=28,outline=(216,184,104),width=5)
        if i==0:
            for n in range(4):
                x=38+n*85;d.line((x,180,x+60,180),fill=(129,164,90),width=7)
                for t in range(3):
                    xx=x+15+t*19;d.ellipse((xx,142,xx+9,151),fill=(98,190,116))
            d.line((40,65,330,65),fill=(103,198,234),width=19)
            for x in (75,150,225,300):
                d.line((x,65,x,115),fill=(84,178,222),width=10)
                d.ellipse((x-8,109,x+8,130),fill=(125,213,238))
        elif i==1:
            d.polygon([(48,120),(192,42),(336,120)],outline=(235,208,135))
            d.rectangle((55,120,329,210),outline=(235,208,135),width=6)
            for x in (100,190,280):
                d.line((x,110,x,204),fill=(104,180,151),width=8)
            for x in (100,280):
                d.ellipse((x-30,125,x+30,185),outline=(130,216,220),width=5)
                d.line((x-20,155,x+20,155),fill=(162,227,219),width=7)
                d.line((x,132,x,177),fill=(162,227,219),width=7)
            d.ellipse((171,160,215,204),fill=(95,151,78))
        else:
            for r in range(3):
                for c in range(5):
                    x=42+63*c;y=38+60*r
                    d.rounded_rectangle((x,y,x+51,y+51),radius=9,outline=(108,184,198),width=3)
                    d.line((x+5,y+25,x+46,y+25),fill=(77,186,230),width=10)
            d.ellipse((17,100,59,142),fill=(55,169,221))
            d.ellipse((326,100,368,142),fill=(219,175,86))
        out=io.BytesIO()
        im.save(out,format="WEBP",quality=62,method=6)
        data=out.getvalue()
        if not data.startswith(b"RIFF") or data[8:12]!=b"WEBP" or len(data)>100000:
            raise RuntimeError("WebP invalid or oversized")
        assets.append(data)
    return assets

def prepare(runid):
    base=root(runid)
    if base.exists():raise RuntimeError("Duplicate image run")
    if shutil.disk_usage(WEB).free<8*1024*1024:raise RuntimeError("Insufficient free disk")
    before={}
    for rel in PROTECTED+PAGES:before[rel]=h(read(rel))
    for rel in PAGES:
        if OLDMARK not in read(rel):raise RuntimeError("Expected released category card not found "+rel)
        if NEW in read(rel):raise RuntimeError("Images already added")
    for name in NAMES:
        if path(DIR+"/"+name).exists():raise RuntimeError("Target WebP exists")
    base.mkdir(parents=True,mode=0o700)
    (base/"before").mkdir()
    for rel in PAGES:
        d=base/"before"/rel;d.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(path(rel),d)
    assets=generate()
    (base/"stage").mkdir()
    for name,data in zip(NAMES,assets):(base/"stage"/name).write_bytes(data)
    save(base,{"state":"prepared","baseline":before,"created":[],"modified":[],"hashes":{},"sizes":dict(zip(NAMES,map(len,assets)))})
    print("IMAGE_BACKUP_AND_WEBP_PREPARED=PASS sizes="+str(dict(zip(NAMES,map(len,assets)))),flush=True)

def apply(runid):
    base=root(runid);m=load(base)
    if m["state"]!="prepared":raise RuntimeError("Not prepared")
    for rel,digest in m["baseline"].items():
        if h(read(rel))!=digest:raise RuntimeError("Concurrent edit detected "+rel)
    m["state"]="installing";save(base,m)
    for name in NAMES:
        rel=DIR+"/"+name;data=(base/"stage"/name).read_bytes()
        if path(rel).exists():raise RuntimeError("Collision "+rel)
        put(path(rel),data);m["created"].append(rel);m["hashes"][rel]=h(data);save(base,m)
    alts=[
        "تصویر اختصاصی سامانه آبیاری قطره‌ای و جریان آب در مزرعه",
        "تصویر اختصاصی گلخانه و تجهیزات گردش هوای کنترل‌شده",
        "تصویر اختصاصی بازی فکری مسیر آب و اتصال لوله‌ها"
    ]
    for rel,name,alt in zip(PAGES,NAMES,alts):
        old=read(rel)
        if OLDMarkMissing(old=old):raise RuntimeError("Missing release marker")
        img=('<img src="/'+DIR+'/'+name+'" alt="'+alt+'" width="384" height="240" loading="lazy" decoding="async" style="display:block;width:min(100%,360px);height:auto;border-radius:12px;border:1px solid #ae975a;margin:10px 0">').encode()
        if rel=="games/index.html":
            needle=b'<article class="card">'
            if old.count(needle)!=1:raise RuntimeError("Unexpected games hub markup")
            new=old.replace(needle,needle+img,1)
        else:
            needle=b'<section class="zm-hourly-addon"'
            if old.count(needle)!=1:raise RuntimeError("Unexpected category card markup")
            pivot=old.index(b">",old.index(needle))+1
            new=old[:pivot]+img+old[pivot:]
        new=new.replace(b"</main>",b"<!-- "+NEW+b" --></main>",1)
        if new==old:raise RuntimeError("Image insertion failed")
        m["modified"].append(rel);save(base,m)
        put(path(rel),new);m["hashes"][rel]=h(new);save(base,m)
    m["state"]="installed";save(base,m)
    print("ADDITIVE_WEBP_CARD_INSTALL=PASS",flush=True)

def OLDMarkMissing(old):return OLDMARK not in old
def verify(runid):
    base=root(runid);m=load(base)
    if m["state"]!="installed":raise RuntimeError("Not installed")
    for rel,sha in m["hashes"].items():
        if h(read(rel))!=sha:raise RuntimeError("Installed asset changed "+rel)
    for rel in PROTECTED:
        if h(read(rel))!=m["baseline"][rel]:raise RuntimeError("Protected site changed "+rel)
    for name in NAMES:
        u="https://zomorodmelal.ir/"+DIR+"/"+name+"?v="+runid
        with urllib.request.urlopen(urllib.request.Request(u,headers={"Cache-Control":"no-cache"}),timeout=25) as res:
            data=res.read(120000)
            if res.status!=200 or data[:4]!=b"RIFF" or data[8:12]!=b"WEBP":raise RuntimeError("Public WEBP failed "+name)
            if h(data)!=m["hashes"][DIR+"/"+name]:raise RuntimeError("Public WebP hash differs "+name)
        print("PUBLIC_WEBP=PASS "+name,flush=True)
    for rel in PAGES:
        route="/"+rel.replace("index.html","")
        with urllib.request.urlopen(urllib.request.Request("https://zomorodmelal.ir"+route+"?v="+runid,headers={"Cache-Control":"no-cache"}),timeout=25) as res:
            if res.status!=200 or NEW not in res.read(300000):raise RuntimeError("Public image-card failed "+route)
        print("PUBLIC_IMAGE_CARD=PASS "+route,flush=True)
    m["state"]="verified";save(base,m)
    print("ZOMOROD_THREE_CUSTOM_WEBP_LIVE=PASS",flush=True)

def rollback(runid):
    base=root(runid)
    if not (base/"manifest.json").exists():return
    m=load(base)
    for rel in reversed(m.get("modified",[])):
        old=(base/"before"/rel).read_bytes()
        p=path(rel)
        if p.is_file() and h(p.read_bytes())==m["hashes"].get(rel):
            put(p,old)
    for rel in reversed(m.get("created",[])):
        p=path(rel)
        if p.is_file() and h(p.read_bytes())==m["hashes"].get(rel):p.unlink()
    try:path(DIR).rmdir()
    except OSError:pass
    m["state"]="rolled_back";save(base,m)
    print("WEBP_RELEASE_ROLLBACK=COMPLETE",flush=True)

if __name__=="__main__":
    if len(sys.argv)!=3 or sys.argv[1] not in ("prepare","apply","verify","rollback"):
        raise SystemExit("Usage: script.py prepare|apply|verify|rollback RUN_ID")
    globals()[sys.argv[1]](sys.argv[2])
