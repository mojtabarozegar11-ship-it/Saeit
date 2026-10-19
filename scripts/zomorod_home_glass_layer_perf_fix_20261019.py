#!/usr/bin/env python3
"""Surgical, rollback-safe homepage copy layering, graceful shelf reveal and H1 fix."""
from __future__ import annotations
import hashlib
import json
import os
import pwd
import re
import sys
import tempfile
from pathlib import Path

HOME=Path('/home/zomorod2/public_html/index.html')
BACKUPS=Path('/home/zomorod2/.backups/zm-home-layer-perf-20261019')
STYLE_ID='zm-home-layer-perf-fix-20261019'
SCRIPT_ID='zm-home-shelf-reveal-20261019'
H1='<h1 id="detail-title" tabindex="-1"></h1>'
H2='<h2 id="detail-title" tabindex="-1"></h2>'
STYLE=r'''<style id="zm-home-layer-perf-fix-20261019">
/* Explicit painting order: glass reflection below ALL textual content. */
body #main-view > .hero .hero-text,
body #main-view > .orbit-intro,
body .orbit-shelf > .shelf-explanation,
body #zm-official-contacts-20261019,
body #site-footer .footer-shell.wrap {
  position:relative;
  isolation:isolate;
  box-sizing:border-box;
  overflow:visible;
}
body #main-view > .hero .hero-text::before,
body #main-view > .orbit-intro::before,
body #zm-official-contacts-20261019::before {
  z-index:0 !important;
  pointer-events:none !important;
}
body #main-view > .hero .hero-text > *,
body #main-view > .orbit-intro > *,
body .orbit-shelf > .shelf-explanation > *,
body #zm-official-contacts-20261019 > *,
body #site-footer .footer-shell.wrap > * {
  position:relative;
  z-index:2;
}
body .orbit-shelf > .shelf-explanation::before,
body .orbit-shelf > .shelf-explanation::after {
  pointer-events:none !important;
  z-index:0 !important;
}
body .orbit-shelf > .shelf-explanation {
  height:auto !important;
  min-height:max-content;
  padding-top:clamp(14px,1.5vw,23px);
  padding-bottom:clamp(14px,1.5vw,23px);
}
body .orbit-shelf > .shelf-explanation .shelf-heading-line,
body .orbit-shelf > .shelf-explanation h3,
body .orbit-shelf > .shelf-explanation > p {
  position:relative;
  z-index:2;
  overflow-wrap:break-word;
  line-height:1.72;
}
body #main-view > .hero .hero-text,
body #main-view > .orbit-intro,
body #zm-official-contacts-20261019,
body #site-footer .footer-shell.wrap {
  height:auto !important;
}
body #zm-official-contacts-20261019 .zm-contact-grid,
body #zm-official-contacts-20261019 .zm-contact-heading,
body #zm-official-contacts-20261019 .zm-contact-footnote,
body #zm-official-contacts-20261019 .zm-contact-card > *,
body #site-footer .footer-grid > *,
body #site-footer .footer-grid > * > *,
body #site-footer .footer-copyright,
body header.topbar.wrap > * {
  position:relative;
  z-index:2;
}
body #zm-official-contacts-20261019 .zm-contact-card,
body #site-footer .footer-grid > * {
  height:auto;
  min-height:min-content;
  overflow:visible;
}
body #site-footer .footer-intro,
body #site-footer .footer-copyright,
body #zm-official-contacts-20261019 p,
body #zm-official-contacts-20261019 h2,
body #zm-official-contacts-20261019 h3 {
  overflow-wrap:break-word;
  line-height:1.8;
}
body #zm-official-contacts-20261019 .zm-contact-grid > *,
body #site-footer .footer-grid > * {min-width:0;}
/* The hidden detail view uses a secondary heading; preserve title prominence. */
body #detail-title {
  font-size:clamp(2.1rem,5.2vw,5.5rem);
  line-height:1.24;
  font-weight:800;
}
/* Paint efficiency: suspend only OFFSCREEN decorative animations.
   Keep every row/card present, clickable, measurable and unhidden. */
body .orbit-shelf.zm-shelf-idle .topic-card,
body .orbit-shelf.zm-shelf-idle .topic-card::before,
body .orbit-shelf.zm-shelf-idle .topic-card::after {
  animation-play-state:paused !important;
}
@media(max-width:700px){
  body .orbit-shelf > .shelf-explanation {
    padding-top:14px;
    padding-bottom:14px;
  }
  body .orbit-shelf > .shelf-explanation > p {
    line-height:1.85;
  }
  body #zm-official-contacts-20261019 .zm-contact-grid > *,
  body #site-footer .footer-grid > * {
    padding-bottom:18px;
  }
}
@media(prefers-reduced-motion:reduce){
  body .orbit-shelf .topic-card {
    animation-duration:0.01ms !important;
    animation-iteration-count:1 !important;
  }
}
</style>
'''
SCRIPT=r'''<script id="zm-home-shelf-reveal-20261019">
/* Repair race with lazy appearance: leave no shelf hidden if a scroll observer
   misses it. Reduce render cost by pausing animation in far offscreen shelves. */
(function(){
  "use strict";
  var known=new WeakSet();
  var io=('IntersectionObserver' in window)?new IntersectionObserver(function(entries){
    for(var i=0;i<entries.length;i++){
      var e=entries[i],row=e.target;
      row.classList.toggle('zm-shelf-idle',!e.isIntersecting);
      if(e.isIntersecting)row.classList.remove('zm-home-shelf-offscreen');
    }
  },{rootMargin:'850px 0px 850px 0px',threshold:0}):null;
  function inspect(){
    var shelves=document.querySelectorAll('#orbit-shelves .orbit-shelf');
    for(var i=0;i<shelves.length;i++){
      var row=shelves[i];
      // Reveal without destroying original content, cards, transforms or rails.
      row.classList.remove('zm-home-shelf-offscreen');
      if(io&&!known.has(row)){
        known.add(row);io.observe(row);
      }
    }
    var cards=document.querySelectorAll('#orbit-shelves .topic-card img');
    for(var j=0;j<cards.length;j++){
      var img=cards[j];
      if(j>5&&!img.hasAttribute('loading'))img.setAttribute('loading','lazy');
      if(!img.hasAttribute('decoding'))img.setAttribute('decoding','async');
    }
  }
  function start(){
    if(window.requestAnimationFrame)requestAnimationFrame(inspect);
    else inspect();
    // Fall back if earlier page code injects shelves in a later task.
    window.setTimeout(inspect,200);
    window.setTimeout(inspect,900);
    window.setTimeout(inspect,2100);
  }
  if(document.readyState==='loading'){
    document.addEventListener('DOMContentLoaded',start,{once:true});
  }else start();
})();
</script>
'''

def digest(content:bytes)->str:return hashlib.sha256(content).hexdigest()

def transform(data:bytes)->bytes:
    text=data.decode('utf-8')
    required=[
        'id="zm-home-copy-cinematic-glass-20261019"',
        'id="zm-home-header-footer-glass-20261019"',
        'id="zm-official-contacts-20261019"',
        'id="zm-glass-row-headers-20261018"',
        'id="zm-fixed-scientific-background-20261018"',
        'id="main-view"','id="orbit-shelves"','id="site-footer"',
        'id="solar-stage"','id="orbital-cards"',
        'ZOMOROD_ORBIT_DATA','.topic-card','.card-track'
    ]
    if len(data)<1500000 or text.count('</head>')!=1 or text.count('</body>')!=1:
        raise RuntimeError('Unexpected homepage structure')
    if text.count(H1)!=1 or text.count(H2)!=0:
        raise RuntimeError('Hidden detail heading changed, refuse untested edit')
    if STYLE_ID in text or SCRIPT_ID in text:
        raise RuntimeError('Homepage fix installed already')
    for marker in required:
        if marker not in text:raise RuntimeError('Missing protected content: '+marker)
    new=text.replace(H1,H2,1).replace('</head>',STYLE+'</head>',1).replace('</body>',SCRIPT+'</body>',1).encode()
    if new.replace(STYLE.encode(),b'',1).replace(SCRIPT.encode(),b'',1).replace(H2.encode(),H1.encode(),1)!=data:
        raise RuntimeError('Original homepage content modified')
    return new

def path_for(run):
    if not re.fullmatch('[0-9]{1,20}',run):raise RuntimeError('Invalid GitHub run id')
    return BACKUPS/run

def safe():
    if pwd.getpwuid(os.getuid()).pw_name!='zomorod2':raise RuntimeError('Unsafe user')
    if not HOME.is_file() or HOME.is_symlink() or HOME.parent.is_symlink() or BACKUPS.is_symlink():
        raise RuntimeError('Unsafe production or backup path')

def atomic(path,data,mode):
    tmp=None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent,delete=False,prefix='.zm-home-perf-') as f:
            tmp=Path(f.name);f.write(data);f.flush();os.fsync(f.fileno())
        os.chmod(tmp,mode);os.replace(tmp,path)
    finally:
        if tmp is not None and tmp.exists():tmp.unlink()

def selftest():
    data=('<html><head></head><body>'
     '<main id="main-view"><div id="solar-stage"></div>'
     '<div id="orbital-cards"></div><div id="orbit-shelves"></div></main>'
     '<footer id="site-footer"></footer>'
     +H1+
     '<style>.topic-card{}.card-track{}</style>'
     '<script>ZOMOROD_ORBIT_DATA</script>'
     '<style id="zm-home-copy-cinematic-glass-20261019"></style>'
     '<style id="zm-home-header-footer-glass-20261019"></style>'
     '<section id="zm-official-contacts-20261019"></section>'
     '<style id="zm-glass-row-headers-20261018"></style>'
     '<style id="zm-fixed-scientific-background-20261018"></style>'
     '</body></html>'+'x'*1600000).encode()
    updated=transform(data)
    assert updated.count(STYLE_ID.encode())==1
    assert updated.count(SCRIPT_ID.encode())==1
    assert updated.count(H2.encode())==1 and updated.count(H1.encode())==0
    assert updated.replace(STYLE.encode(),b'',1).replace(SCRIPT.encode(),b'',1).replace(H2.encode(),H1.encode(),1)==data
    for x in ('shelf-explanation','.hero-text','footer-copyright',
              '.zm-contact-card','zm-shelf-idle','z-index:2','pointer-events:none'):
        assert x in STYLE,x
    assert 'zm-home-shelf-offscreen' in SCRIPT and 'IntersectionObserver' in SCRIPT
    print('ZM_HOME_LAYER_PERF_SELFTEST=passed',flush=True)

def apply(run,sha):
    safe()
    if not re.fullmatch('[a-f0-9]{64}',sha):raise RuntimeError('Bad SHA')
    before=HOME.read_bytes()
    if digest(before)!=sha:raise RuntimeError('Concurrent homepage update detected')
    after=transform(before)
    location=path_for(run)
    if location.exists() or location.is_symlink():raise RuntimeError('Backup exists')
    location.mkdir(mode=0o700,parents=True)
    mode=HOME.stat().st_mode & 0o777
    atomic(location/'index.before.html',before,0o600)
    if digest((location/'index.before.html').read_bytes())!=sha:raise RuntimeError('Backup mismatch')
    (location/'manifest.json').write_text(json.dumps({'before':sha,'after':digest(after),'mode':mode}),encoding='utf-8')
    if digest(HOME.read_bytes())!=sha:raise RuntimeError('Concurrent homepage edit')
    atomic(HOME,after,mode)
    if digest(HOME.read_bytes())!=digest(after):raise RuntimeError('Installation mismatch')
    print('ZM_HOME_LAYER_PERF_INSTALLED=yes',flush=True)

def verify(run):
    safe()
    loc=path_for(run);m=json.loads((loc/'manifest.json').read_text())
    before=(loc/'index.before.html').read_bytes()
    after=HOME.read_bytes()
    if digest(before)!=m['before'] or digest(after)!=m['after']:
        raise RuntimeError('Checksum changed')
    if after.replace(STYLE.encode(),b'',1).replace(SCRIPT.encode(),b'',1).replace(H2.encode(),H1.encode(),1)!=before:
        raise RuntimeError('Site content mismatch')
    print('ZM_HOME_LAYER_PERF_CONTENT_PRESERVED=yes',flush=True)

def rollback(run):
    safe()
    loc=path_for(run)
    if not (loc/'manifest.json').is_file():
        print('ZM_HOME_LAYER_PERF_NO_INSTALL=yes',flush=True);return
    m=json.loads((loc/'manifest.json').read_text())
    before=(loc/'index.before.html').read_bytes()
    if digest(before)!=m['before']:raise RuntimeError('Backup checksum changed')
    actual=digest(HOME.read_bytes())
    if actual==m['before']:return
    if actual!=m['after']:raise RuntimeError('Page changed, safe rollback rejected')
    atomic(HOME,before,m['mode'])
    assert digest(HOME.read_bytes())==m['before']
    print('ZM_HOME_LAYER_PERF_ROLLBACK=yes',flush=True)

if __name__=='__main__':
    if sys.argv[1:]==['selftest']:selftest()
    elif len(sys.argv)==4 and sys.argv[1]=='apply':apply(sys.argv[2],sys.argv[3])
    elif len(sys.argv)==3 and sys.argv[1]=='verify':verify(sys.argv[2])
    elif len(sys.argv)==3 and sys.argv[1]=='rollback':rollback(sys.argv[2])
    else:raise SystemExit('selftest | apply RUN SHA | verify RUN | rollback RUN')
