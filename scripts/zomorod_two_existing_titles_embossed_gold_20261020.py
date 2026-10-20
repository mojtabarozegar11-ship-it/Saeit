#!/usr/bin/env python3
"""Reversible two-title gold typography only; preserve all existing home HTML and frames."""
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
BACKUPS = Path("/home/zomorod2/.backups/zm-gold-title-pair-20261020")
STYLE_ID = "zm-home-two-embossed-gold-titles-20261020"
STYLE = r'''<style id="zm-home-two-embossed-gold-titles-20261020">
/* ONLY existing two homepage title glyphs; no font/layout/frame/content changes. */
html body #main-view > .hero .hero-text h1,
html body #main-view > .orbit-intro h2 {
  color:#ffe778 !important;
  background-image:linear-gradient(180deg,
    #fffef4 0%,#fff8c8 12%,#ffe782 28%,#ffd347 44%,
    #fff5bc 53%,#ffd75c 66%,#ffed9a 83%,#fffbed 100%) !important;
  -webkit-background-clip:text !important;
  background-clip:text !important;
  -webkit-text-fill-color:transparent !important;
  -webkit-text-stroke:.38px rgba(255,235,145,.92);
  text-shadow:
    0 1px 0 rgba(255,252,211,.85),
    0 2px 0 rgba(247,208,97,.92),
    0 3px 0 rgba(222,176,63,.87),
    0 4px 0 rgba(174,125,35,.78),
    0 6px 7px rgba(44,30,5,.5),
    0 9px 17px rgba(0,0,0,.38),
    0 0 13px rgba(255,231,119,.79),
    0 0 26px rgba(255,216,86,.55) !important;
  filter:drop-shadow(0 0 8px rgba(255,220,100,.38));
}
@media(prefers-reduced-motion:reduce){
  html body #main-view > .hero .hero-text h1,
  html body #main-view > .orbit-intro h2 {transition:none !important;}
}
</style>
'''
MARKERS=(
    'id="main-view"', 'class="hero-text"', 'class="orbit-intro wrap"',
    'id="solar-stage"', 'id="orbital-cards"', 'id="orbit-shelves"',
    'id="site-footer"', 'ZOMOROD_ORBIT_DATA',
    'id="zm-home-dual-embossed-gold-20261020"',
    'id="zm-home-copy-cinematic-glass-20261019"',
    'id="zm-fixed-scientific-background-20261018"',
    'id="zm-glass-row-headers-20261018"',
)
def digest(data:bytes)->str: return hashlib.sha256(data).hexdigest()

def transform(before:bytes)->bytes:
    if len(before)<1500000 or before.count(b"</head>")!=1 or before.count(b"</body>")!=1:
        raise RuntimeError("Unexpected homepage structure; refuse")
    if before.count(('id="'+STYLE_ID+'"').encode())!=0:
        raise RuntimeError("Title patch already installed; refuse duplicate")
    if any(marker.encode() not in before for marker in MARKERS):
        raise RuntimeError("Missing homepage protection marker")
    frame=before.split(b'<style id="zm-home-dual-embossed-gold-20261020">',1)
    if len(frame)!=2 or b"#ffe77f" not in frame[1].split(b"</style>",1)[0]:
        raise RuntimeError("Expected current bright gold frames missing; refuse")
    after=before.replace(b"</head>",STYLE.encode("utf-8")+b"</head>",1)
    if after.replace(STYLE.encode("utf-8"),b"",1)!=before:
        raise RuntimeError("Existing page content changed")
    return after

def folder(run:str)->Path:
    if not re.fullmatch(r"[0-9]{1,20}",run):raise RuntimeError("Invalid run id")
    return BACKUPS/run

def safe()->None:
    if pwd.getpwuid(os.getuid()).pw_name!="zomorod2":
        raise RuntimeError("Unexpected account identity")
    if not HOME.is_file() or HOME.is_symlink() or HOME.parent.is_symlink() or BACKUPS.is_symlink():
        raise RuntimeError("Unsafe paths")

def atomic(path:Path,data:bytes,mode:int)->None:
    temporary=None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent,delete=False,prefix=".zm-two-title-") as handle:
            temporary=Path(handle.name)
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary,mode)
        os.replace(temporary,path)
    finally:
        if temporary is not None and temporary.exists():temporary.unlink()

def selftest()->None:
    frame='<style id="zm-home-dual-embossed-gold-20261020">#ffe77f</style>'
    sample=('<html><head>'+frame+'</head><body><main id="main-view">'
      '<section class="hero"><div class="hero-text"><h1>زمرد ملل</h1></div></section>'
      '<section class="orbit-intro wrap"><h2>حوزه‌های تخصصی زمرد ملل</h2></section>'
      '<div id="solar-stage"></div><div id="orbital-cards"></div>'
      '<div id="orbit-shelves"></div></main><footer id="site-footer"></footer>'
      '<style id="zm-home-copy-cinematic-glass-20261019"></style>'
      '<style id="zm-fixed-scientific-background-20261018"></style>'
      '<style id="zm-glass-row-headers-20261018"></style>'
      '<script>ZOMOROD_ORBIT_DATA</script></body></html>'+'x'*1600000).encode("utf-8")
    after=transform(sample)
    assert after.replace(STYLE.encode("utf-8"),b"",1)==sample
    assert after.count(('id="'+STYLE_ID+'"').encode())==1
    assert STYLE.count('html body #main-view > .hero .hero-text h1')==2
    assert STYLE.count('html body #main-view > .orbit-intro h2')==2
    assert '.topic-card' not in STYLE and '.card-track' not in STYLE
    assert '#main-view > .hero .hero-text::' not in STYLE
    assert '#main-view > .orbit-intro::' not in STYLE
    print("TWO_TITLE_GOLD_CSS_ONLY_SELFTEST=passed",flush=True)

def apply(run:str,expected:str)->None:
    safe()
    if not re.fullmatch(r"[a-f0-9]{64}",expected):raise RuntimeError("Invalid SHA")
    before=HOME.read_bytes()
    if digest(before)!=expected:raise RuntimeError("Concurrent homepage update detected")
    after=transform(before)
    location=folder(run)
    if location.exists() or location.is_symlink():raise RuntimeError("Backup already exists")
    location.mkdir(parents=True,mode=0o700)
    mode=HOME.stat().st_mode & 0o777
    atomic(location/"index.before.html",before,0o600)
    if digest((location/"index.before.html").read_bytes())!=expected:raise RuntimeError("Backup checksum mismatch")
    (location/"manifest.json").write_text(json.dumps({"before":expected,"after":digest(after),"mode":mode}),encoding="utf-8")
    if digest(HOME.read_bytes())!=expected:raise RuntimeError("Concurrent edit after backup")
    atomic(HOME,after,mode)
    if digest(HOME.read_bytes())!=digest(after):raise RuntimeError("Postwrite checksum mismatch")
    print("TWO_GOLD_TITLES_APPLIED=yes",flush=True)

def verify(run:str)->None:
    safe()
    location=folder(run)
    meta=json.loads((location/"manifest.json").read_text(encoding="utf-8"))
    before=(location/"index.before.html").read_bytes()
    after=HOME.read_bytes()
    if digest(before)!=meta["before"] or digest(after)!=meta["after"]:
        raise RuntimeError("Byte integrity mismatch")
    if after.replace(STYLE.encode("utf-8"),b"",1)!=before:
        raise RuntimeError("Existing original content not preserved")
    print("TWO_GOLD_TITLES_LOSSLESS_VERIFIED=yes",flush=True)

def rollback(run:str)->None:
    safe()
    location=folder(run)
    if not (location/"manifest.json").is_file():
        print("TWO_GOLD_TITLES_NO_INSTALL=yes",flush=True)
        return
    meta=json.loads((location/"manifest.json").read_text(encoding="utf-8"))
    before=(location/"index.before.html").read_bytes()
    if digest(before)!=meta["before"]:raise RuntimeError("Backup integrity failed")
    current=digest(HOME.read_bytes())
    if current==meta["before"]:return
    if current!=meta["after"]:raise RuntimeError("Concurrent edit; refuse unsafe rollback")
    atomic(HOME,before,meta["mode"])
    if digest(HOME.read_bytes())!=meta["before"]:raise RuntimeError("Rollback failed")
    print("TWO_GOLD_TITLES_ROLLED_BACK=yes",flush=True)

if __name__=="__main__":
    if sys.argv[1:]==["selftest"]:selftest()
    elif len(sys.argv)==4 and sys.argv[1]=="apply":apply(sys.argv[2],sys.argv[3])
    elif len(sys.argv)==3 and sys.argv[1]=="verify":verify(sys.argv[2])
    elif len(sys.argv)==3 and sys.argv[1]=="rollback":rollback(sys.argv[2])
    else:raise SystemExit("selftest | apply RUN EXPECTED_SHA | verify RUN | rollback RUN")
