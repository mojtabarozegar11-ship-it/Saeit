#!/usr/bin/env python3
"""Four additive CSS-only homepage embellishments: ring, star, card, icon.

NEVER modify child-sites, Django/Passenger, JS, routes, layout HTML or data.
Only appends one isolated <style> tag in exact verified root index.html.
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

ROOT=Path('/home/zomorod2/public_html')
TARGET=ROOT/'index.html'
BACKUP_ROOT=Path('/home/zomorod2/.backups/zomorod-four-visual-fx-20261018')
EXPECTED_SHA='67d1253f53960cc324d3c18e93dde3f1717d7b1e794d4091527472380c539723'
STYLE_ID='zm-four-premium-fx-css-20261018'

STYLE=r"""
<style id="zm-four-premium-fx-css-20261018">
/* Scoped homepage-only, purely presentational, zero HTML/data modifications.
   FX 1: fine additional luminous rings; original 3 opposing orbital motions remain intact. */
#solar-stage .central-globe .globe-ring{pointer-events:none}
#solar-stage .central-globe .globe-ring.ring-one::before,
#solar-stage .central-globe .globe-ring.ring-three::after {
  content:"";position:absolute;display:block;pointer-events:none;
  left:4%;right:4%;top:9%;bottom:9%;border-radius:50%;
  border:1px solid rgba(255,222,138,.69);
  box-shadow:0 0 8px rgba(246,208,105,.35),inset 0 0 7px rgba(236,190,79,.18);
  transform-origin:50% 50%;
  animation:zm-fx4-orbit-add-20261018 19s ease-in-out infinite alternate;
}
#solar-stage .central-globe .globe-ring.ring-three::after{
  border-color:rgba(244,204,110,.58);
  box-shadow:0 0 12px rgba(250,207,100,.31);
  animation-direction:alternate-reverse;animation-duration:29s;
}
@keyframes zm-fx4-orbit-add-20261018{
  0%{transform:rotate(-20deg) scale(1,.91);opacity:.51}
  50%{transform:rotate(8deg) scale(1.03,1.05);opacity:.85}
  100%{transform:rotate(28deg) scale(1,.91);opacity:.58}
}
/* FX 2: sparse, light, non-interactive star layers; original stars remain untouched. */
#solar-stage .orbital-stars::before,
#solar-stage .orbital-stars::after{
  content:"";position:absolute;inset:12% 7%;display:block;pointer-events:none;
  border-radius:50%;opacity:.48;
  background-image:
    radial-gradient(circle at 11% 13%,rgba(255,226,153,.85) 0 1.2px,transparent 2.6px),
    radial-gradient(circle at 88% 19%,rgba(255,219,139,.72) 0 1px,transparent 2.2px),
    radial-gradient(circle at 23% 74%,rgba(255,228,157,.78) 0 1px,transparent 2.6px),
    radial-gradient(circle at 77% 64%,rgba(255,219,138,.88) 0 1.3px,transparent 2.8px),
    radial-gradient(circle at 53% 6%,rgba(244,221,153,.62) 0 .9px,transparent 2.5px),
    radial-gradient(circle at 62% 91%,rgba(244,226,163,.67) 0 1.1px,transparent 2.5px);
  animation:zm-fx4-stardust-20261018 13s ease-in-out infinite alternate;
}
#solar-stage .orbital-stars::after{
  inset:16% 13%;opacity:.33;filter:blur(.35px);
  transform:translate3d(3px,-2px,0);
  animation-duration:19s;animation-direction:alternate-reverse;
}
@keyframes zm-fx4-stardust-20261018{
  from{transform:translate3d(-5px,3px,0);opacity:.24}
  to{transform:translate3d(6px,-6px,0);opacity:.59}
}
/* FX 3: crisp luminous card perimeter without changing card size, position or transform. */
#orbital-cards .topic-card,
#content .detail-card{
  outline:1px solid rgba(255,221,143,.28);
  outline-offset:-1px;
  transition-property:box-shadow,outline-color,filter;
  transition-duration:.25s;
  transition-timing-function:ease-out;
}
#orbital-cards .topic-card:is(:hover,:focus-visible,:focus-within),
#content .detail-card:is(:hover,:focus-within){
  outline-color:rgba(255,232,171,.76);
  box-shadow:0 0 0 1px rgba(243,198,96,.22),0 0 21px rgba(240,194,99,.19),
    inset 0 0 16px rgba(251,218,149,.055);
}
/* FX 4: gold-depth treatment on existing icons, never replaces icons or buttons. */
.header-orbit a > span,
.hero-values b,
#zm-gold-search-toolbar-20261018 .zm-topics-gold-icon svg{
  color:#ffe1a0;
  text-shadow:0 1px 0 #75551c,0 2px 2px rgba(4,14,8,.8),
    0 0 11px rgba(244,199,111,.43);
  filter:drop-shadow(0 2px 1px rgba(0,0,0,.38));
}
.header-orbit a:is(:hover,:focus-visible) > span,
#zm-gold-search-toolbar-20261018 .zm-topics-gold-icon:is(:hover,:focus-visible) svg{
  color:#fff0c4;
  text-shadow:0 1px 0 #926a29,0 2px 2px rgba(7,18,8,.8),
    0 0 16px rgba(255,223,144,.78);
}
/* Preserve user's motion toggle and accessibility choices. */
.motion-paused #solar-stage .globe-ring.ring-one::before,
.motion-paused #solar-stage .globe-ring.ring-three::after,
.motion-paused #solar-stage .orbital-stars::before,
.motion-paused #solar-stage .orbital-stars::after {
  animation-play-state:paused!important;
}
@media (max-width:600px){
  #solar-stage .orbital-stars::before{opacity:.28;animation-duration:24s}
  #solar-stage .orbital-stars::after{display:none}
  #orbital-cards .topic-card {outline-color:rgba(246,209,131,.23)}
}
@media (prefers-reduced-motion:reduce){
  #solar-stage .globe-ring.ring-one::before,
  #solar-stage .globe-ring.ring-three::after,
  #solar-stage .orbital-stars::before,
  #solar-stage .orbital-stars::after {animation:none!important;transform:none!important}
  #orbital-cards .topic-card,
  #content .detail-card {transition:none!important}
}
</style>
"""

def digest(payload:bytes)->str:
    return hashlib.sha256(payload).hexdigest()

def backup_path(run:str)->Path:
    if not re.fullmatch(r'[0-9]{1,20}',run):
        raise RuntimeError('Invalid Run ID')
    return BACKUP_ROOT/run

def safety():
    if pwd.getpwuid(os.getuid()).pw_name!='zomorod2':
        raise RuntimeError('Unexpected hosting user')
    for path in (ROOT,TARGET):
        if not path.exists() or path.is_symlink():
            raise RuntimeError('Unsafe hosting path')
    if not TARGET.is_file():
        raise RuntimeError('Not the HTML homepage')

def transform(source:str)->str:
    if 'id="'+STYLE_ID+'"' in source:
        raise RuntimeError('FX4 already present')
    required=(
      '<header class="topbar wrap"','<div class="solar-area">',
      '<div class="globe-ring ring-one"></div>',
      '<div class="globe-ring ring-two"></div>',
      '<div class="globe-ring ring-three"></div>',
      'class="orbital-stars"',
      'class="orbital-cards"',
      'id="orbital-cards"',
      'id="zm-topics-top-icon-20261018"',
      'id="zm-gold-search-toolbar-20261018"',
      '<footer class="footer" id="site-footer"',
      'ZOMOROD_ORBIT_DATA','<main id="content">'
    )
    for marker in required:
        if source.count(marker)!=1:
            raise RuntimeError('Original page feature missing or duplicated: '+marker)
    if source.count('</head>')!=1 or source.count('</body>')!=1 or len(source)<2200000:
        raise RuntimeError('Unexpected homepage or head')
    if not (source.index('</head>')<source.index('<header class="topbar wrap"')<source.index('<main id="content">')<source.index('<footer class="footer" id="site-footer"')):
        raise RuntimeError('Original page hierarchy changed')
    next_source=source.replace('</head>',STYLE+'</head>',1)
    if next_source.replace(STYLE,'',1)!=source:
        raise RuntimeError('Unrelated original HTML data altered')
    if next_source.count('id="'+STYLE_ID+'"')!=1:
        raise RuntimeError('Duplicate FX4 style')
    if next_source.count('href="/topics/"')!=source.count('href="/topics/"'):
        raise RuntimeError('Navigation changed')
    if next_source.count('action="/search/"')!=source.count('action="/search/"'):
        raise RuntimeError('Search changed')
    return next_source

def atomic(target:Path,payload:bytes,mode:int):
    temp=None
    try:
        with tempfile.NamedTemporaryFile(mode='wb',prefix='.zm-fx4-',dir=target.parent,delete=False) as fd:
            temp=Path(fd.name);fd.write(payload);fd.flush();os.fsync(fd.fileno())
        os.chmod(temp,mode)
        os.replace(temp,target)
    finally:
        if temp and temp.exists():temp.unlink()

def install(run:str):
    safety()
    before=TARGET.read_bytes()
    if digest(before)!=EXPECTED_SHA:
        raise RuntimeError('Live root SHA changed; refuse overwritten update')
    updated=transform(before.decode('utf8')).encode('utf8')
    backup=backup_path(run)
    if backup.exists() or backup.is_symlink():
        raise RuntimeError('Backup already exists')
    backup.mkdir(parents=True,mode=0o700)
    mode=TARGET.stat().st_mode&0o777
    shutil.copy2(TARGET,backup/'index.original.html')
    if digest((backup/'index.original.html').read_bytes())!=EXPECTED_SHA:
        raise RuntimeError('Original backup hash mismatch')
    manifest={'before':EXPECTED_SHA,'after':digest(updated),'mode':mode}
    (backup/'manifest.json').write_text(json.dumps(manifest))
    atomic(TARGET,updated,mode)
    if digest(TARGET.read_bytes())!=manifest['after']:
        raise RuntimeError('FX4 write checksum failed')
    print('ZM_FX4_PUBLISHED=yes',flush=True)
    print('ZM_FX4_NEW_SHA='+manifest['after'],flush=True)
    print('ZM_FX4_BACKUP_VERIFIED=yes',flush=True)
    print('ZM_FX4_ONLY_INLINE_CSS=yes',flush=True)

def rollback(run:str):
    safety()
    backup=backup_path(run)
    if backup.is_symlink():
        raise RuntimeError('Unsafe backup dir')
    manifest=json.loads((backup/'manifest.json').read_text())
    before=(backup/'index.original.html').read_bytes()
    if digest(before)!=manifest['before']:
        raise RuntimeError('Corrupt backup')
    if digest(TARGET.read_bytes()) not in (manifest['before'],manifest['after']):
        raise RuntimeError('Unexpected concurrent edit')
    atomic(TARGET,before,manifest['mode'])
    if digest(TARGET.read_bytes())!=manifest['before']:
        raise RuntimeError('Unable to verify rollback')
    print('ZM_FX4_ROLLBACK_OK=yes',flush=True)

def selftest():
    sample=('<html><head></head><body>'
      '<header class="topbar wrap">Test</header>'
      '<div class="solar-area"><div class="globe-ring ring-one"></div>'
      '<div class="globe-ring ring-two"></div>'
      '<div class="globe-ring ring-three"></div>'
      '<div aria-hidden="true" class="orbital-stars"></div>'
      '<div class="orbital-cards" id="orbital-cards"></div></div>'
      '<section id="zm-gold-search-toolbar-20261018">'
      '<a id="zm-topics-top-icon-20261018" href="/topics/">Book</a></section>'
      '<main id="content"><form action="/search/"></form></main>'
      '<footer class="footer" id="site-footer">Legal</footer>'
      '<script>ZOMOROD_ORBIT_DATA</script></body></html>')
    sample += 'X'*2200000
    result=transform(sample)
    assert result.count('id="'+STYLE_ID+'"')==1
    assert result.replace(STYLE,'',1)==sample
    assert all(x in STYLE for x in ('FX 1','FX 2','FX 3','FX 4','prefers-reduced-motion','motion-paused'))
    print('ZM_FX4_LOCAL_SELFTEST=passed')

if __name__=='__main__':
    if len(sys.argv)==2 and sys.argv[1]=='selftest':
        selftest()
    elif len(sys.argv)==3 and sys.argv[1] in ('install','rollback'):
        (install if sys.argv[1]=='install' else rollback)(sys.argv[2])
    else:
        raise SystemExit('Usage: selftest | install RUN_ID | rollback RUN_ID')
