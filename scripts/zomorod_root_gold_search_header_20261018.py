#!/usr/bin/env python3
"""Move the existing Zomorod home search/store controls out of footer, atomically.

Scope: /home/zomorod2/public_html/index.html only.
No Passenger restart, no .htaccess edits, no child-sites, no store or search changes.
"""
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

HOME = Path("/home/zomorod2")
ROOT = HOME / "public_html"
PAGE = ROOT / "index.html"
BACKUPS = HOME / ".backups" / "zomorod-gold-search-header"
OLD_SHA = "2988abd7ce242c24ba9e9041c8bad053e5917c3b45fcae25cf87ff560c81baf7"
NEW_ID = "zm-gold-search-toolbar-20261018"
ORIGINAL_MARK = "<!-- zm-v11-site-links -->"
NAV_REGEX = re.compile(r'<nav\b[^>]*class="zm-v11-site-links"[^>]*>.*?</nav>\s*<!-- zm-v11-site-links -->', re.S | re.I)
ANCHOR_REGEX = re.compile(r'<nav\b[^>]*class="header-orbit wrap"[^>]*>.*?</nav>', re.S | re.I)
SAFE_STYLE_ID = "zm-gold-toolbar-style-20261018"

CSS = r"""
<style id="zm-gold-toolbar-style-20261018">
/* Only the standalone Zomorod public homepage, no site-wide template impact. */
#zm-gold-search-toolbar-20261018 {
  box-sizing:border-box;position:relative;z-index:90;
  display:flex!important;align-items:center;justify-content:space-between;gap:15px;
  direction:rtl;width:calc(100% - 24px);max-width:1420px;
  margin:12px auto 22px;padding:13px clamp(14px,2.2vw,27px);
  border:1px solid rgba(247,208,124,.72);border-radius:20px;
  background:linear-gradient(115deg,#071b17,#15362b 52%,#0a201c);
  box-shadow:0 15px 32px rgba(0,0,0,.29),inset 0 1px 0 rgba(255,237,180,.1);
}
#zm-gold-search-toolbar-20261018 .zm-gold-toolbar-label {
  flex:0 1 auto;min-width:0;display:flex;flex-direction:column;gap:3px;
}
#zm-gold-search-toolbar-20261018 .zm-gold-toolbar-label strong {
  color:#ffe5a8!important;font:800 clamp(14px,1.4vw,18px)/1.7 Tahoma,Arial,sans-serif!important;
}
#zm-gold-search-toolbar-20261018 .zm-gold-toolbar-label small {
  color:#d1c09c!important;font:400 12px/1.6 Tahoma,Arial,sans-serif!important;
}
#zm-gold-search-toolbar-20261018 .zm-gold-toolbar-controls{
  box-sizing:border-box;display:flex!important;align-items:stretch;justify-content:flex-end;
  flex:1 1 500px;max-width:740px;gap:11px;min-width:0;
}
#zm-gold-search-toolbar-20261018 form.zm-gold-search{
  box-sizing:border-box;margin:0!important;padding:4px!important;
  flex:1 1 360px;display:flex!important;align-items:stretch;min-width:0;
  min-height:49px;gap:5px;direction:rtl;
  border:1px solid #eec777!important;border-radius:13px;
  background:#0b241d!important;box-shadow:0 0 0 1px rgba(255,227,153,.10);
}
#zm-gold-search-toolbar-20261018 form.zm-gold-search:focus-within{
  outline:2px solid #ffebbd;outline-offset:2px;
}
#zm-gold-search-toolbar-20261018 form.zm-gold-search input[type="search"]{
  box-sizing:border-box;flex:1 1 auto;min-width:0;width:100%;
  border:0!important;border-radius:9px!important;outline:0!important;
  background:transparent!important;color:#fff3d7!important;
  padding:8px 13px!important;margin:0!important;
  font:500 15px/1.6 Tahoma,Arial,sans-serif!important;
}
#zm-gold-search-toolbar-20261018 form.zm-gold-search input::placeholder{
  color:#e3c68b!important;opacity:1!important;
}
#zm-gold-search-toolbar-20261018 form.zm-gold-search button {
  box-sizing:border-box;flex:0 0 auto;min-width:92px;padding:8px 14px!important;
  margin:0!important;border:0!important;border-radius:9px!important;
  background:linear-gradient(130deg,#fff0ba,#dbab4f 70%,#bb8735)!important;
  color:#1c200c!important;cursor:pointer;
  font:800 14px/1.6 Tahoma,Arial,sans-serif!important;
  box-shadow:inset 0 1px 0 rgba(255,255,255,.25);
}
#zm-gold-search-toolbar-20261018 form.zm-gold-search button:hover{
  background:linear-gradient(130deg,#fff5cf,#e9bc63)!important;
}
#zm-gold-search-toolbar-20261018 a.zm-gold-store-entry[href="/store/"]{
  box-sizing:border-box;flex:0 0 auto;min-height:49px;
  display:inline-flex!important;align-items:center;justify-content:center;
  border:1px solid #fff0b9!important;border-radius:13px!important;
  padding:11px 19px!important;margin:0!important;
  background:linear-gradient(130deg,#fbe2a0,#d0a046)!important;
  color:#172219!important;font:800 15px/1.5 Tahoma,Arial,sans-serif!important;
  white-space:nowrap;text-decoration:none!important;
  box-shadow:0 8px 20px rgba(212,165,81,.24);
}
#zm-gold-search-toolbar-20261018 a.zm-gold-store-entry:focus-visible{
  outline:3px solid #fff2ba!important;outline-offset:3px;
}
@media(max-width:820px){
  #zm-gold-search-toolbar-20261018{flex-wrap:wrap;padding:12px 15px}
  #zm-gold-search-toolbar-20261018 .zm-gold-toolbar-controls{max-width:none;flex:1 1 100%}
}
@media(max-width:500px){
  #zm-gold-search-toolbar-20261018{width:calc(100% - 16px);margin:9px auto 18px;gap:8px}
  #zm-gold-search-toolbar-20261018 .zm-gold-toolbar-label small{display:none}
  #zm-gold-search-toolbar-20261018 .zm-gold-toolbar-controls{flex-wrap:wrap;gap:8px}
  #zm-gold-search-toolbar-20261018 form.zm-gold-search{flex:1 1 100%;width:100%}
  #zm-gold-search-toolbar-20261018 a.zm-gold-store-entry{flex:1 1 100%;width:100%}
}
</style>
"""

# These are deliberately the exact old form/action and store target.
BAR = (
    '<section id="'+NEW_ID+'" class="zm-gold-toolbar wrap" '
    'aria-label="جست‌وجو و ورود به فروشگاه زمرد ملل">'
    '<div class="zm-gold-toolbar-label"><strong>جست‌وجو در زمرد ملل</strong>'
    '<small>دسترسی سریع به دانش، پژوهش و محصولات</small></div>'
    '<nav class="zm-gold-toolbar-controls" aria-label="جست‌وجو و فروشگاه">'
    '<form class="zm-gold-search" method="get" action="/search/" role="search">'
    '<label for="zm-top-search-q" '
    'style="position:absolute;width:1px;height:1px;padding:0;margin:-1px;overflow:hidden;clip:rect(0,0,0,0);white-space:nowrap;border:0">'
    'عبارت جست‌وجو</label>'
    '<input id="zm-top-search-q" type="search" name="q" '
    'placeholder="جست‌وجو در سایت" aria-label="جست‌وجو" maxlength="100" required>'
    '<button type="submit">⌕ جست‌وجو</button></form>'
    '<a class="zm-gold-store-entry" href="/store/">◈ ورود به فروشگاه</a>'
    '</nav></section>'
)

def sha(data:bytes)->str:
    return hashlib.sha256(data).hexdigest()

def backup_dir(run_id:str)->Path:
    if not re.fullmatch(r"[0-9]{1,20}",run_id):
        raise ValueError("Invalid release identifier")
    return BACKUPS/run_id

def guards():
    if pwd.getpwuid(os.getuid()).pw_name != "zomorod2":
        raise RuntimeError("Wrong cPanel user")
    for p in (ROOT,PAGE):
        if not p.exists() or p.is_symlink():
            raise RuntimeError("Unsafe target path "+str(p))
    if not PAGE.is_file():
        raise RuntimeError("Main root file absent")

def patch(s:str)->str:
    if NEW_ID in s or SAFE_STYLE_ID in s:
        raise RuntimeError("Toolbar already installed")
    if s.count(ORIGINAL_MARK)!=1:
        raise RuntimeError("Missing or duplicated legacy marker")
    legacy=list(NAV_REGEX.finditer(s))
    if len(legacy)!=1:
        raise RuntimeError("Expected exactly one legacy nav")
    old=legacy[0]
    original=old.group(0)
    if not all(x in original for x in ('action="/search/"','href="/store/"','name="q"','role="search"')):
        raise RuntimeError("Legacy routes differ")
    if not (s.index('<footer')<old.start()<s.index('</footer>')):
        raise RuntimeError("Legacy links no longer in footer")
    top=list(ANCHOR_REGEX.finditer(s))
    if len(top)!=1 or not top[0].end() < s.index('<main id="content">'):
        raise RuntimeError("Expected single header-orbit immediately before main")
    if not (top[0].end() < s.index('<footer')):
        raise RuntimeError("Top navigation not above footer")
    if s.count('</head>')!=1 or s.count('<footer')!=1 or s.count('</footer>')!=1:
        raise RuntimeError("Structural HTML markers changed")
    if 'ZOMOROD_ORBIT_DATA' not in s or 'zm-unified-v7-20261018' not in s:
        raise RuntimeError("Wrong main homepage template")
    # Remove only the legacy footer widget, then inject one gold toolbar in the top shell.
    stripped=s[:old.start()]+s[old.end():]
    matches=list(ANCHOR_REGEX.finditer(stripped))
    if len(matches)!=1:
        raise RuntimeError("Header moved during patch")
    insertion=matches[0].end()
    result=stripped[:insertion]+'\n'+BAR+'\n'+stripped[insertion:]
    result=result.replace('</head>',CSS+'</head>',1)
    if result.count('id="'+NEW_ID+'"')!=1:
        raise RuntimeError("Toolbar duplicate")
    if result.count('action="/search/"')!=1:
        raise RuntimeError("Search form duplicated")
    if result.count('href="/store/"')!=1:
        raise RuntimeError("Store action duplicated")
    if result.find('id="'+NEW_ID+'"') > result.find('<main id="content">'):
        raise RuntimeError("Toolbar not at the top")
    if result.find('id="'+NEW_ID+'"') > result.find('<footer'):
        raise RuntimeError("Toolbar still below footer")
    if len(result)-len(s) > 9000 or len(result)-len(s) < 2000:
        raise RuntimeError("Unexpected byte-change scope")
    # Strict round-trip proves the whole original homepage is intact except the widget and CSS.
    reversed_html=result.replace(CSS,'',1).replace('\n'+BAR+'\n','',1)
    reversed_html=reversed_html[:old.start()]+original+reversed_html[old.start():]
    if reversed_html!=s:
        raise RuntimeError("Unrelated bytes changed in home page")
    return result

def atomic_write(file:Path,bytes_:bytes,mode:int):
    staged=None
    try:
        with tempfile.NamedTemporaryFile(dir=file.parent,prefix=".zm-gold-",delete=False) as f:
            staged=Path(f.name)
            f.write(bytes_);f.flush();os.fsync(f.fileno())
        os.chmod(staged,mode)
        os.replace(staged,file)
    finally:
        if staged and staged.exists():
            staged.unlink()

def apply(run_id:str):
    guards()
    data=PAGE.read_bytes()
    if sha(data)!=OLD_SHA:
        raise RuntimeError("Live homepage changed since inspection; refuse destructive overwrite")
    next_bytes=patch(data.decode('utf8')).encode('utf8')
    dest=backup_dir(run_id)
    if dest.exists() or dest.is_symlink():
        raise RuntimeError("Backup already exists")
    dest.mkdir(parents=True,mode=0o700)
    original_mode=PAGE.stat().st_mode&0o777
    shutil.copy2(PAGE,dest/"index.original.html")
    if sha((dest/"index.original.html").read_bytes())!=OLD_SHA:
        raise RuntimeError("Backup checksum mismatch")
    manifest={"before":OLD_SHA,"after":sha(next_bytes),"mode":original_mode}
    (dest/"manifest.json").write_text(json.dumps(manifest))
    atomic_write(PAGE,next_bytes,original_mode)
    if sha(PAGE.read_bytes())!=manifest["after"]:
        raise RuntimeError("Postwrite sha mismatch")
    print("ZM_GOLD_ROOT_HEADER_PUBLISHED=yes",flush=True)
    print("ZM_GOLD_ROOT_NEW_SHA="+manifest["after"],flush=True)
    print("ZM_GOLD_PROTECTED_ROUTES_UNTOUCHED=yes",flush=True)

def rollback(run_id:str):
    guards()
    dest=backup_dir(run_id)
    if dest.is_symlink():
        raise RuntimeError("Backup directory is symlink")
    manifest=json.loads((dest/"manifest.json").read_text())
    old=(dest/"index.original.html").read_bytes()
    if sha(old)!=manifest["before"]:
        raise RuntimeError("Backup invalid")
    if sha(PAGE.read_bytes()) not in (manifest["after"],manifest["before"]):
        raise RuntimeError("Concurrent edit detected; refuse rollback")
    atomic_write(PAGE,old,manifest["mode"])
    if sha(PAGE.read_bytes())!=manifest["before"]:
        raise RuntimeError("Rollback not verified")
    print("ZM_GOLD_ROLLBACK_VERIFIED=yes",flush=True)

def selftest():
    sample=(
        '<html><head></head><body><!-- zm-unified-v7-20261018 -->'
        '<header class="topbar wrap">Logo</header>'
        '<nav class="header-orbit wrap"><a href="/">Home</a></nav><main id="content">Hi</main>'
        '<footer class="footer"><b>Legal content</b><nav class="zm-v11-site-links">'
        '<a href="/search/">Search</a><a href="/store/">Store</a>'
        '<form action="/search/" role="search"><input name="q"></form>'
        '</nav><!-- zm-v11-site-links --></footer>'
        '<script>ZOMOROD_ORBIT_DATA</script></body></html>'
    )
    out=patch(sample)
    assert out.count(NEW_ID)==1
    assert out.find(NEW_ID)<out.find('<main id="content">')
    assert out.find(NEW_ID)<out.find('<footer')
    assert '<b>Legal content</b>' in out
    assert out.count('action="/search/"')==1 and out.count('href="/store/"')==1
    print("ZM_GOLD_ROOT_PATCH_SELFTEST=passed")

if __name__=="__main__":
    if len(sys.argv)==2 and sys.argv[1]=="selftest":
        selftest()
    elif len(sys.argv)==3 and sys.argv[1] in ("apply","rollback"):
        (apply if sys.argv[1]=="apply" else rollback)(sys.argv[2])
    else:raise SystemExit("Usage: selftest | apply RUN_ID | rollback RUN_ID")
