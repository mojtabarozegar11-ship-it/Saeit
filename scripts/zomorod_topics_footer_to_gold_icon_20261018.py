#!/usr/bin/env python3
"""Safe, scoped migration of Zomorod main homepage's all-topics footer sentence to a gold icon.

Only writes /home/zomorod2/public_html/index.html. SHA-guarded backup + rollback.
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

ROOT = Path('/home/zomorod2/public_html')
PAGE = ROOT / 'index.html'
BACKUPS = Path('/home/zomorod2/.backups/zomorod-all-topics-icon-20261018')
EXPECTED_SHA256 = '7eb3cebe8285c357604695490f9ee6b58031aee2e4f7116d289d5adeb2a4e4c0'
OLD_LINE = '<p class="zm-full-topics-index-link"><a href="/topics/">دانشنامه تخصصی زمرد ملل؛ معرفی همه حوزه‌های علمی و فنی</a></p>'
HEADER_CONTROL_OPEN = '<nav class="zm-gold-toolbar-controls" aria-label="جست‌وجو و فروشگاه">'
CSS_MARKER = 'zm-topics-ornate-gold-icon-style-20261018'
ICON_ID = 'zm-topics-top-icon-20261018'

ICON = (
    '<a id="'+ICON_ID+'" class="zm-topics-gold-icon" href="/topics/"'
    ' title="دانشنامه تخصصی زمرد ملل؛ همه حوزه‌های علمی و فنی"'
    ' aria-label="دانشنامه تخصصی زمرد ملل؛ مشاهده همه حوزه‌های علمی و فنی">'
    '<svg xmlns="http://www.w3.org/2000/svg" aria-hidden="true"'
    ' width="29" height="29" viewBox="0 0 32 32" fill="none"'
    ' stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="1.8">'
    '<path d="M16 8.5c-3.2-2.3-7.6-3.1-12-2v16c4.6-1.1 8.9-.3 12 2'
    'm0-16c3.2-2.3 7.6-3.1 12-2v16c-4.6-1.1-8.9-.3-12 2V8.5Z"/>'
    '<path d="M16 8.5V24.5M7 12.5c2-.2 4.1.2 5.7 1.1M20 13.6c1.6-.9 3.7-1.3 5.7-1.1'
    'M7 16.5c2-.2 4.1.2 5.7 1.1M20 17.6c1.6-.9 3.7-1.3 5.7-1.1"/>'
    '<path d="M13 3h6m-3-3v6" stroke-width="1.3" stroke="#fff1bd"/>'
    '</svg>'
    '<span class="zm-topics-gold-icon-hint" aria-hidden="true">همه</span>'
    '</a>'
)

STYLE = r"""
<style id="zm-topics-ornate-gold-icon-style-20261018">
#zm-gold-search-toolbar-20261018 .zm-topics-gold-icon {
  box-sizing:border-box;position:relative;isolation:isolate;flex:0 0 57px;
  display:inline-flex!important;justify-content:center!important;align-items:center!important;
  width:57px;height:53px;min-width:53px;min-height:49px;
  border:1px solid #ffe9a9!important;border-radius:16px!important;
  color:#ffe4a0!important;text-decoration:none!important;
  background:linear-gradient(155deg,#2b4d36 0%,#122b23 56%,#102019 100%)!important;
  box-shadow:inset 0 1px 0 rgba(255,237,170,.32),0 3px 0 #947030,
    0 9px 18px rgba(0,0,0,.24),0 0 14px rgba(236,190,94,.09);
  overflow:visible;transition:transform .22s ease,box-shadow .22s ease;
}
#zm-gold-search-toolbar-20261018 .zm-topics-gold-icon::before {
  content:"";position:absolute;inset:3px;border:1px solid rgba(243,200,109,.48);
  border-radius:12px;pointer-events:none;
}
#zm-gold-search-toolbar-20261018 .zm-topics-gold-icon svg {
  width:28px;height:28px;display:block;color:#ffdb8b;filter:drop-shadow(0 0 5px rgba(243,190,77,.28));
}
#zm-gold-search-toolbar-20261018 .zm-topics-gold-icon .zm-topics-gold-icon-hint {
  position:absolute;bottom:-6px;right:-5px;padding:2px 5px;
  border:1px solid #edd38b;border-radius:8px;background:#1d3929;
  color:#fff1c4;font:700 9px/1.3 Tahoma,Arial,sans-serif;
  box-shadow:0 2px 5px rgba(0,0,0,.35);white-space:nowrap;
}
#zm-gold-search-toolbar-20261018 .zm-topics-gold-icon:hover {
  transform:translateY(-3px);
  box-shadow:inset 0 1px 0 rgba(255,237,170,.45),0 4px 0 #947030,
    0 12px 25px rgba(0,0,0,.35),0 0 22px rgba(236,190,94,.22);
}
#zm-gold-search-toolbar-20261018 .zm-topics-gold-icon:focus-visible {
  outline:3px solid #ffe9aa!important;outline-offset:4px;
}
@media(max-width:500px) {
  #zm-gold-search-toolbar-20261018 .zm-gold-toolbar-controls > a.zm-gold-store-entry[href="/store/"] {
    box-sizing:border-box;flex:1 1 155px!important;width:auto!important;min-width:145px;
  }
  #zm-gold-search-toolbar-20261018 .zm-topics-gold-icon {
    flex:0 0 57px!important;width:57px!important;height:50px!important;
  }
}
@media(prefers-reduced-motion:reduce) {
  #zm-gold-search-toolbar-20261018 .zm-topics-gold-icon{transition:none!important}
  #zm-gold-search-toolbar-20261018 .zm-topics-gold-icon:hover{transform:none!important}
}
</style>
"""

def digest(data:bytes)->str:
    return hashlib.sha256(data).hexdigest()

def safe_paths():
    if pwd.getpwuid(os.getuid()).pw_name != 'zomorod2':
        raise RuntimeError('Unexpected cPanel user')
    for p in (ROOT,PAGE):
        if p.is_symlink() or not p.exists():
            raise RuntimeError('Missing path or symlink: '+str(p))
    if not PAGE.is_file():
        raise RuntimeError('Expected static main root HTML')

def transform(src:str)->str:
    if src.count(OLD_LINE)!=1:
        raise RuntimeError('Footer topics sentence was moved or duplicated')
    if ICON_ID in src or CSS_MARKER in src:
        raise RuntimeError('Ornate icon already installed')
    if src.count(HEADER_CONTROL_OPEN)!=1 or src.count('</head>')!=1:
        raise RuntimeError('Main template navigation changed')
    if 'ZOMOROD_ORBIT_DATA' not in src or '<footer class="footer" id="site-footer"' not in src:
        raise RuntimeError('Wrong live root or missing essential site content')
    if not (src.index('<footer class="footer" id="site-footer"')<src.index(OLD_LINE)<src.index('</footer>')):
        raise RuntimeError('Topics sentence not in footer as expected')
    nav = src.index(HEADER_CONTROL_OPEN)
    nav_end = src.index('</nav>',nav)
    if not (nav<src.index('href="/store/"',nav)<nav_end<src.index('<main id="content">')):
        raise RuntimeError('Top controls not in intended header position')
    # Two exact, independent edits; no re-render or minification of homepage content.
    without_footer=src.replace(OLD_LINE,'',1)
    nav_tail=without_footer.index('</nav>',without_footer.index(HEADER_CONTROL_OPEN))
    with_icon=without_footer[:nav_tail]+ICON+without_footer[nav_tail:]
    result=with_icon.replace('</head>',STYLE+'</head>',1)

    if result.count('id="'+ICON_ID+'"')!=1 or result.count('href="/topics/"')!=src.count('href="/topics/"'):
        raise RuntimeError('Icon count or original directory link count differs')
    if OLD_LINE in result or 'zm-full-topics-index-link' in result:
        raise RuntimeError('Footer text not fully removed')
    if result.index('id="'+ICON_ID+'"')>result.index('<main id="content">'):
        raise RuntimeError('Topics icon was not moved above main content')
    if result.count('id="zm-gold-search-toolbar-20261018"')!=1:
        raise RuntimeError('Top header damaged')
    if result.count('action="/search/"')!=src.count('action="/search/"'):
        raise RuntimeError('Search form route damaged')
    if len(re.findall(r'<a\b[^>]*href="/store/"',result))!=len(re.findall(r'<a\b[^>]*href="/store/"',src)):
        raise RuntimeError('Store entry changed')
    if not 2200000<len(result)<2350000:
        raise RuntimeError('Unexpected main homepage size')
    # Full reversible reconstruction: only old <p>, inserted top icon, and CSS differ.
    reverse=result.replace(STYLE,'',1).replace(ICON,'',1)
    old_insert=src.index(OLD_LINE)
    reverse=reverse[:old_insert]+OLD_LINE+reverse[old_insert:]
    if reverse!=src:
        raise RuntimeError('Unrelated HTML bytes changed')
    return result

def atomic_replace(p:Path,data:bytes,mode:int):
    temp=None
    try:
        with tempfile.NamedTemporaryFile(dir=p.parent,prefix='.zm-topics-',delete=False) as f:
            temp=Path(f.name)
            f.write(data);f.flush();os.fsync(f.fileno())
        os.chmod(temp,mode)
        os.replace(temp,p)
    finally:
        if temp and temp.exists():
            temp.unlink()

def location(runid:str)->Path:
    if not re.fullmatch(r'[0-9]{1,20}',runid):
        raise RuntimeError('Invalid run ID')
    return BACKUPS/runid

def apply(runid:str):
    safe_paths()
    original=PAGE.read_bytes()
    if digest(original)!=EXPECTED_SHA256:
        raise RuntimeError('Homepage changed since audit; refusing unsafe overwrite')
    changed=transform(original.decode('utf8')).encode('utf8')
    backup=location(runid)
    if backup.exists() or backup.is_symlink():
        raise RuntimeError('Backup folder already exists')
    backup.mkdir(parents=True,mode=0o700)
    mode=PAGE.stat().st_mode & 0o777
    shutil.copy2(PAGE,backup/'index.original.html')
    if digest((backup/'index.original.html').read_bytes())!=EXPECTED_SHA256:
        raise RuntimeError('Original backup SHA mismatch')
    manifest={'before':EXPECTED_SHA256,'after':digest(changed),'mode':mode}
    (backup/'manifest.json').write_text(json.dumps(manifest))
    atomic_replace(PAGE,changed,mode)
    if digest(PAGE.read_bytes())!=manifest['after']:
        raise RuntimeError('Post-publish checksum mismatch')
    print('ZM_TOPICS_ICON_PUBLISHED=yes',flush=True)
    print('ZM_TOPICS_ICON_SHA='+manifest['after'],flush=True)
    print('ZM_BACKUP_VERIFIED=yes',flush=True)
    print('ZM_NO_PASSENGER_RESTART=yes',flush=True)

def rollback(runid:str):
    safe_paths()
    backup=location(runid)
    if backup.is_symlink():
        raise RuntimeError('Invalid backup symlink')
    manifest=json.loads((backup/'manifest.json').read_text())
    original=(backup/'index.original.html').read_bytes()
    if digest(original)!=manifest['before']:
        raise RuntimeError('Invalid backup')
    if digest(PAGE.read_bytes()) not in (manifest['after'],manifest['before']):
        raise RuntimeError('Unexpected concurrent edit; rollback refused')
    atomic_replace(PAGE,original,manifest['mode'])
    if digest(PAGE.read_bytes())!=manifest['before']:
        raise RuntimeError('Rollback verification failed')
    print('ZM_TOPICS_ICON_ROLLBACK_VERIFIED=yes')

def selftest():
    dummy=(
      '<html><head></head><body><nav class="header-orbit wrap">Nav</nav>'
      '<section id="zm-gold-search-toolbar-20261018">'
      + HEADER_CONTROL_OPEN + '<form action="/search/"></form>'
      '<a href="/store/">shop</a></nav></section>'
      '<main id="content">ZOMOROD_ORBIT_DATA <a href="/topics/">Some topic</a></main>'
      '<footer class="footer" id="site-footer">Legal'+OLD_LINE+'</footer></body></html>'
    )
    # The 2.2MB output size constraint is specifically for production, not synthetic test.
    sample=dummy+('z'*2200000)
    out=transform(sample)
    assert out.count('id="'+ICON_ID+'"')==1
    assert out.index('id="'+ICON_ID+'"')<out.index('<main id="content">')
    assert OLD_LINE not in out and 'Legal' in out
    print('ZM_TOPICS_ICON_SELFTEST=passed')

if __name__=='__main__':
    if len(sys.argv)==2 and sys.argv[1]=='selftest':
        selftest()
    elif len(sys.argv)==3 and sys.argv[1] in ('apply','rollback'):
        (apply if sys.argv[1]=='apply' else rollback)(sys.argv[2])
    else:
        raise SystemExit('Usage: selftest | apply RUN_ID | rollback RUN_ID')
