#!/usr/bin/env python3
"""Add only homepage scoped repairs with exact original SHA backup and verified rollback."""
from __future__ import annotations
import hashlib,json,os,pwd,re,sys,tempfile
from pathlib import Path
TARGET=Path('/home/zomorod2/public_html/index.html')
BACKUPS=Path('/home/zomorod2/.backups/zomorod-home-template-fixes-20261018')
ID='zm-home-template-repairs-20261018'
CSS=r'''<style id="zm-home-template-repairs-20261018">
/* Scoped to live Zomorod homepage. Keep autonomous card tracks and 3D visuals intact. */
/* Clip ONLY cross-axis visual spill, including over-wide ambient lighting. */
html body:has(#orbital-cards) #content {
  overflow-x:clip;
  overflow-y:visible;
}
/* Telephone needs a non-color-only affordance against adjoining gold text. */
html body:has(#orbital-cards) a[href^="tel:"] {
  text-decoration:underline solid 2px currentColor !important;
  text-underline-offset:4px;
  text-decoration-skip-ink:auto;
}
html body:has(#orbital-cards) a[href^="tel:"]:focus-visible {
  outline:3px solid #fff0c5;
  outline-offset:3px;
}
/* Reduce compositor work far outside viewport without pausing visible rows. */
@media(prefers-reduced-motion:no-preference) {
  html body:has(#orbital-cards) .orbit-shelf.zm-home-shelf-offscreen :is(.card-track,.topic-card) {
    animation-play-state:paused!important;
  }
}
@media(prefers-reduced-motion:reduce) {
  html body:has(#orbital-cards) .orbit-shelf :is(.card-track,.topic-card) {
    animation:none!important;
    transition:none!important;
  }
}
</style>'''
JS=r'''<script id="zm-home-template-repairs-runtime-20261018">
/* No data, images or HTML edits. Track only in-view shelf motion. */
(()=>{'use strict';
 const start=()=>{
  const shelves=document.querySelectorAll('#orbital-cards .orbit-shelf');
  if(shelves.length!==29 || !('IntersectionObserver' in window)) return;
  const observer=new IntersectionObserver(entries=>{
   for(const entry of entries)entry.target.classList.toggle('zm-home-shelf-offscreen',!entry.isIntersecting);
  },{root:null,rootMargin:'700px 0px 700px 0px',threshold:0});
  shelves.forEach(el=>observer.observe(el));
  window.addEventListener('pagehide',()=>observer.disconnect(),{once:true});
 };
 if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',start,{once:true});
 else start();
})();
</script>'''
def digest(data):return hashlib.sha256(data).hexdigest()
def folder(run):
    if not re.fullmatch(r'[0-9]{1,20}',run):raise RuntimeError('Invalid run id')
    return BACKUPS/run
def safety():
    if pwd.getpwuid(os.getuid()).pw_name!='zomorod2':raise RuntimeError('Unexpected account')
    if not TARGET.is_file() or TARGET.is_symlink() or TARGET.parent.is_symlink() or BACKUPS.is_symlink():
        raise RuntimeError('Unsafe homepage path')
def transform(old):
    s=old.decode('utf-8')
    if len(old)<1500000 or s.count('</head>')!=1 or s.count('</body>')!=1:raise RuntimeError('Unexpected homepage structure')
    if ID in s:raise RuntimeError('Already patched')
    for tag in (
       'id="zm-fixed-scientific-background-20261018"',
       'id="zm-glass-floating-cards-20261018"',
       'id="zm-glass-row-headers-20261018"',
       'id="orbital-cards"','id="solar-stage"','id="site-footer"',
       'id="content"','id="hero-title"','id="detail-title"',
       'stage-ambient','topic-card','card-track','orbit-shelf',
       'ZOMOROD_ORBIT_DATA','tel:+989022048691'
    ):
        if tag not in s:raise RuntimeError('Feature marker missing '+tag)
    n=s.replace('</head>',CSS+'</head>',1).replace('</body>',JS+'</body>',1)
    if n.replace(CSS,'',1).replace(JS,'',1)!=s:raise RuntimeError('Underlying source changed')
    return n.encode('utf-8')
def atomic(path,bytes_,mode):
    tmp=None
    try:
      with tempfile.NamedTemporaryFile(dir=path.parent,prefix='.zm-home-fixed-',delete=False) as f:
        tmp=Path(f.name);f.write(bytes_);f.flush();os.fsync(f.fileno())
      os.chmod(tmp,mode);os.replace(tmp,path)
    finally:
      if tmp and tmp.exists():tmp.unlink()
def selftest():
    orig=('<html><head></head><body><main id="content"><div id="solar-stage" class="stage-ambient"></div><div id="orbital-cards"><div class="orbit-shelf"><div class="card-track"><a class="topic-card"></a></div></div></div><h1 id="hero-title"></h1><h1 id="detail-title"></h1></main><footer id="site-footer"><a href="tel:+989022048691"></a></footer>'
      '<script>ZOMOROD_ORBIT_DATA</script><style id="zm-fixed-scientific-background-20261018"></style><style id="zm-glass-floating-cards-20261018"></style><style id="zm-glass-row-headers-20261018"></style></body></html>'+'z'*1550000).encode()
    new=transform(orig)
    assert new.replace(CSS.encode(),b'',1).replace(JS.encode(),b'',1)==orig
    assert 'overflow-x:clip' in CSS and 'text-decoration:underline' in CSS
    assert 'IntersectionObserver' in JS and 'rootMargin' in JS and 'shelves.length!==29' in JS
    assert not re.search(r'(?:width|height|padding|margin|grid-template-columns|display)\s*:',CSS)
    print('ROOT_TEMPLATE_PATCH_SELFTEST_PASS=yes',flush=True)
def apply(run,expected):
    safety()
    if not re.fullmatch('[0-9a-f]{64}',expected):raise RuntimeError('Bad original sha')
    old=TARGET.read_bytes()
    if digest(old)!=expected:raise RuntimeError('Concurrent edit')
    new=transform(old)
    out=folder(run)
    if out.exists() or out.is_symlink():raise RuntimeError('Backup exists')
    out.mkdir(parents=True,mode=0o700)
    mode=TARGET.stat().st_mode&0o777
    atomic(out/'index.before.html',old,0o600)
    if digest((out/'index.before.html').read_bytes())!=expected:raise RuntimeError('Backup failed')
    (out/'manifest.json').write_text(json.dumps({'before':expected,'after':digest(new),'mode':mode}),encoding='utf-8')
    if digest(TARGET.read_bytes())!=expected:raise RuntimeError('Concurrent edit after backup')
    atomic(TARGET,new,mode)
    if digest(TARGET.read_bytes())!=digest(new):raise RuntimeError('Invalid live write')
    print('ROOT_TEMPLATE_PATCH_INSTALLED=yes',flush=True)
def verify(run):
    safety()
    out=folder(run);m=json.loads((out/'manifest.json').read_text())
    old=(out/'index.before.html').read_bytes();now=TARGET.read_bytes()
    if digest(old)!=m['before'] or digest(now)!=m['after']:raise RuntimeError('Digest mismatch')
    if now.replace(CSS.encode(),b'',1).replace(JS.encode(),b'',1)!=old:raise RuntimeError('Original page changed')
    print('ROOT_TEMPLATE_ORIGINAL_BYTE_IDENTICAL=yes',flush=True)
def rollback(run):
    safety()
    out=folder(run)
    if not (out/'manifest.json').is_file():print('NO_PATCH_TO_ROLLBACK=yes');return
    m=json.loads((out/'manifest.json').read_text())
    old=(out/'index.before.html').read_bytes()
    if digest(old)!=m['before']:raise RuntimeError('Corrupt backup')
    now=digest(TARGET.read_bytes())
    if now==m['before']:print('ALREADY_ROLLED_BACK=yes');return
    if now!=m['after']:raise RuntimeError('Concurrent edits; do not overwrite')
    atomic(TARGET,old,m['mode'])
    if digest(TARGET.read_bytes())!=m['before']:raise RuntimeError('Rollback failed')
    print('ROOT_TEMPLATE_PATCH_ROLLED_BACK=yes',flush=True)
if __name__=='__main__':
    if sys.argv[1:]==['selftest']:selftest()
    elif len(sys.argv)==4 and sys.argv[1]=='apply':apply(sys.argv[2],sys.argv[3])
    elif len(sys.argv)==3 and sys.argv[1]=='verify':verify(sys.argv[2])
    elif len(sys.argv)==3 and sys.argv[1]=='rollback':rollback(sys.argv[2])
    else:raise SystemExit('selftest | apply RUN SHA | verify RUN | rollback RUN')