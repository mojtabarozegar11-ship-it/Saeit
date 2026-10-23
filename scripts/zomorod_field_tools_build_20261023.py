#!/usr/bin/env python3
"""Immutable source pack: 2 original calculators, 2 distinct guides, 2 original WebPs."""
from pathlib import Path
from PIL import Image,ImageDraw
import hashlib,json,sys,math,random,re

SOURCE=Path(__file__).resolve().parents[1]/"content"/"zomorod-next-20261023"
MAPPING={
 "irrigation-uniformity/index.html":"agriculture/water-soil/emitter-uniformity/index.html",
 "greenhouse-dewpoint/index.html":"agriculture/greenhouse/dewpoint-vpd/index.html",
 "irrigation-uniformity-guide/index.html":"agriculture/water-soil/emitter-uniformity-guide/index.html",
 "greenhouse-dewpoint-guide/index.html":"agriculture/greenhouse/dewpoint-vpd-guide/index.html",
}
RELEASE="ZM-AGRICULTURE-TOOLS-20261023-B"
def image(dest:Path,variant:int):
    w,h=960,540
    im=Image.new("RGB",(w,h))
    px=im.load()
    for y in range(h):
        for x in range(w):
            t=y/h
            if variant==0:
                px[x,y]=(int(16+19*t),int(55+56*t),int(53+42*t))
            else:
                px[x,y]=(int(12+24*t),int(48+37*t),int(64+36*t))
    d=ImageDraw.Draw(im,"RGBA")
    r=random.Random(403+variant)
    for i in range(140):
        x=r.randrange(w);y=r.randrange(h);q=r.randrange(1,4)
        d.ellipse((x-q,y-q,x+q,y+q),fill=(224,241,210,r.randrange(20,80)))
    if variant==0:
        for i in range(5):
            y=120+i*78
            d.line((75,y,900,y),fill=(236,208,133,180),width=10)
            for j in range(9):
                x=115+j*90
                d.ellipse((x-11,y-11,x+11,y+11),fill=(255,232,165,255))
                dy=22+(i+j)%5*7
                d.ellipse((x-6,y+17,x+6,y+17+dy),fill=(112,229,228,210))
        for i in range(4):
            x=140+i*220
            d.rounded_rectangle((x,420,x+100,505),15,fill=(15,60,73,230),outline=(244,206,117,220),width=5)
            d.rectangle((x+9,452,x+91,494),fill=(73,173+10*i,189,180))
    else:
        d.ellipse((105,72,420,387),outline=(243,202,116,235),width=13)
        for i in range(7):
            a=2*math.pi*i/7
            x=262+125*math.cos(a);y=230+125*math.sin(a)
            d.line((262,230,x,y),fill=(242,220,168,130),width=4)
        d.ellipse((205,173,320,286),fill=(239,204,124,255))
        for i in range(10):
            x=545+(i%5)*78;y=145+(i//5)*125
            d.ellipse((x-20,y-35,x+20,y+35),fill=(107,218,231,180),outline=(203,249,248,190),width=3)
        d.line((505,412,882,412),fill=(253,207,134,230),width=7)
        d.polygon([(670,410),(725,355),(775,410)],fill=(239,174,119,235))
    dest.parent.mkdir(parents=True,exist_ok=True)
    im.save(dest,"WEBP",quality=70,method=6)
    data=dest.read_bytes()
    assert data[:4]==b"RIFF" and data[8:12]==b"WEBP" and len(data)<100000,(dest,len(data))
    print("WEBP_ORIGINAL",dest.name,len(data),hashlib.sha256(data).hexdigest()[:20])
def main(out:Path):
    out.mkdir(parents=True,exist_ok=True)
    for src,dst in MAPPING.items():
        text=(SOURCE/src).read_text("utf-8")
        assert RELEASE in text and '<html lang="fa" dir="rtl">' in text
        assert text.count('rel="canonical"')==1 and text.count('name="description"')==1
        assert text.count('<h1>')==1 and 'alt="' in text
        assert len(text)>4000,(src,len(text))
        p=out/dst;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(text,"utf-8")
    image(out/"agriculture/assets/field-tools-20261023/irrigation-uniformity.webp",0)
    image(out/"agriculture/assets/field-tools-20261023/greenhouse-dewpoint.webp",1)
    m={}
    for p in sorted(out.rglob("*")):
        if not p.is_file():continue
        rel=p.relative_to(out).as_posix()
        data=p.read_bytes()
        m[rel]={"sha256":hashlib.sha256(data).hexdigest(),"size":len(data),
                "url":"https://zomorodmelal.ir/"+rel.removesuffix("index.html")}
    assert len(m)==6
    (out/"source-manifest.json").write_text(json.dumps(m,ensure_ascii=False,indent=2),"utf-8")
    print("STAGED_TOOLS=2 STAGED_GUIDES=2 STAGED_IMAGES=2")
if __name__=="__main__":main(Path(sys.argv[1]))
