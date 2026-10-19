#!/usr/bin/env python3
"""Reversible, isolated 3D glass coating for the Zomorod homepage header and footer."""
import hashlib
import json
import os
import pwd
import re
import sys
import tempfile
from pathlib import Path

HOME=Path("/home/zomorod2/public_html/index.html")
BACKUPS=Path("/home/zomorod2/.backups/zomorod-home-header-footer-glass-20261019")
ID="zm-home-header-footer-glass-20261019"
STYLE=r'''<style id="zm-home-header-footer-glass-20261019">
/* Homepage-only 3D glass: paint existing header/footer, no menu rewrites. */
body header.topbar.wrap {
  background:
    radial-gradient(ellipse 80% 210% at 5% -54%,rgba(230,255,236,.29),transparent 76%),
    linear-gradient(145deg,rgba(68,143,106,.60),rgba(10,52,45,.82) 52%,rgba(4,26,32,.90)) !important;
  border-color:rgba(255,229,160,.86) !important;
  border-radius:clamp(16px,2vw,27px);
  outline:1px solid rgba(255,255,233,.41);
  outline-offset:-3px;
  box-shadow:
    inset 1px 2px 0 rgba(255,255,241,.54),
    inset -2px -3px 0 rgba(87,204,162,.24),
    inset 0 0 21px rgba(227,239,200,.08),
    0 13px 26px rgba(0,10,16,.35),
    0 26px 53px rgba(0,10,16,.27),
    0 0 22px rgba(241,197,94,.22) !important;
  -webkit-backdrop-filter:blur(11px) saturate(1.18);
  backdrop-filter:blur(11px) saturate(1.18);
  transition:border-color .28s ease,box-shadow .28s ease;
}
body header.topbar.wrap .identity,
body header.topbar.wrap .top-actions {
  border-radius:14px;
  background:linear-gradient(136deg,rgba(221,255,238,.085),rgba(3,25,29,.16));
  box-shadow:inset 1px 1px 0 rgba(255,255,244,.16);
}
body header.topbar.wrap .identity strong {
  color:#fff2cc;
  text-shadow:0 1px 4px rgba(0,9,12,.86),0 0 11px rgba(243,201,102,.22);
}
body #site-footer {
  background:transparent !important;
}
body #site-footer .footer-shell.wrap {
  border-radius:clamp(21px,3vw,36px);
  border:1.5px solid rgba(255,224,145,.82) !important;
  outline:1px solid rgba(251,250,227,.35);
  outline-offset:-3px;
  background:
    radial-gradient(ellipse 80% 120% at 11% -20%,rgba(220,255,236,.26),transparent 69%),
    linear-gradient(147deg,rgba(62,137,101,.52),rgba(10,51,45,.81) 54%,rgba(4,25,32,.88)) !important;
  box-shadow:
    inset 1px 2px 0 rgba(255,255,239,.49),
    inset -1px -2px 0 rgba(102,222,187,.23),
    0 17px 38px rgba(0,11,18,.38),
    0 33px 71px rgba(0,11,18,.24),
    0 0 24px rgba(237,197,99,.19) !important;
  -webkit-backdrop-filter:blur(12px) saturate(1.15);
  backdrop-filter:blur(12px) saturate(1.15);
}
body #site-footer .footer-grid > * {
  box-sizing:border-box;
  min-width:0;
  border-radius:clamp(13px,1.6vw,20px);
  border:1px solid rgba(242,215,153,.50);
  background:linear-gradient(145deg,rgba(210,255,235,.12),rgba(6,39,39,.35));
  box-shadow:inset 1px 1px 0 rgba(255,255,239,.23),
             inset -1px -1px 0 rgba(92,202,171,.12),
             0 12px 29px rgba(0,12,17,.21);
  padding:clamp(14px,2vw,24px);
}
body #site-footer :is(.footer-crest,.footer-site-nav h2,.footer-social-col h2){
  color:#fff0c5;
  text-shadow:0 2px 8px rgba(0,12,16,.82),0 0 13px rgba(251,215,129,.15);
}
body #site-footer :is(.footer-intro,.footer-social-lead,.footer-copyright){
  color:#f3f0df;
  text-shadow:0 1px 3px rgba(0,12,17,.85);
}
body #site-footer .footer-copyright {
  box-sizing:border-box;
  border:1px solid rgba(255,220,149,.51);
  border-radius:16px;
  padding:clamp(12px,2vw,18px);
  background:linear-gradient(145deg,rgba(223,255,235,.11),rgba(7,37,38,.49));
  box-shadow:inset 1px 1px 0 rgba(255,255,245,.26),
             0 11px 25px rgba(0,11,16,.22);
}
@media(max-width:700px){
  body header.topbar.wrap {
    -webkit-backdrop-filter:blur(5px) saturate(1.08);
    backdrop-filter:blur(5px) saturate(1.08);
  }
  body #site-footer .footer-shell.wrap {
    -webkit-backdrop-filter:blur(5px) saturate(1.08);
    backdrop-filter:blur(5px) saturate(1.08);
  }
  body #site-footer .footer-grid > * {padding:14px}
}
@media(hover:hover) and (pointer:fine){
  body header.topbar.wrap:hover {
    border-color:rgba(255,239,193,.98) !important;
    box-shadow:inset 1px 2px 0 rgba(255,255,239,.60),
               inset -2px -2px 0 rgba(93,219,178,.27),
               0 18px 39px rgba(0,10,16,.39),
               0 32px 64px rgba(0,10,16,.28),
               0 0 28px rgba(245,197,97,.30) !important;
  }
}
@media(prefers-reduced-motion:reduce){
  body header.topbar.wrap {transition:none !important}
}
</style>
'''

NEEDED=(
  'id="zm-fixed-scientific-background-20261018"',
  'id="zm-glass-floating-cards-20261018"',
  'id="zm-glass-row-headers-20261018"',
  'id="zm-home-copy-cinematic-glass-20261019"',
  'class="topbar wrap"', 'class="identity"', 'id="motion-toggle"',
  'id="site-footer"', 'class="footer-shell wrap"',
  'class="footer-grid"', 'class="footer-copyright"',
  'id="main-view"', 'id="orbital-cards"', 'id="solar-stage"',
  'ZOMOROD_ORBIT_DATA', '.topic-card', '.card-track'
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
        with tempfile.NamedTemporaryFile(dir=path.parent,delete=False,prefix=".zm-home-chrome-") as f:
            temporary=Path(f.name)
            f.write(data);f.flush();os.fsync(f.fileno())
        os.chmod(temporary,mode)
        os.replace(temporary,path)
    finally:
        if temporary is not None and temporary.exists(): temporary.unlink()

def selftest():
    sample=('<html><head></head><body><header class="topbar wrap">'
            '<a class="identity" href="#home">Logo</a><button id="motion-toggle"></button>'
            '</header><div id="main-view"><div id="solar-stage"></div>'
            '<div id="orbital-cards"></div></div>'
            '<style>.topic-card{}.card-track{}</style>'
            '<footer id="site-footer"><div class="footer-shell wrap">'
            '<div class="footer-grid"></div>'
            '<p class="footer-copyright"></p></div></footer>'
            '<script>ZOMOROD_ORBIT_DATA</script>'
            '<style id="zm-glass-floating-cards-20261018"></style>'
            '<style id="zm-glass-row-headers-20261018"></style>'
            '<style id="zm-home-copy-cinematic-glass-20261019"></style>'
            '<style id="zm-fixed-scientific-background-20261018"></style>'
            '</body></html>'+'x'*1600000).encode()
    after=transform(sample)
    assert after.replace(STYLE.encode(),b"",1)==sample
    assert after.count(('id="'+ID+'"').encode())==1
    assert all(x in STYLE for x in ('header.topbar.wrap','#site-footer',
        '.footer-shell.wrap','.footer-grid > *','.footer-copyright',
        'backdrop-filter','prefers-reduced-motion','box-shadow'))
    assert 'body .topic-card' not in STYLE and 'body .orbit-shelf' not in STYLE
    assert 'animation:' not in STYLE and 'transform:' not in STYLE
    print("HOME_CHROME_GLASS_SELFTEST=passed",flush=True)

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
    print("HOME_CHROME_GLASS_LIVE_APPLIED=yes",flush=True)

def verify(run):
    safety()
    location=run_path(run)
    meta=json.loads((location/"manifest.json").read_text())
    before=(location/"index.before.html").read_bytes()
    current=HOME.read_bytes()
    assert digest(before)==meta["before"] and digest(current)==meta["after"]
    assert current.replace(STYLE.encode(),b"",1)==before
    print("HOME_CHROME_GLASS_BYTE_LOSSLESS=yes",flush=True)

def rollback(run):
    safety()
    location=run_path(run)
    if not (location/"manifest.json").is_file():
        print("HOME_CHROME_GLASS_NO_INSTALL_TO_RESTORE=yes",flush=True)
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
    print("HOME_CHROME_GLASS_ROLLED_BACK=yes",flush=True)

if __name__=="__main__":
    if sys.argv[1:]==["selftest"]:selftest()
    elif len(sys.argv)==4 and sys.argv[1]=="apply":apply(sys.argv[2],sys.argv[3])
    elif len(sys.argv)==3 and sys.argv[1]=="verify":verify(sys.argv[2])
    elif len(sys.argv)==3 and sys.argv[1]=="rollback":rollback(sys.argv[2])
    else:raise SystemExit("Usage: selftest | apply RUN SHA | verify RUN | rollback RUN")
