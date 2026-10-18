#!/usr/bin/env python3
"""Read-only guarded inputs; append narrowly scoped CSS and wrap existing skip link in a landmark."""
from __future__ import annotations
import hashlib,json,os,pwd,re,sys,tempfile
from pathlib import Path
TARGET=Path('/home/zomorod2/public_html/company/index.html')
BACKUP=Path('/home/zomorod2/.backups/zomorod-company-a11y-css-20261018')
MARKER='zm-company-audit-fixes-20261018'
CSS=r'''<style id="zm-company-audit-fixes-20261018">
/* Company-page accessibility and mobile rendering improvements only. */
body.zm-unified-v7 #main a.zm-link:not(.zm-link-ghost),
body.zm-unified-v7 #main a.zm-link:not(.zm-link-ghost):is(:hover,:focus-visible){
  color:#17372a!important;text-shadow:none!important;
}
body.zm-unified-v7 #main a[href]{
  display:inline-flex;align-items:center;min-height:44px;
}
body.zm-unified-v7 .zm-v7-chain a{min-height:44px}
body.zm-unified-v7 #main a:focus-visible{
 outline:3px solid #ffecb6!important;outline-offset:3px;
}
.zm-company-skip-landmark{position:static;margin:0;padding:0}
@media(max-width:700px){
 body.zm-unified-v7 #main :is(.zm-card,.zm-article,.zm-history-card,.zm-section-head,.zm-history-topic>summary){
   -webkit-backdrop-filter:blur(2px) saturate(1.09);
   backdrop-filter:blur(2px) saturate(1.09);
   box-shadow:inset 0 2px 0 rgba(255,255,255,.82),
              inset 3px 0 0 rgba(215,255,239,.21),
              inset 0 -5px 0 rgba(0,11,23,.69),
              0 6px 0 -1px #072b30,
              0 13px 25px rgba(0,11,21,.48),
              0 0 13px rgba(255,212,121,.27)!important;
 }
 body.zm-unified-v7 #main :is(.zm-card-grid>.zm-card,.zm-article-grid>.zm-article){
  animation-duration:14s;
 }
}
@media(prefers-reduced-motion:reduce){
 body.zm-unified-v7 #main :is(.zm-card,.zm-article,.zm-history-card){animation:none!important;transition:none!important}
}
</style>'''
SKIP=b'<a class="zm-skip" href="#main">'
START=b'<nav aria-label="\xd9\xbe\xd8\xb1\xd8\xb4 \xd8\xa8\xd9\x87 \xd9\x85\xd8\xad\xd8\xaa\xd9\x88\xd8\xa7\xdb\x8c \xd8\xa7\xd8\xb5\xd9\x84\xdb\x8c" class="zm-company-skip-landmark">'
# Keep the existing skip-link completely unchanged. Only add a semantic wrapper.
def sha(x):return hashlib.sha256(x).hexdigest()
def p(run):
    if not re.fullmatch(r'[0-9]{1,20}',run):raise ValueError('Invalid run ID')
    return BACKUP/run
def guard():
    if pwd.getpwuid(os.getuid()).pw_name!='zomorod2':raise RuntimeError('Incorrect user')
    if not TARGET.is_file() or TARGET.is_symlink() or TARGET.parent.is_symlink() or BACKUP.is_symlink():raise RuntimeError('Unsafe path')
def patch(src):
    s=src.decode('utf-8')
    assert len(src)>40000 and s.count('</head>')==1 and s.count('</main>')==1 and s.count('</body>')==1
    for x in ('zm-company-cinematic-glass-20261018','zm-company-thick-glass-20261018','zm-history-company-content-20261018','zm-unified-v7-20261018','zm-section-head','zm-history-card'):
        if x not in s:raise RuntimeError('Missing protected marker '+x)
    if MARKER in s:raise RuntimeError('Already installed')
    skip=re.search(r'<a class="zm-skip" href="#main">[^<]+</a>',s)
    if not skip or s.count('<a class="zm-skip" href="#main">')!=1:raise RuntimeError('Unexpected original skip anchor')
    wrapped='<nav aria-label="پرش به محتوای اصلی" class="zm-company-skip-landmark">'+skip.group(0)+'</nav>'
    update=s.replace('</head>',CSS+'</head>',1)
    update=update.replace(skip.group(0),wrapped,1)
    stripped=update.replace(CSS,'',1).replace(wrapped,skip.group(0),1)
    if stripped!=s:raise RuntimeError('More than specified CSS and wrapper changed')
    assert update.count(MARKER)==1
    return update.encode('utf-8')
def atomic(dest,data,mode):
    tmp=None
    try:
        with tempfile.NamedTemporaryFile(dir=dest.parent,prefix='.zm-a11y-',delete=False) as f:
            tmp=Path(f.name);f.write(data);f.flush();os.fsync(f.fileno())
        os.chmod(tmp,mode);os.replace(tmp,dest)
    finally:
        if tmp and tmp.exists():tmp.unlink()
def check_original(old,new):
    a=old.decode();b=new.decode()
    skip=re.search(r'<a class="zm-skip" href="#main">[^<]+</a>',a).group(0)
    wrapper='<nav aria-label="پرش به محتوای اصلی" class="zm-company-skip-landmark">'+skip+'</nav>'
    return b.replace(CSS,'',1).replace(wrapper,skip,1)==a
def selftest():
    b=('<html><head></head><body class="zm-unified-v7"><a class="zm-skip" href="#main">رفتن به محتوای اصلی</a><main id="main"><div class="zm-section-head"><article class="zm-history-card"></article></div></main><!-- zm-company-cinematic-glass-20261018 --><!-- zm-company-thick-glass-20261018 --><!-- zm-history-company-content-20261018 --><!-- zm-unified-v7-20261018 --></body></html>'+'x'*42000).encode()
    new=patch(b)
    assert check_original(b,new)
    assert new.count(MARKER.encode())==1
    assert 'min-height:44px' in CSS and 'color:#17372a' in CSS and 'blur(2px)' in CSS
    print('A11Y_PATCH_SELFTEST=passed',flush=True)
def apply(run,expected):
    guard()
    if not re.fullmatch('[a-f0-9]{64}',expected):raise RuntimeError('Invalid SHA')
    old=TARGET.read_bytes()
    if sha(old)!=expected:raise RuntimeError('Concurrent edit before backup')
    new=patch(old);folder=p(run)
    if folder.exists() or folder.is_symlink():raise RuntimeError('Duplicate backup')
    folder.mkdir(parents=True,mode=0o700)
    mode=TARGET.stat().st_mode&0o777
    atomic(folder/'original.html',old,0o600)
    if sha((folder/'original.html').read_bytes())!=expected:raise RuntimeError('Backup failed')
    (folder/'manifest.json').write_text(json.dumps({'before':expected,'after':sha(new),'mode':mode}))
    if sha(TARGET.read_bytes())!=expected:raise RuntimeError('Concurrent edit after backup')
    atomic(TARGET,new,mode)
    if sha(TARGET.read_bytes())!=sha(new):raise RuntimeError('Write mismatch')
    print('A11Y_COMPANY_PATCH_INSTALLED=yes',flush=True)
def verify(run):
    guard();folder=p(run);m=json.loads((folder/'manifest.json').read_text())
    old=(folder/'original.html').read_bytes();now=TARGET.read_bytes()
    assert sha(old)==m['before'] and sha(now)==m['after'] and check_original(old,now)
    print('A11Y_COMPANY_PATCH_BYTE_EXACT_VERIFIED=yes',flush=True)
def rollback(run):
    guard();folder=p(run)
    if not (folder/'manifest.json').is_file():print('NO_INSTALL_TO_REVERT=yes');return
    m=json.loads((folder/'manifest.json').read_text());old=(folder/'original.html').read_bytes()
    if sha(old)!=m['before']:raise RuntimeError('Invalid backup')
    current=sha(TARGET.read_bytes())
    if current==m['before']:print('ALREADY_REVERTED=yes');return
    if current!=m['after']:raise RuntimeError('Concurrent edit; manual reconciliation required')
    atomic(TARGET,old,m['mode'])
    assert sha(TARGET.read_bytes())==m['before']
    print('COMPANY_A11Y_ROLLED_BACK=yes',flush=True)
if __name__=='__main__':
    if sys.argv[1:]==['selftest']:selftest()
    elif len(sys.argv)==4 and sys.argv[1]=='apply':apply(sys.argv[2],sys.argv[3])
    elif len(sys.argv)==3 and sys.argv[1]=='verify':verify(sys.argv[2])
    elif len(sys.argv)==3 and sys.argv[1]=='rollback':rollback(sys.argv[2])
    else:raise SystemExit('selftest | apply RUN SHA | verify RUN | rollback RUN')