#!/usr/bin/env python3
"""Reversible glass-only treatment for unframed homepage text (not the site template)."""
import hashlib
import json
import os
import pwd
import re
import sys
import tempfile
from pathlib import Path

HOME=Path("/home/zomorod2/public_html/index.html")
BACKUPS=Path("/home/zomorod2/.backups/zomorod-home-copy-glass-20261019")
ID="zm-home-copy-cinematic-glass-20261019"
STYLE=r'''<style id="zm-home-copy-cinematic-glass-20261019">
/* Scoped to current public home only. Never alter the globe, row headers, fixed
   photograph, motion controls, 605 cards, navigation, or other URL paths. */
body #main-view > .hero .hero-text,
body #main-view > .orbit-intro {
  position:relative;
  isolation:isolate;
  box-sizing:border-box;
  border:1.5px solid rgba(255,224,153,.82) !important;
  border-radius:clamp(18px,2.6vw,30px);
  background:
    radial-gradient(ellipse 95% 125% at 9% -18%,rgba(226,255,236,.27),transparent 66%),
    linear-gradient(146deg,rgba(76,149,113,.43),rgba(13,58,50,.74) 46%,rgba(5,27,34,.84)) !important;
  outline:1px solid rgba(255,255,230,.35);
  outline-offset:-3px;
  box-shadow:inset 1px 2px 0 rgba(255,255,245,.47),
    inset -1px -2px 0 rgba(93,211,173,.22),inset 0 0 24px rgba(235,240,207,.065),
    0 16px 35px rgba(0,9,13,.38),0 30px 67px rgba(0,9,13,.27),
    0 0 24px rgba(244,193,93,.18) !important;
  -webkit-backdrop-filter:blur(11px) saturate(1.18);
  backdrop-filter:blur(11px) saturate(1.18);
  transition:box-shadow .3s ease,border-color .3s ease;
}
body #main-view > .hero .hero-text{padding:clamp(18px,3vw,38px);min-width:0;z-index:3}
body #main-view > .orbit-intro{
  padding:clamp(22px,3.4vw,46px);
  max-width:min(1320px,calc(100% - 32px));
  margin-inline:auto;
  color:#fbf4e1;
}
body #main-view > .hero .hero-text::before,
body #main-view > .orbit-intro::before{
  content:"";position:absolute;inset:1px;border-radius:inherit;
  pointer-events:none;z-index:-1;
  background:linear-gradient(128deg,rgba(255,255,255,.14),transparent 32%,transparent 74%,rgba(241,204,113,.06));
}
body #main-view > .hero .hero-text :is(h1,.claim),
body #main-view > .orbit-intro h2{
  text-shadow:0 2px 8px rgba(0,10,15,.68),0 0 17px rgba(244,199,109,.13);
}
body #main-view > .hero .hero-text :is(.claim,.lede),
body #main-view > .orbit-intro > p{
  color:#f5f1e5;text-shadow:0 1px 4px rgba(0,10,15,.8);
}
body #main-view > .orbit-intro > *{position:relative;z-index:1}
body #main-view .mobile-nav-note{
  border:1px solid rgba(255,225,155,.71);
  border-radius:16px;
  background:linear-gradient(140deg,rgba(66,140,112,.51),rgba(6,36,37,.76));
  box-shadow:inset 1px 1px 0 rgba(255,255,238,.33),0 12px 26px rgba(0,12,18,.33);
  -webkit-backdrop-filter:blur(7px);backdrop-filter:blur(7px);
  padding:9px 15px;color:#fff5d9;text-shadow:0 1px 3px #041510;
}
@media(max-width:700px){
  body #main-view > .hero .hero-text{padding:20px 17px;max-width:100%}
  body #main-view > .orbit-intro{padding:22px 18px;max-width:calc(100% - 20px)}
  body #main-view > .hero .hero-text,body #main-view > .orbit-intro{
    -webkit-backdrop-filter:blur(4px) saturate(1.1);
    backdrop-filter:blur(4px) saturate(1.1);
  }
}
@media(hover:hover) and (pointer:fine){
  body #main-view > .hero .hero-text:hover,
  body #main-view > .orbit-intro:hover{
    border-color:rgba(255,240,191,.95) !important;
    box-shadow:inset 1px 2px 0 rgba(255,255,245,.52),
      inset -1px -2px 0 rgba(112,236,192,.28),0 20px 43px rgba(0,9,14,.41),
      0 35px 78px rgba(0,9,14,.26),0 0 27px rgba(245,196,94,.29) !important;
  }
}
@media(prefers-reduced-motion:reduce){
  body #main-view > .hero .hero-text,body #main-view > .orbit-intro{
    transition:none !important;
  }
}
</style>
'''

NEEDED=(
  'id="zm-fixed-scientific-background-20261018"',
  'id="zm-glass-floating-cards-20261018"',
  'id="zm-glass-row-headers-20261018"',
  'id="main-view"', 'class="hero-text"', 'class="orbit-intro wrap"',
  'class="mobile-nav-note"', 'id="orbital-cards"', 'id="solar-stage"',
  'id="site-footer"', 'ZOMOROD_ORBIT_DATA', '.topic-card', '.card-track'
)

def digest(value):
    return hashlib.sha256(value).hexdigest()

def transform(before):
    html=before.decode("utf-8")
    if len(before)<1500000 or html.count("</head>")!=1 or html.count("</body>")!=1:
        raise RuntimeError("Unexpected homepage structure; refusing modification")
    if 'id="'+ID+'"' in html:
        raise RuntimeError("Glass already present; refusing duplicate")
    for marker in NEEDED:
        if marker not in html:
            raise RuntimeError("Missing protected homepage feature: "+marker)
    after=html.replace("</head>",STYLE+"</head>",1).encode("utf-8")
    if after.replace(STYLE.encode(),b"",1)!=before:
        raise RuntimeError("Original HTML content modified")
    return after

def run_path(run):
    if not re.fullmatch(r"[0-9]{1,20}",run):
        raise RuntimeError("Invalid run")
    return BACKUPS/run

def safety():
    if pwd.getpwuid(os.getuid()).pw_name!="zomorod2":
        raise RuntimeError("Unexpected cPanel identity")
    if not HOME.is_file() or HOME.is_symlink() or HOME.parent.is_symlink() or BACKUPS.is_symlink():
        raise RuntimeError("Unsafe live file or backup path")

def atomic(path,data,mode):
    temporary=None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent,delete=False,prefix=".zm-home-copy-") as f:
            temporary=Path(f.name)
            f.write(data);f.flush();os.fsync(f.fileno())
        os.chmod(temporary,mode)
        os.replace(temporary,path)
    finally:
        if temporary is not None and temporary.exists(): temporary.unlink()

def selftest():
    sample=('<html><head></head><body><div id="main-view"><section class="hero">'
            '<div class="hero-text"></div><div class="mobile-nav-note"></div>'
            '<div id="solar-stage"></div><div id="orbital-cards"></div></section>'
            '<section class="orbit-intro wrap"></section></div>'
            '<style>.topic-card{}.card-track{}</style>'
            '<footer id="site-footer"></footer><script>ZOMOROD_ORBIT_DATA</script>'
            '<style id="zm-glass-floating-cards-20261018"></style>'
            '<style id="zm-glass-row-headers-20261018"></style>'
            '<style id="zm-fixed-scientific-background-20261018"></style>'
            '</body></html>'+'x'*1600000).encode()
    after=transform(sample)
    assert after.replace(STYLE.encode(),b"",1)==sample
    assert after.count(('id="'+ID+'"').encode())==1
    assert all(x in STYLE for x in ('.hero-text','.orbit-intro','.mobile-nav-note',
        'backdrop-filter','prefers-reduced-motion','box-shadow'))
    assert 'body .topic-card' not in STYLE and 'body .orbit-shelf' not in STYLE
    assert 'animation:' not in STYLE and 'transform:' not in STYLE
    print("HOME_COPY_GLASS_SELFTEST=passed",flush=True)

def apply(run,expected):
    safety()
    if not re.fullmatch("[a-f0-9]{64}",expected):
        raise RuntimeError("Invalid expected SHA256")
    before=HOME.read_bytes()
    if digest(before)!=expected:
        raise RuntimeError("Concurrent change; refusing overwrite")
    after=transform(before)
    location=run_path(run)
    if location.exists() or location.is_symlink():
        raise RuntimeError("Backup directory exists")
    location.mkdir(mode=0o700,parents=True)
    mode=HOME.stat().st_mode & 0o777
    atomic(location/"index.before.html",before,0o600)
    assert digest((location/"index.before.html").read_bytes())==expected
    metadata={"before":expected,"after":digest(after),"mode":mode}
    (location/"manifest.json").write_text(json.dumps(metadata),encoding="utf-8")
    if digest(HOME.read_bytes())!=expected:
        raise RuntimeError("Concurrent update after backup")
    atomic(HOME,after,mode)
    assert digest(HOME.read_bytes())==metadata["after"]
    print("HOME_COPY_GLASS_LIVE_APPLIED=yes",flush=True)

def verify(run):
    safety()
    location=run_path(run)
    meta=json.loads((location/"manifest.json").read_text())
    before=(location/"index.before.html").read_bytes()
    current=HOME.read_bytes()
    assert digest(before)==meta["before"] and digest(current)==meta["after"]
    assert current.replace(STYLE.encode(),b"",1)==before
    print("HOME_COPY_GLASS_BYTE_LOSSLESS=yes",flush=True)

def rollback(run):
    safety()
    location=run_path(run)
    if not (location/"manifest.json").is_file():
        print("HOME_COPY_GLASS_NO_INSTALL_TO_RESTORE=yes",flush=True)
        return
    meta=json.loads((location/"manifest.json").read_text())
    before=(location/"index.before.html").read_bytes()
    if digest(before)!=meta["before"]:
        raise RuntimeError("Corrupt backup")
    now=digest(HOME.read_bytes())
    if now==meta["before"]:return
    if now!=meta["after"]:
        raise RuntimeError("Concurrent changes; refusing rollback")
    atomic(HOME,before,meta["mode"])
    assert digest(HOME.read_bytes())==meta["before"]
    print("HOME_COPY_GLASS_ROLLED_BACK=yes",flush=True)

if __name__=="__main__":
    if sys.argv[1:]==["selftest"]:selftest()
    elif len(sys.argv)==4 and sys.argv[1]=="apply":apply(sys.argv[2],sys.argv[3])
    elif len(sys.argv)==3 and sys.argv[1]=="verify":verify(sys.argv[2])
    elif len(sys.argv)==3 and sys.argv[1]=="rollback":rollback(sys.argv[2])
    else:raise SystemExit("Usage: selftest | apply RUN SHA | verify RUN | rollback RUN")
