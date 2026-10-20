#!/usr/bin/env python3
"""Replace ONLY copper/gold color values inside the two existing homepage frame CSS rules."""
from __future__ import annotations
import hashlib
import json
import os
import pwd
import re
import sys
import tempfile
from pathlib import Path

HOME = Path("/home/zomorod2/public_html/index.html")
BACKUPS = Path("/home/zomorod2/.backups/zm-dual-frame-brightgold-20261020")
STYLE_ID = "zm-home-dual-embossed-gold-20261020"
OLD_STYLE = r'''<style id="zm-home-dual-embossed-gold-20261020">
/* Metallic relief strictly for the two home glass panels. Glass, text, orbit
   animations, individual shelf headings and topic cards remain unchanged. */
html body #main-view > .hero .hero-text,
html body #main-view > .orbit-intro {
  position:relative;
  isolation:isolate;
  border:3px solid #dbb259 !important;
  outline:1px solid rgba(255,239,164,.56);
  outline-offset:-7px;
  border-radius:clamp(18px,2.6vw,30px);
  box-shadow:
    inset 0 2px 0 rgba(255,251,210,.85),
    inset 2px 0 0 rgba(255,225,145,.66),
    inset 0 -3px 0 rgba(85,48,8,.92),
    inset -2px 0 0 rgba(126,78,18,.78),
    inset 0 0 18px rgba(255,207,106,.13),
    0 2px 0 #f2ce73,
    0 4px 0 #a57421,
    0 7px 0 #65410e,
    0 13px 24px rgba(0,10,12,.49),
    0 25px 54px rgba(0,10,12,.28),
    0 0 22px rgba(244,185,66,.26) !important;
  transition:box-shadow .24s ease,border-color .24s ease;
}
html body #main-view > .hero .hero-text::after,
html body #main-view > .orbit-intro::after {
  content:"";
  position:absolute;
  inset:-3px;
  z-index:3;
  box-sizing:border-box;
  border:3px solid transparent;
  border-radius:inherit;
  background:linear-gradient(137deg,
    #fff9cc 0%,#f7d882 12%,#b88026 29%,#6e460f 42%,
    #e2b654 53%,#ffecac 64%,#ae7621 79%,#694514 100%) border-box;
  -webkit-mask:linear-gradient(#fff 0 0) padding-box,linear-gradient(#fff 0 0);
  -webkit-mask-composite:xor;
  mask-composite:exclude;
  pointer-events:none;
}
@media(hover:hover) and (pointer:fine){
  html body #main-view > .hero .hero-text:hover,
  html body #main-view > .orbit-intro:hover {
    border-color:#ffe29a !important;
    box-shadow:
      inset 0 2px 0 rgba(255,250,206,.91),
      inset 2px 0 0 rgba(255,225,145,.66),
      inset 0 -3px 0 rgba(85,48,8,.92),
      inset -2px 0 0 rgba(126,78,18,.78),
      0 2px 0 #ffda80,0 4px 0 #b67f25,0 7px 0 #65410e,
      0 16px 28px rgba(0,10,12,.48),
      0 30px 55px rgba(0,10,12,.27),
      0 0 30px rgba(247,198,88,.35) !important;
  }
}
@media(max-width:700px){
  html body #main-view > .hero .hero-text,
  html body #main-view > .orbit-intro {
    border-width:3px !important;
    outline-offset:-6px;
    box-shadow:
      inset 0 1px 0 rgba(255,251,210,.8),
      inset 0 -2px 0 rgba(85,48,8,.9),
      0 2px 0 #ecc06b,0 4px 0 #835719,
      0 10px 24px rgba(0,10,12,.43),
      0 0 16px rgba(244,185,66,.24) !important;
  }
}
@media(prefers-reduced-motion:reduce){
  html body #main-view > .hero .hero-text,
  html body #main-view > .orbit-intro {transition:none !important;}
}
</style>
'''
NEW_STYLE = r'''<style id="zm-home-dual-embossed-gold-20261020">
/* Metallic relief strictly for the two home glass panels. Glass, text, orbit
   animations, individual shelf headings and topic cards remain unchanged. */
html body #main-view > .hero .hero-text,
html body #main-view > .orbit-intro {
  position:relative;
  isolation:isolate;
  border:3px solid #ffe77f !important;
  outline:1px solid rgba(255,250,213,.97);
  outline-offset:-7px;
  border-radius:clamp(18px,2.6vw,30px);
  box-shadow:
    inset 0 2px 0 rgba(255,255,240,.98),
    inset 2px 0 0 rgba(255,246,190,.95),
    inset 0 -3px 0 rgba(234,190,67,.88),
    inset -2px 0 0 rgba(250,223,123,.94),
    inset 0 0 18px rgba(255,237,147,.38),
    0 2px 0 #fff5bf,
    0 4px 0 #ffdf76,
    0 7px 0 #dfa918,
    0 13px 24px rgba(0,10,12,.49),
    0 25px 54px rgba(0,10,12,.28),
    0 0 22px rgba(255,229,87,.76) !important;
  transition:box-shadow .24s ease,border-color .24s ease;
}
html body #main-view > .hero .hero-text::after,
html body #main-view > .orbit-intro::after {
  content:"";
  position:absolute;
  inset:-3px;
  z-index:3;
  box-sizing:border-box;
  border:3px solid transparent;
  border-radius:inherit;
  background:linear-gradient(137deg,
    #fffef1 0%,#fff5bf 12%,#ffe47d 29%,#ffd447 42%,
    #fff0a1 53%,#fffde2 64%,#ffe170 79%,#fff4b9 100%) border-box;
  -webkit-mask:linear-gradient(#fff 0 0) padding-box,linear-gradient(#fff 0 0);
  -webkit-mask-composite:xor;
  mask-composite:exclude;
  pointer-events:none;
}
@media(hover:hover) and (pointer:fine){
  html body #main-view > .hero .hero-text:hover,
  html body #main-view > .orbit-intro:hover {
    border-color:#fffbe3 !important;
    box-shadow:
      inset 0 2px 0 rgba(255,255,241,.99),
      inset 2px 0 0 rgba(255,246,190,.95),
      inset 0 -3px 0 rgba(234,190,67,.88),
      inset -2px 0 0 rgba(250,223,123,.94),
      0 2px 0 #fff8d4,0 4px 0 #ffe17c,0 7px 0 #dfa918,
      0 16px 28px rgba(0,10,12,.48),
      0 30px 55px rgba(0,10,12,.27),
      0 0 30px rgba(255,230,102,.83) !important;
  }
}
@media(max-width:700px){
  html body #main-view > .hero .hero-text,
  html body #main-view > .orbit-intro {
    border-width:3px !important;
    outline-offset:-6px;
    box-shadow:
      inset 0 1px 0 rgba(255,254,231,.98),
      inset 0 -2px 0 rgba(239,194,61,.87),
      0 2px 0 #fff5c1,0 4px 0 #ffdc62,
      0 10px 24px rgba(0,10,12,.43),
      0 0 16px rgba(255,229,83,.73) !important;
  }
}
@media(prefers-reduced-motion:reduce){
  html body #main-view > .hero .hero-text,
  html body #main-view > .orbit-intro {transition:none !important;}
}
</style>
'''
NEEDED = (
    'id="main-view"', 'class="hero-text"', 'class="orbit-intro wrap"',
    'id="solar-stage"', 'id="orbital-cards"', 'id="orbit-shelves"',
    'ZOMOROD_ORBIT_DATA',
    'id="zm-home-copy-cinematic-glass-20261019"',
    'id="zm-glass-floating-cards-20261018"',
    'id="zm-glass-row-headers-20261018"',
    'id="zm-fixed-scientific-background-20261018"',
)

def digest(data: bytes)->str:
    return hashlib.sha256(data).hexdigest()

def transform(before: bytes)->bytes:
    if len(before)<1500000:
        raise RuntimeError("Unexpected homepage size; refuse")
    if any(token.encode() not in before for token in NEEDED):
        raise RuntimeError("Missing protected homepage markup")
    old=OLD_STYLE.encode("utf-8")
    new=NEW_STYLE.encode("utf-8")
    if before.count(old)!=1:
        raise RuntimeError("Previously installed copper frame style differs; refuse unsafe edit")
    if before.count(('id="'+STYLE_ID+'"').encode())!=1:
        raise RuntimeError("Unexpected style id count")
    after=before.replace(old,new,1)
    if after.replace(new,old,1)!=before:
        raise RuntimeError("HTML not conserved beyond exact CSS replacement")
    return after

def where(run: str)->Path:
    if not re.fullmatch("[0-9]{1,20}",run):
        raise RuntimeError("Invalid run id")
    return BACKUPS/run

def safety():
    if pwd.getpwuid(os.getuid()).pw_name!="zomorod2":
        raise RuntimeError("Unexpected cPanel user")
    if not HOME.is_file() or HOME.is_symlink() or HOME.parent.is_symlink() or BACKUPS.is_symlink():
        raise RuntimeError("Unsafe paths")

def atomic(path: Path, data: bytes, mode:int):
    temp=None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent,delete=False,prefix=".zm-frame-gold-") as f:
            temp=Path(f.name)
            f.write(data);f.flush();os.fsync(f.fileno())
        os.chmod(temp,mode)
        os.replace(temp,path)
    finally:
        if temp is not None and temp.exists():temp.unlink()

def selftest():
    assert OLD_STYLE.count('html body #main-view > .hero .hero-text')==NEW_STYLE.count('html body #main-view > .hero .hero-text')
    assert OLD_STYLE.count('html body #main-view > .orbit-intro')==NEW_STYLE.count('html body #main-view > .orbit-intro')
    assert OLD_STYLE.count('{')==NEW_STYLE.count('{') and OLD_STYLE.count('}')==NEW_STYLE.count('}')
    assert 'border:3px solid #ffe77f !important' in NEW_STYLE
    assert '#fffef1' in NEW_STYLE and '#fffde2' in NEW_STYLE
    assert '#a57421' not in NEW_STYLE and '#65410e' not in NEW_STYLE
    assert '.topic-card' not in NEW_STYLE and '.card-track' not in NEW_STYLE
    assert OLD_STYLE!=NEW_STYLE
    dummy=(
      '<html><head>'+OLD_STYLE+'</head><body><main id="main-view">'
      '<div class="hero-text"></div><div class="orbit-intro wrap"></div>'
      '<div id="solar-stage"></div><div id="orbital-cards"></div>'
      '<div id="orbit-shelves"></div></main>'
      '<style id="zm-home-copy-cinematic-glass-20261019"></style>'
      '<style id="zm-glass-floating-cards-20261018"></style>'
      '<style id="zm-glass-row-headers-20261018"></style>'
      '<style id="zm-fixed-scientific-background-20261018"></style>'
      '<script>ZOMOROD_ORBIT_DATA</script></body></html>'
      + 'x'*1600000).encode('utf-8')
    out=transform(dummy)
    assert out.replace(NEW_STYLE.encode(),OLD_STYLE.encode(),1)==dummy
    assert len(out)-len(dummy)==len(NEW_STYLE.encode())-len(OLD_STYLE.encode())
    print("ZM_ONLY_FRAME_COLOR_REPLACEMENT_SELFTEST=passed",flush=True)

def apply(run:str, expected:str):
    safety()
    if not re.fullmatch("[a-f0-9]{64}",expected):raise RuntimeError("Bad expected sha")
    before=HOME.read_bytes()
    if digest(before)!=expected:raise RuntimeError("Concurrent file edit")
    after=transform(before)
    loc=where(run)
    if loc.exists() or loc.is_symlink():raise RuntimeError("Existing backup location")
    loc.mkdir(mode=0o700,parents=True)
    mode=HOME.stat().st_mode & 0o777
    atomic(loc/"index.before.html",before,0o600)
    if digest((loc/"index.before.html").read_bytes())!=expected:raise RuntimeError("Backup not reliable")
    (loc/"manifest.json").write_text(json.dumps({"before":expected,"after":digest(after),"mode":mode}),encoding="utf-8")
    if digest(HOME.read_bytes())!=expected:raise RuntimeError("Concurrent change after backup")
    atomic(HOME,after,mode)
    if digest(HOME.read_bytes())!=digest(after):raise RuntimeError("Unexpected postwrite checksum")
    print("ZM_BRIGHT_GOLD_FRAME_COLORS_INSTALLED=yes",flush=True)

def verify(run:str):
    safety()
    loc=where(run)
    m=json.loads((loc/"manifest.json").read_text(encoding="utf-8"))
    before=(loc/"index.before.html").read_bytes()
    after=HOME.read_bytes()
    if digest(before)!=m["before"] or digest(after)!=m["after"]:raise RuntimeError("File checksum changed")
    if after.replace(NEW_STYLE.encode(),OLD_STYLE.encode(),1)!=before:
        raise RuntimeError("Non-frame material altered")
    print("ZM_ONLY_TWO_FRAME_CSS_CHANGED_AND_VERIFIED=yes",flush=True)

def rollback(run:str):
    safety()
    loc=where(run)
    if not (loc/"manifest.json").is_file():
        print("ZM_BRIGHT_GOLD_NOT_INSTALLED=yes",flush=True)
        return
    m=json.loads((loc/"manifest.json").read_text(encoding="utf-8"))
    before=(loc/"index.before.html").read_bytes()
    if digest(before)!=m["before"]:raise RuntimeError("Backup changed")
    now=digest(HOME.read_bytes())
    if now==m["before"]:return
    if now!=m["after"]:raise RuntimeError("Concurrent updates; refuse rollback")
    atomic(HOME,before,m["mode"])
    assert digest(HOME.read_bytes())==m["before"]
    print("ZM_BRIGHT_GOLD_FRAME_COLORS_ROLLED_BACK=yes",flush=True)

if __name__=="__main__":
    if sys.argv[1:]==["selftest"]:selftest()
    elif len(sys.argv)==4 and sys.argv[1]=="apply":apply(sys.argv[2],sys.argv[3])
    elif len(sys.argv)==3 and sys.argv[1]=="verify":verify(sys.argv[2])
    elif len(sys.argv)==3 and sys.argv[1]=="rollback":rollback(sys.argv[2])
    else:raise SystemExit("Usage: selftest | apply RUN SHA | verify RUN | rollback RUN")
