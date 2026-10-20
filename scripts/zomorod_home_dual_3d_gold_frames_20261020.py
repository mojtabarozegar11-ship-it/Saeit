#!/usr/bin/env python3
"""Lossless, reversible, two-panel embossed gold trim on Zomorod Melal live homepage."""
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
BACKUPS = Path("/home/zomorod2/.backups/zm-dual-gold-frames-20261020")
STYLE_ID = "zm-home-dual-embossed-gold-20261020"
STYLE = r'''<style id="zm-home-dual-embossed-gold-20261020">
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
MARKERS = (
  'id="main-view"', 'class="hero-text"', 'class="orbit-intro wrap"',
  'id="solar-stage"', 'id="orbital-cards"', 'id="orbit-shelves"',
  'id="site-footer"', 'ZOMOROD_ORBIT_DATA',
  'id="zm-home-copy-cinematic-glass-20261019"',
  'id="zm-glass-row-headers-20261018"',
  'id="zm-fixed-scientific-background-20261018"'
)

def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def transform(before: bytes) -> bytes:
    html=before.decode("utf-8")
    if len(before)<1500000 or html.count("</head>")!=1 or html.count("</body>")!=1:
        raise RuntimeError("Unexpected live homepage; refuse")
    if ('id="'+STYLE_ID+'"') in html:
        raise RuntimeError("Dual gold trim already present")
    for marker in MARKERS:
        if marker not in html: raise RuntimeError("Missing protected feature: "+marker)
    after=html.replace("</head>",STYLE+"</head>",1).encode("utf-8")
    if after.replace(STYLE.encode("utf-8"),b"",1)!=before:
        raise RuntimeError("Lossless patch invariant failed")
    return after

def backup_dir(run: str) -> Path:
    if not re.fullmatch("[0-9]{1,20}",run): raise RuntimeError("Invalid run id")
    return BACKUPS/run

def safe() -> None:
    if pwd.getpwuid(os.getuid()).pw_name!="zomorod2":
        raise RuntimeError("Unexpected cPanel identity")
    if (not HOME.is_file() or HOME.is_symlink() or HOME.parent.is_symlink()
          or BACKUPS.is_symlink()):
        raise RuntimeError("Unsafe file path")

def atomic(path: Path, data: bytes, mode: int) -> None:
    temporary=None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent,delete=False,prefix=".zm-dual-gold-") as f:
            temporary=Path(f.name)
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.chmod(temporary,mode)
        os.replace(temporary,path)
    finally:
        if temporary is not None and temporary.exists():temporary.unlink()

def selftest() -> None:
    sample=(
        '<html><head></head><body>'
        '<main id="main-view"><div id="solar-stage"></div>'
        '<div id="orbital-cards"></div><div id="orbit-shelves"></div>'
        '<section class="hero"><div class="hero-text"></div></section>'
        '<section class="orbit-intro wrap"></section></main>'
        '<footer id="site-footer"></footer>'
        '<style id="zm-home-copy-cinematic-glass-20261019"></style>'
        '<style id="zm-glass-row-headers-20261018"></style>'
        '<style id="zm-fixed-scientific-background-20261018"></style>'
        '<script>ZOMOROD_ORBIT_DATA</script></body></html>'
        + 'X'*1600000
    ).encode("utf-8")
    result=transform(sample)
    assert result.replace(STYLE.encode(),b"",1)==sample
    assert result.count(('id="'+STYLE_ID+'"').encode())==1
    assert STYLE.count('html body #main-view > .hero .hero-text')>=2
    assert STYLE.count('html body #main-view > .orbit-intro')>=2
    assert 'pointer-events:none' in STYLE and 'mask-composite:exclude' in STYLE
    assert '.topic-card' not in STYLE and '.card-track' not in STYLE
    print("ZM_DUAL_GOLD_SELFTEST=passed",flush=True)

def apply(run: str, expected: str) -> None:
    safe()
    if not re.fullmatch("[a-f0-9]{64}",expected):raise RuntimeError("Invalid digest")
    before=HOME.read_bytes()
    if sha(before)!=expected:raise RuntimeError("Concurrent homepage edit")
    after=transform(before)
    folder=backup_dir(run)
    if folder.exists() or folder.is_symlink():raise RuntimeError("Backup path occupied")
    folder.mkdir(parents=True,mode=0o700)
    mode=HOME.stat().st_mode & 0o777
    atomic(folder/"index.before.html",before,0o600)
    if sha((folder/"index.before.html").read_bytes())!=expected:
        raise RuntimeError("Backup corruption")
    (folder/"manifest.json").write_text(json.dumps({"before":expected,"after":sha(after),"mode":mode}))
    if sha(HOME.read_bytes())!=expected: raise RuntimeError("Concurrent edit before publish")
    atomic(HOME,after,mode)
    if sha(HOME.read_bytes())!=sha(after):raise RuntimeError("Postwrite checksum mismatch")
    print("ZM_DUAL_GOLD_INSTALLED=yes",flush=True)

def verify(run: str) -> None:
    safe()
    folder=backup_dir(run)
    meta=json.loads((folder/"manifest.json").read_text())
    before=(folder/"index.before.html").read_bytes()
    after=HOME.read_bytes()
    if sha(before)!=meta["before"] or sha(after)!=meta["after"]:
        raise RuntimeError("Checksum mismatch")
    if after.replace(STYLE.encode(),b"",1)!=before:
        raise RuntimeError("Source HTML changed beyond CSS insertion")
    print("ZM_DUAL_GOLD_LOSSLESS_VERIFIED=yes",flush=True)

def rollback(run: str) -> None:
    safe()
    folder=backup_dir(run)
    if not (folder/"manifest.json").exists():
        print("ZM_DUAL_GOLD_NO_CHANGE_TO_RESTORE=yes",flush=True)
        return
    meta=json.loads((folder/"manifest.json").read_text())
    before=(folder/"index.before.html").read_bytes()
    if sha(before)!=meta["before"]:raise RuntimeError("Backup changed")
    current=sha(HOME.read_bytes())
    if current==meta["before"]:return
    if current!=meta["after"]:raise RuntimeError("Concurrent edit; reject destructive rollback")
    atomic(HOME,before,meta["mode"])
    print("ZM_DUAL_GOLD_ROLLED_BACK=yes",flush=True)

if __name__=="__main__":
    if sys.argv[1:]==["selftest"]:selftest()
    elif len(sys.argv)==4 and sys.argv[1]=="apply":apply(sys.argv[2],sys.argv[3])
    elif len(sys.argv)==3 and sys.argv[1]=="verify":verify(sys.argv[2])
    elif len(sys.argv)==3 and sys.argv[1]=="rollback":rollback(sys.argv[2])
    else:raise SystemExit("selftest | apply RUN SHA | verify RUN | rollback RUN")
