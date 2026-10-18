#!/usr/bin/env python3
"""Two strictly additive CSS effects for Zomorod root homepage.
FX5: subtle golden animated light under preexisting nav.
FX7: card depth and micro-lift without replacing existing transform or click handling.
Changes ONLY /home/zomorod2/public_html/index.html and creates private SHA verified backup.
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

PAGE=Path('/home/zomorod2/public_html/index.html')
BACKUP=Path('/home/zomorod2/.backups/zomorod-fx5-fx7-20261018')
ORIGINAL_SHA='98d7912c08f2599015c422dab7f032618ae1dcab9ffc5a74d20d9926553f93c9'
MARKER='zm-fx5-fx7-extra-css-20261018'

CSS=r"""
<style id="zm-fx5-fx7-extra-css-20261018">
/* Zomorod FX5: purely decorative light under original chain menu, no new layout box.
   Uses an unused nav pseudo element; no changes to navigation links or destinations. */
html body nav.header-orbit::after{
  content:"";position:absolute;pointer-events:none;
  left:1%;right:1%;bottom:-2px;height:3px;border-radius:999px;
  background:linear-gradient(90deg,
    transparent 0%,rgba(233,193,100,.04) 20%,
    rgba(241,204,117,.36) 40%,#ffefb6 49%,#ffe09b 51%,
    rgba(240,193,101,.33) 62%,rgba(231,185,91,.06) 82%,transparent 100%);
  background-size:260% 100%;background-position:100% 50%;
  opacity:.78;
  box-shadow:0 0 7px rgba(243,199,103,.33);
  animation:zm-fx5-gold-ray-travel-20261018 14s ease-in-out infinite;
}
@keyframes zm-fx5-gold-ray-travel-20261018{
  0%,100%{background-position:100% 50%;opacity:.14}
  20%{opacity:.46}
  50%{background-position:0% 50%;opacity:.83}
  79%{opacity:.43}
}
/* Zomorod FX7: preserve existing transform: scale(1.05) translateY(-5px)
   and improve elevation with composited micro-lift + layered visual shadow.
   Never change dimensions, layout order, click handling or card content. */
@media (hover:hover) and (pointer:fine){
  #content .topic-card{
    transition-property:transform,box-shadow,outline-color,filter,translate;
    transition-duration:.22s,.28s,.25s,.26s,.26s;
    transition-timing-function:ease-out;
  }
  #content .topic-card:hover{
    translate:0 -2px;
    filter:brightness(1.07) saturate(1.035);
    outline-color:rgba(255,227,156,.8);
    box-shadow:
      0 14px 30px rgba(4,19,10,.35),
      0 0 23px rgba(252,205,107,.3),
      inset 0 0 13px rgba(255,221,147,.10);
  }
}
#content .topic-card:focus-visible,
#content .topic-card:focus-within{
  filter:brightness(1.055);
  outline:2px solid rgba(255,238,185,.80);
  outline-offset:2px;
  box-shadow:0 0 24px rgba(255,216,130,.34),0 14px 24px rgba(5,20,10,.25);
}
/* Respect existing site pause switch and visitor motion preferences. */
.motion-paused nav.header-orbit::after{animation-play-state:paused!important}
@media(prefers-reduced-motion:reduce){
  html body nav.header-orbit::after{
    animation:none!important;
    background-position:50% 50%;opacity:.35;
  }
  #content .topic-card{
    transition:none!important;
  }
  #content .topic-card:hover{
    translate:none!important;
  }
}
@media(max-width:600px){
  html body nav.header-orbit::after{
    height:2px;animation-duration:22s;opacity:.50;
  }
}
</style>
"""

def digest(data:bytes)->str:
    return hashlib.sha256(data).hexdigest()

def backup_dir(runid:str)->Path:
    if not re.fullmatch(r'[0-9]{1,20}',runid):
        raise RuntimeError('Invalid deployment run id')
    return BACKUP/runid

def guard():
    if pwd.getpwuid(os.getuid()).pw_name!='zomorod2':
        raise RuntimeError('Wrong hosting user')
    if not PAGE.is_file() or PAGE.is_symlink() or PAGE.parent.is_symlink():
        raise RuntimeError('Unsafe homepage path')

def change(s:str)->str:
    if 'id="'+MARKER+'"' in s:raise RuntimeError('Already installed')
    markers=(
        '<header class="topbar wrap"',
        'class="header-orbit wrap"',
        'id="solar-stage"',
        'class="orbital-cards"',
        'id="zm-gold-search-toolbar-20261018"',
        'id="zm-topics-top-icon-20261018"',
        'id="zm-four-premium-fx-css-20261018"',
        '<footer class="footer" id="site-footer"',
    )
    for mark in markers:
        if s.count(mark)!=1:
            raise RuntimeError('Protected homepage element changed: '+mark)
    if '.topic-card:hover' not in s or '@keyframes ring-wave' not in s:
        raise RuntimeError('Card motion or globe controls missing')
    if 'ZOMOROD_ORBIT_DATA' not in s or s.count('</head>')!=1:
        raise RuntimeError('Main homepage data missing')
    before=s.index('</head>')
    nav=s.index('class="header-orbit wrap"')
    if not before<nav<s.index('<main id="content">')<s.index('<footer class="footer"'):
        raise RuntimeError('Main homepage hierarchy unexpected')
    result=s.replace('</head>',CSS+'</head>',1)
    if result.replace(CSS,'',1)!=s:
        raise RuntimeError('Original HTML was modified')
    if result.count('id="'+MARKER+'"')!=1 or len(result)-len(s)!=len(CSS):
        raise RuntimeError('Unexpected insertion size or duplicated CSS')
    for key in ('action="/search/"','href="/store/"','href="/topics/"'):
        if result.count(key)!=s.count(key):
            raise RuntimeError('Protected action link changed: '+key)
    return result

def atomic_replace(path:Path,body:bytes,mode:int):
    temp=None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent,prefix='.zm-fx57-',delete=False) as f:
            temp=Path(f.name);f.write(body);f.flush();os.fsync(f.fileno())
        os.chmod(temp,mode);os.replace(temp,path)
    finally:
        if temp and temp.exists():temp.unlink()

def apply(runid:str):
    guard()
    before=PAGE.read_bytes()
    if digest(before)!=ORIGINAL_SHA:
        raise RuntimeError('Root HTML has changed since inspection; refuse overwrite')
    next_bytes=change(before.decode('utf8')).encode('utf8')
    folder=backup_dir(runid)
    if folder.exists() or folder.is_symlink():
        raise RuntimeError('Backup folder already present')
    folder.mkdir(parents=True,mode=0o700)
    mode=PAGE.stat().st_mode&0o777
    shutil.copy2(PAGE,folder/'index.original.html')
    if digest((folder/'index.original.html').read_bytes())!=ORIGINAL_SHA:
        raise RuntimeError('Backup sha verification failed')
    manifest={'before':ORIGINAL_SHA,'after':digest(next_bytes),'mode':mode}
    (folder/'manifest.json').write_text(json.dumps(manifest))
    atomic_replace(PAGE,next_bytes,mode)
    if digest(PAGE.read_bytes())!=manifest['after']:
        raise RuntimeError('Published root sha verification failed')
    print('ZM_FX57_PUBLISHED=yes',flush=True)
    print('ZM_FX57_NEW_SHA='+manifest['after'],flush=True)
    print('ZM_FX57_BACKUP_VERIFIED=yes',flush=True)
    print('ZM_FX57_CSS_ONLY=yes',flush=True)

def rollback(runid:str):
    guard()
    folder=backup_dir(runid)
    if folder.is_symlink():raise RuntimeError('Unsafe backup symlink')
    manifest=json.loads((folder/'manifest.json').read_text())
    old=(folder/'index.original.html').read_bytes()
    if digest(old)!=manifest['before']:
        raise RuntimeError('Backup invalid')
    if digest(PAGE.read_bytes()) not in (manifest['before'],manifest['after']):
        raise RuntimeError('Concurrent edit; rollback refuses overwrite')
    atomic_replace(PAGE,old,manifest['mode'])
    if digest(PAGE.read_bytes())!=manifest['before']:
        raise RuntimeError('Rollback hash mismatch')
    print('ZM_FX57_ROLLBACK_VERIFIED=yes',flush=True)

def selftest():
    s=('<html><head><title>ZM</title></head><body>'
       '<header class="topbar wrap"><nav class="header-orbit wrap">Navigation</nav></header>'
       '<main id="content"><div id="solar-stage"><div class="orbital-cards"></div></div>'
       '<div class="orbit-shelves"></div>'
       '<style id="zm-four-premium-fx-css-20261018"></style>'
       '<section id="zm-gold-search-toolbar-20261018">'
       '<a id="zm-topics-top-icon-20261018" href="/topics/">Book</a>'
       '<a href="/store/">Shop</a>'
       '<form action="/search/"></form></section>'
       '<p>.topic-card:hover @keyframes ring-wave</p></main>'
       '<footer class="footer" id="site-footer">Original Footer</footer>'
       '<script>ZOMOROD_ORBIT_DATA</script></body></html>')
    out=change(s)
    assert out.replace(CSS,'',1)==s
    assert out.count('id="'+MARKER+'"')==1
    assert 'transition-property:transform,box-shadow' in CSS
    assert 'prefers-reduced-motion' in CSS
    print('ZM_FX57_PATCH_SELFTEST=passed',flush=True)

if __name__=='__main__':
    if len(sys.argv)==2 and sys.argv[1]=='selftest':selftest()
    elif len(sys.argv)==3 and sys.argv[1] in ('apply','rollback'):
        (apply if sys.argv[1]=='apply' else rollback)(sys.argv[2])
    else:raise SystemExit('Usage: selftest | apply RUN_ID | rollback RUN_ID')
