#!/usr/bin/env python3
"""Company-page only: lossless CSS overlay with SHA-256 backup and rollback."""
from __future__ import annotations
import hashlib,json,os,pwd,re,sys,tempfile
from pathlib import Path
TARGET=Path('/home/zomorod2/public_html/company/index.html')
BACKUPS=Path('/home/zomorod2/.backups/zomorod-company-glass-20261018')
STYLE_ID='zm-company-cinematic-glass-20261018'
STYLE=r'''<style id="zm-company-cinematic-glass-20261018">
/* Scoped exclusively to the /company/ page; paint-only enhancements. */
body.zm-unified-v7 #main :is(.zm-card-grid,.zm-article-grid,.zm-history-list){perspective:1100px}
body.zm-unified-v7 #main :is(.zm-section-head,#zm-company-comprehensive > h2,.zm-history-topic > summary){
background:radial-gradient(ellipse 85% 105% at 8% -25%,rgba(243,255,244,.31),transparent 66%),linear-gradient(145deg,rgba(64,139,116,.58),rgba(14,58,54,.76) 49%,rgba(6,24,36,.84))!important;
border-color:rgba(255,228,161,.72)!important;
outline:1px solid rgba(247,246,218,.24);outline-offset:-3px;border-radius:18px!important;
box-shadow:inset 1px 1px 0 rgba(255,255,255,.49),inset -1px -1px 0 rgba(133,244,214,.23),0 10px 24px rgba(0,10,20,.35),0 24px 48px rgba(1,9,17,.24),0 0 19px rgba(237,207,131,.20)!important;
-webkit-backdrop-filter:blur(9px) saturate(1.22);backdrop-filter:blur(9px) saturate(1.22);
transform-style:preserve-3d;transition:box-shadow .32s ease,border-color .32s ease,translate .36s ease
}
body.zm-unified-v7 #main :is(.zm-section-head,#zm-company-comprehensive > h2,.zm-history-topic > summary):hover{
border-color:rgba(255,235,182,.95)!important;
box-shadow:inset 1px 1px 0 rgba(255,255,255,.60),0 16px 33px rgba(0,8,18,.40),0 27px 55px rgba(0,8,17,.25),0 0 23px rgba(249,215,139,.37)!important
}
body.zm-unified-v7 #main :is(.zm-card,.zm-article,.zm-history-card){
background:radial-gradient(ellipse 110% 60% at 8% -12%,rgba(243,255,241,.30),transparent 64%),linear-gradient(156deg,rgba(92,158,132,.32),rgba(27,88,79,.49) 34%,rgba(7,30,37,.81))!important;
border-color:rgba(244,221,162,.76)!important;outline:1px solid rgba(239,245,217,.27);outline-offset:-3px;
box-shadow:inset 1px 1px 0 rgba(255,255,255,.52),inset -1px -1px 0 rgba(135,237,207,.24),0 9px 20px rgba(0,8,17,.36),0 20px 39px rgba(0,9,19,.23),0 0 14px rgba(247,206,112,.19)!important;
-webkit-backdrop-filter:blur(9px) saturate(1.22);backdrop-filter:blur(9px) saturate(1.22);
transform-style:preserve-3d;backface-visibility:hidden;
transition:translate .32s ease,rotate .32s ease,box-shadow .32s ease,border-color .32s ease
}
body.zm-unified-v7 #main :is(.zm-card-grid > .zm-card,.zm-article-grid > .zm-article){animation:zm-company-card-float-20261018 8.7s ease-in-out infinite}
body.zm-unified-v7 #main :is(.zm-card-grid > .zm-card,.zm-article-grid > .zm-article):nth-child(3n+2){animation-delay:-3.1s;animation-duration:9.6s}
@keyframes zm-company-card-float-20261018{0%,100%{translate:0 0}50%{translate:0 -3px}}
@media(hover:hover) and (pointer:fine){
body.zm-unified-v7 #main :is(.zm-card,.zm-article,.zm-history-card):is(:hover,:focus-within){
animation-play-state:paused;translate:0 -5px;rotate:y -1.5deg;
border-color:rgba(255,240,191,.96)!important;
box-shadow:inset 1px 1px 0 rgba(255,255,255,.67),0 17px 34px rgba(0,8,17,.43),0 30px 51px rgba(0,8,19,.28),0 0 25px rgba(255,213,121,.48)!important
}}
@media(max-width:700px){
body.zm-unified-v7 #main :is(.zm-section-head,#zm-company-comprehensive > h2,.zm-history-topic > summary,.zm-card,.zm-article,.zm-history-card){
-webkit-backdrop-filter:blur(3px) saturate(1.12);backdrop-filter:blur(3px) saturate(1.12)}
body.zm-unified-v7 #main :is(.zm-card-grid > .zm-card,.zm-article-grid > .zm-article){animation-duration:12s}}
@media(prefers-reduced-motion:reduce){
body.zm-unified-v7 #main :is(.zm-card,.zm-article,.zm-history-card){animation:none!important;translate:none!important;rotate:none!important;transition:none!important}
body.zm-unified-v7 #main :is(.zm-section-head,#zm-company-comprehensive > h2,.zm-history-topic > summary){transition:none!important}
}
</style>'''
def sha(b): return hashlib.sha256(b).hexdigest()
def path(run):
    if not re.fullmatch(r'[0-9]{1,20}',run): raise RuntimeError('Invalid run ID')
    return BACKUPS/run
def guard():
    if pwd.getpwuid(os.getuid()).pw_name!='zomorod2':raise RuntimeError('Unexpected user')
    if not TARGET.is_file() or TARGET.is_symlink() or TARGET.parent.is_symlink() or BACKUPS.is_symlink():raise RuntimeError('Unsafe target')
def change(old):
    if len(old)<40000:raise RuntimeError('Suspiciously short company HTML')
    data=old.decode('utf-8')
    if STYLE_ID in data:raise RuntimeError('CSS already installed')
    for part in ('zm-unified-v7-20261018','zm-history-company-content-20261018','zm-history-topic','zm-history-card','zm-card-grid','zm-section-head','https://zomorodmelal.ir/company/'):
        if part not in data:raise RuntimeError('Unexpected HTML; missing '+part)
    if data.count('</head>')!=1 or data.count('</body>')!=1 or data.count('</main>')!=1:raise RuntimeError('Unexpected HTML skeleton')
    new=data.replace('</head>',STYLE+'</head>',1).encode('utf-8')
    if new.replace(STYLE.encode('utf-8'),b'',1)!=old:raise RuntimeError('Non-CSS edit detected')
    return new
def atomic(file,data,mode):
    tmp=None
    try:
        with tempfile.NamedTemporaryFile(dir=file.parent,prefix='.zm-company-glass-',delete=False) as f:
            tmp=Path(f.name);f.write(data);f.flush();os.fsync(f.fileno())
        os.chmod(tmp,mode);os.replace(tmp,file)
    finally:
        if tmp is not None and tmp.exists():tmp.unlink()
def selftest():
    b=('<html lang="fa"><head></head><body class="zm-unified-v7"><main id="main">'
       '<div class="zm-section-head"></div><div class="zm-card-grid"></div>'
       '<details class="zm-history-topic"><article class="zm-history-card"></article></details>'
       '</main><!-- zm-unified-v7-20261018 --><!-- zm-history-company-content-20261018 -->'
       '<a href="https://zomorodmelal.ir/company/">شرکت</a></body></html>'+'x'*41000).encode('utf-8')
    new=change(b)
    assert new.replace(STYLE.encode(),b'',1)==b
    assert new.count(STYLE_ID.encode())==1
    assert all(x in STYLE for x in ('zm-section-head','zm-history-topic > summary','zm-history-card','.zm-article','backdrop-filter','prefers-reduced-motion'))
    assert not re.search(r'(?<![-\w])(width|height|padding|margin|display|grid-template-columns|flex-basis|z-index)\s*:',STYLE)
    print('COMPANY_GLASS_SELFTEST=passed',flush=True)
def apply(run,expected):
    guard()
    if not re.fullmatch(r'[0-9a-f]{64}',expected):raise RuntimeError('Invalid SHA')
    old=TARGET.read_bytes()
    if sha(old)!=expected:raise RuntimeError('Concurrent edit detected')
    new=change(old);d=path(run)
    if d.exists() or d.is_symlink():raise RuntimeError('Backup exists')
    d.mkdir(parents=True,mode=0o700)
    mode=TARGET.stat().st_mode&0o777
    atomic(d/'company.before.html',old,0o600)
    if sha((d/'company.before.html').read_bytes())!=expected:raise RuntimeError('Backup invalid')
    manifest={'before':expected,'after':sha(new),'mode':mode}
    (d/'manifest.json').write_text(json.dumps(manifest),encoding='utf-8')
    if sha(TARGET.read_bytes())!=expected:raise RuntimeError('Concurrent company edit')
    atomic(TARGET,new,mode)
    if sha(TARGET.read_bytes())!=manifest['after']:raise RuntimeError('Post-install digest mismatch')
    print('COMPANY_GLASS_INSTALLED=yes',flush=True)
def verify(run):
    guard();d=path(run);m=json.loads((d/'manifest.json').read_text())
    old=(d/'company.before.html').read_bytes();now=TARGET.read_bytes()
    if sha(old)!=m['before'] or sha(now)!=m['after']:raise RuntimeError('Digest mismatch')
    if now.replace(STYLE.encode('utf-8'),b'',1)!=old:raise RuntimeError('Source not preserved')
    print('COMPANY_ONLY_CSS_AND_BACKUP_VERIFIED=yes',flush=True)
def rollback(run):
    guard();d=path(run)
    if not (d/'manifest.json').is_file():print('NO_INSTALL_TO_ROLL_BACK=yes');return
    m=json.loads((d/'manifest.json').read_text())
    old=(d/'company.before.html').read_bytes()
    if sha(old)!=m['before']:raise RuntimeError('Corrupted backup')
    current=sha(TARGET.read_bytes())
    if current==m['before']:print('ORIGINAL_ALREADY_PRESENT=yes');return
    if current!=m['after']:raise RuntimeError('Concurrent update; unsafe rollback')
    atomic(TARGET,old,m['mode'])
    if sha(TARGET.read_bytes())!=m['before']:raise RuntimeError('Rollback invalid')
    print('COMPANY_PAGE_ROLLED_BACK=yes',flush=True)
if __name__=='__main__':
    if sys.argv[1:]==['selftest']:selftest()
    elif len(sys.argv)==4 and sys.argv[1]=='apply':apply(sys.argv[2],sys.argv[3])
    elif len(sys.argv)==3 and sys.argv[1]=='verify':verify(sys.argv[2])
    elif len(sys.argv)==3 and sys.argv[1]=='rollback':rollback(sys.argv[2])
    else:raise SystemExit('selftest | apply RUN SHA | verify RUN | rollback RUN')