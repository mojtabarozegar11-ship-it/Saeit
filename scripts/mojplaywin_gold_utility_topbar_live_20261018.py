#!/usr/bin/env python3
"""Correct MojPlayWin public homepage utility placement, preserving all other files."""
from __future__ import annotations
import hashlib
import json
import os
import pwd
import re
import shutil
import sys
import tempfile
from pathlib import Path

HOME=Path("/home/zomorod2")
ROOT=HOME/"mojplaywin.com"
TARGET=ROOT/"design-preview-20261017/production-home-20261017.html"
ROUTES=ROOT/".htaccess"
BACKUPS=HOME/".mojplaywin-backups"
EXACT_OLD_SHA="6feddcd5bea7251fa4985cb9515014ff9806e61c3e9cfc23277dfe3ec00eef7b"
FORM_ID="mpw-top-search-gold-20261018"
PANEL_ID="mpw-top-utility-panel-20261018"
STYLE_ID="mpw-top-header-gold-css-20261018"

CSS=r"""
<style id="mpw-top-header-gold-css-20261018">
/* Isolated static root-page utilities. No shared Django templates or other hosts. */
#mpw-top-utility-panel-20261018{
  box-sizing:border-box;position:relative;z-index:1050;
  width:calc(100% - 24px);max-width:1416px;margin:8px auto 9px;
  padding:11px clamp(12px,2.2vw,28px);
  display:flex;align-items:center;justify-content:space-between;gap:15px;
  border:1px solid rgba(230,184,90,.59);border-radius:15px;
  background:linear-gradient(120deg,#10100e,#211b11 55%,#0f0f0d);
  box-shadow:0 9px 26px rgba(0,0,0,.28),inset 0 1px 0 rgba(255,228,174,.09);
}
#mpw-top-utility-panel-20261018 .mpw-utility-intro{
  display:flex;flex-direction:column;gap:2px;min-width:0;
}
#mpw-top-utility-panel-20261018 .mpw-utility-intro strong{
  color:#ffe2a0!important;font:800 12px/1.4 system-ui,sans-serif;
  letter-spacing:.12em;text-transform:uppercase;
}
#mpw-top-utility-panel-20261018 .mpw-utility-intro small{
  color:#bfb39d!important;font:400 12px/1.3 system-ui,sans-serif;
}
#mpw-top-utility-panel-20261018 .mpw-utility-controls{
  display:flex;align-items:center;justify-content:flex-end;gap:10px;
  flex:1 1 auto;min-width:0;
}
#mpw-top-utility-panel-20261018 .mpw-header-search-gold{
  box-sizing:border-box;display:flex;align-items:stretch;
  width:min(430px,100%);min-width:220px;height:48px;
  margin:0!important;padding:4px!important;gap:4px;
  border:1px solid #e8c475!important;border-radius:11px;
  background:#12100d!important;
  box-shadow:0 0 0 1px rgba(246,211,134,.09),0 5px 18px rgba(0,0,0,.28);
}
#mpw-top-utility-panel-20261018 .mpw-header-search-gold:focus-within{
  outline:3px solid #fff0bf;outline-offset:2px;
}
#mpw-top-utility-panel-20261018 .mpw-header-search-gold input[type="search"]{
  min-width:0;flex:1 1 auto;width:100%;
  box-sizing:border-box;padding:9px 12px!important;margin:0!important;
  border:0!important;border-radius:7px!important;box-shadow:none!important;
  color:#fff4d8!important;background:#12100d!important;
  font:500 16px/1.3 system-ui,sans-serif!important;outline:none!important;
}
#mpw-top-utility-panel-20261018 .mpw-header-search-gold input::placeholder{
  color:#dfc38b!important;opacity:1!important;
}
#mpw-top-utility-panel-20261018 .mpw-header-search-gold button{
  min-width:44px;flex:0 0 44px;border:0!important;border-radius:8px!important;
  padding:8px!important;margin:0!important;cursor:pointer;
  background:linear-gradient(140deg,#ffe7a8,#cd983e)!important;
  color:#160f05!important;font:800 21px/1 system-ui,sans-serif!important;
}
#mpw-top-utility-panel-20261018 .mpw-header-search-gold button:hover{
  background:linear-gradient(140deg,#fff2d2,#e6b35a)!important;
}
#mpw-top-utility-panel-20261018 .mw-nav-cta[href="/store/"]{
  display:inline-flex!important;align-items:center!important;justify-content:center!important;
  box-sizing:border-box;flex:0 0 auto;min-height:48px;
  padding:10px 18px!important;margin:0!important;white-space:nowrap!important;
  border:1px solid #ffe5a5!important;border-radius:11px!important;
  background:linear-gradient(135deg,#f4d68d,#c89638)!important;
  color:#181006!important;text-decoration:none!important;
  font:800 14px/1.2 system-ui,sans-serif!important;
  box-shadow:0 6px 17px rgba(214,169,73,.2);
}
#mpw-top-utility-panel-20261018 .mw-nav-cta[href="/store/"]:focus-visible{
  outline:3px solid #fff0bf!important;outline-offset:3px;
}
@media(max-width:680px){
  #mpw-top-utility-panel-20261018{
    width:calc(100% - 16px);margin:5px auto 8px;
    padding:10px;flex-wrap:wrap;gap:8px;
  }
  #mpw-top-utility-panel-20261018 .mpw-utility-intro small{display:none}
  #mpw-top-utility-panel-20261018 .mpw-utility-controls{width:100%;flex-wrap:wrap;gap:8px}
  #mpw-top-utility-panel-20261018 .mpw-header-search-gold{
    flex:1 1 100%;width:100%;min-width:0;
  }
  #mpw-top-utility-panel-20261018 .mw-nav-cta[href="/store/"]{
    flex:1 1 auto;width:100%;
  }
}
</style>
"""

def digest(s:bytes)->str:
    return hashlib.sha256(s).hexdigest()

def folder(run_id:str)->Path:
    if not re.fullmatch(r"[0-9]{1,20}",run_id): raise RuntimeError("Invalid run ID")
    return BACKUPS/("mpw-gold-utility-topbar-"+run_id)

def verify_path():
    if pwd.getpwuid(os.getuid()).pw_name!="zomorod2":raise RuntimeError("Invalid server user")
    for p in (ROOT,TARGET,ROUTES):
        if not p.exists() or p.is_symlink():raise RuntimeError("Missing or symbolic source: "+str(p))
    rewrite=ROUTES.read_text(encoding="utf8",errors="replace")
    if "RewriteRule ^.*$ /design-preview-20261017/production-home-20261017.html [END,QSD]" not in rewrite:
        raise RuntimeError("Actual public home route has changed")

def change(text:str)->str:
    if PANEL_ID in text:raise RuntimeError("Already installed")
    if text.count('id="'+STYLE_ID+'"')!=1 or text.count('id="'+FORM_ID+'"')!=1:
        raise RuntimeError("Existing single gold search/style markers missing")
    if text.count("mpw-home-ten-guides")<1 or "mpw-17x20-mainonly-autostart" not in text:
        raise RuntimeError("Homepage content or orbit carousel markers missing")
    if "Mojtaba Roozegar" not in text or "<footer" not in text:
        raise RuntimeError("Founder credit or footer missing")
    header=re.search(r'<header\b[^>]*class="mw-site-nav"[^>]*>.*?</header>',text,re.S|re.I)
    if not header:raise RuntimeError("MojPlayWin top header cannot be found")
    original_header=header.group(0)
    form=re.search(r'<form\b[^>]*id="'+FORM_ID+r'"[^>]*>.*?</form>',original_header,re.S|re.I)
    if not form:raise RuntimeError("Existing search form is not in top navigation")
    link=re.search(r'<a\b[^>]*class="mw-nav-cta"[^>]*href="/store/"[^>]*>Enter Store ↗</a>',original_header)
    if not link:raise RuntimeError("Existing store CTA not in navigation")
    if link.start()<form.end():raise RuntimeError("Unexpected original control ordering")
    new_header=original_header.replace(form.group(0),"",1).replace(link.group(0),"",1)
    if FORM_ID in new_header or "Enter Store ↗" in new_header:
        raise RuntimeError("Old controls could not be removed")
    panel=(
        '<section class="mpw-top-utility-panel" id="'+PANEL_ID+'" aria-label="Site search and digital store">'
        '<div class="mpw-utility-intro"><strong>Search Moj Play Win</strong>'
        '<small>Quick access to research, games and products</small></div>'
        '<div class="mpw-utility-controls">'+form.group(0)+link.group(0)+'</div></section>'
    )
    changed=text[:header.start()]+panel+new_header+text[header.end():]
    style=re.search(r'<style id="'+STYLE_ID+r'">.*?</style>',changed,re.S|re.I)
    if not style:raise RuntimeError("Existing gold CSS not found")
    changed=changed[:style.start()]+CSS+changed[style.end():]
    original_footer=text[text.rfind('<footer class="mw-site-footer"'):]
    if not original_footer or not changed.endswith(original_footer):
        raise RuntimeError("Footer/trailing JavaScript changed")
    if changed.count('id="'+FORM_ID+'"')!=1 or changed.count('id="'+PANEL_ID+'"')!=1:
        raise RuntimeError("Duplicate search or utility panel")
    if changed.find('id="'+PANEL_ID+'"')>=changed.find('<header class="mw-site-nav"'):
        raise RuntimeError("Gold search is not physically before main header")
    if len(re.findall(r'<a\b[^>]*href="/store/"',changed))!=len(re.findall(r'<a\b[^>]*href="/store/"',text)):
        raise RuntimeError("Store links have changed")
    if abs(len(changed)-len(text))>7000:raise RuntimeError("Unexpected replacement size")
    return changed

def atomic(target:Path,payload:bytes,mode:int):
    temporary=None
    try:
        with tempfile.NamedTemporaryFile("wb",dir=target.parent,prefix=".mpw-utility-",delete=False) as fh:
            temporary=Path(fh.name);fh.write(payload);fh.flush();os.fsync(fh.fileno())
        os.chmod(temporary,mode);os.replace(temporary,target)
    finally:
        if temporary and temporary.exists():temporary.unlink()

def install(run_id:str):
    verify_path()
    original=TARGET.read_bytes()
    if digest(original)!=EXACT_OLD_SHA:raise RuntimeError("Live hash changed; refuse to overwrite")
    result=change(original.decode("utf8")).encode("utf8")
    backup=folder(run_id)
    if backup.exists() or backup.is_symlink():raise RuntimeError("Existing backup folder")
    backup.mkdir(parents=True,mode=0o700)
    mode=TARGET.stat().st_mode&0o777
    shutil.copy2(TARGET,backup/"homepage.original.html")
    if digest((backup/"homepage.original.html").read_bytes())!=EXACT_OLD_SHA:
        raise RuntimeError("Backup verification failed")
    meta={"before":EXACT_OLD_SHA,"after":digest(result),"mode":mode}
    (backup/"manifest.json").write_text(json.dumps(meta))
    atomic(TARGET,result,mode)
    if digest(TARGET.read_bytes())!=meta["after"]:raise RuntimeError("Atomic write verification failed")
    print("MPW_TOP_UTILITY_PUBLISHED=yes",flush=True)
    print("MPW_TOP_UTILITY_SHA256="+meta["after"],flush=True)
    print("MPW_PASSENGER_UNTOUCHED=yes",flush=True)

def rollback(run_id:str):
    verify_path()
    backup=folder(run_id)
    if backup.is_symlink():raise RuntimeError("Unsafe backup folder")
    meta=json.loads((backup/"manifest.json").read_text())
    old=(backup/"homepage.original.html").read_bytes()
    if digest(old)!=meta["before"]:raise RuntimeError("Bad original backup")
    if digest(TARGET.read_bytes()) not in (meta["before"],meta["after"]):
        raise RuntimeError("Unexpected concurrent edit; refuse overwrite")
    atomic(TARGET,old,meta["mode"])
    if digest(TARGET.read_bytes())!=meta["before"]:raise RuntimeError("Rollback digest failed")
    print("MPW_TOP_UTILITY_ROLLBACK_VERIFIED=yes",flush=True)

def selftest():
    original=('<html><head><style id="'+STYLE_ID+'">old</style></head><body>'
      '<header class="mw-site-nav"><a class="mw-brand" href="/">Logo</a>'
      '<nav class="mw-navigation"><a class="mw-nav-cta" href="/other/">Other</a>'
      '<form id="'+FORM_ID+'" action="/search/" method="get"><input name="q"></form>'
      '<a class="mw-nav-cta" href="/store/">Enter Store ↗</a></nav></header>'
      '<div id="mpw-home-ten-guides">10</div><p>mpw-17x20-mainonly-autostart</p>'
      '<footer class="mw-site-footer">Mojtaba Roozegar</footer></body></html>')
    result=change(original)
    assert result.count('id="'+PANEL_ID+'"')==1
    assert result.find(PANEL_ID)<result.find('<header class="mw-site-nav"')
    assert result.count('action="/search/"')==1
    assert result.endswith(original[original.index('<footer class="mw-site-footer"'):])
    print("MPW_TOP_UTILITY_SELFTEST_OK=yes")

if __name__=="__main__":
    if len(sys.argv)==2 and sys.argv[1]=="selftest":selftest()
    elif len(sys.argv)==3 and sys.argv[1] in ("install","rollback"):
        (install if sys.argv[1]=="install" else rollback)(sys.argv[2])
    else:raise SystemExit("Usage: selftest | install RUN_ID | rollback RUN_ID")
