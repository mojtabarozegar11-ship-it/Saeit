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
    """Render original vector designs through existing ImageMagick on cPanel.
    No Pillow installation, shell injection or Django runtime modifications.
    """
    import subprocess
    executable=shutil.which("convert")
    if not executable:
        raise RuntimeError("ImageMagick convert is unavailable")
    common="fill none stroke '#d9c17f' stroke-width 4 roundrectangle 12,12 372,228 25,25"
    scenes=[
      [
        "fill '#e2b76d' stroke none circle 308,49 308,71",
        "fill '#355d36' stroke none polygon 0,182 384,147 384,240 0,240",
        "stroke '#53915a' stroke-width 6 fill none path 'M 20,220 L 368,170 M 15,195 L 320,150'",
        "stroke '#5bb8d0' stroke-width 15 fill none path 'M 34,91 L 350,91'",
        "stroke '#a8e5e9' stroke-width 4 fill none path 'M 34,84 L 350,84'",
        "stroke '#5bb8d0' stroke-width 9 fill none path 'M 83,91 L 83,140 M 151,91 L 151,130 M 219,91 L 219,120 M 286,91 L 286,110'",
        "fill '#91ddcc' stroke none circle 83,146 83,153 circle 151,138 151,145 circle 219,128 219,135",
      ],
      [
        "fill '#d5c57a' stroke none circle 318,59 318,77",
        "fill '#325b46' stroke none polygon 13,190 371,190 371,227 13,227",
        "stroke '#c6dbb5' stroke-width 6 fill none path 'M 48,138 L 192,47 L 336,138 M 48,138 L 48,206 L 336,206 L 336,138 M 192,47 L 192,206'",
        "stroke '#8bb8ba' stroke-width 3 fill none path 'M 120,95 L 120,205 M 261,95 L 261,205 M 48,163 L 336,163'",
        "fill '#6bad69' stroke none circle 120,176 120,194 circle 189,175 189,196 circle 270,176 270,195",
        "stroke '#a4dec0' stroke-width 7 fill none path 'M 120,203 L 120,174 M 188,205 L 188,168 M 270,205 L 270,172'",
      ],
      [
        "fill '#244a5b' stroke none roundrectangle 30,36 355,204 16,16",
        "stroke '#5b96ab' stroke-width 3 fill none path 'M 30,92 L 355,92 M 30,148 L 355,148 M 95,36 L 95,204 M 160,36 L 160,204 M 225,36 L 225,204 M 290,36 L 290,204'",
        "stroke '#77d7ed' stroke-width 15 fill none path 'M 62,120 L 126,120 L 126,64 L 192,64 L 192,178 L 258,178 L 258,120 L 323,120'",
        "stroke '#c4f2f1' stroke-width 4 fill none path 'M 62,115 L 126,115 L 126,64 L 192,64 L 192,178 L 258,178 L 258,120 L 323,120'",
        "fill '#91dbee' stroke none circle 60,120 60,139",
        "fill '#e1be74' stroke none circle 323,120 323,139",
      ]
    ]
    assets=[]
    for index,scene in enumerate(scenes):
        args=[executable,"-size","384x240",
              "xc:#253e31" if index!=2 else "xc:#193e48"]
        for draw in scene:
            args.extend(["-draw",draw])
        args.extend(["-draw",common,"-quality","70","webp:-"])
        result=subprocess.run(args,capture_output=True,timeout=30,check=False)
        if result.returncode:
            raise RuntimeError("WebP conversion failed for card "+str(index))
        data=result.stdout
        if not data.startswith(b"RIFF") or data[8:12]!=b"WEBP" or len(data)>100000:
            raise RuntimeError("Invalid or oversized WebP for card "+str(index))
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
            import re
            cards=list(re.finditer(rb"<article\b[^>]*>.*?</article>",old,re.S|re.I))
            target=[card for card in cards if b"/games/water-path/" in card.group(0)]
            if len(target)!=1:
                raise RuntimeError("Water Path game card cannot be isolated safely")
            card=target[0]
            insert_at=old.index(b">",card.start())+1
            new=old[:insert_at]+img+old[insert_at:]
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
