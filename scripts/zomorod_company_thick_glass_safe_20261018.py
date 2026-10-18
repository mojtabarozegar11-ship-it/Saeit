#!/usr/bin/env python3
"""Add a reversible, company-only thick-glass CSS layer without editing markup."""
import hashlib,json,os,pwd,re,sys,tempfile
from pathlib import Path
HOME=Path('/home/zomorod2/public_html/company/index.html')
BACKUP=Path('/home/zomorod2/.backups/zomorod-thick-company-glass-20261018')
MARKER='zm-company-thick-glass-20261018'
STYLE=r'''<style id="zm-company-thick-glass-20261018">
/* Bevelled thick glass and cinematic light; only company page cards and row headers. */
body.zm-unified-v7 #main :is(.zm-section-head,#zm-company-comprehensive>h2,.zm-history-topic>summary){
background:radial-gradient(ellipse at 10% -15%,rgba(255,255,244,.42),transparent 65%),linear-gradient(145deg,rgba(90,182,147,.55),rgba(12,62,61,.78) 55%,rgba(3,23,36,.88))!important;
border-color:rgba(255,229,158,.92)!important;
box-shadow:inset 0 2px 0 rgba(255,255,255,.85),inset 0 6px 0 rgba(245,255,242,.20),inset 4px 0 0 rgba(215,255,239,.21),inset -4px 0 0 rgba(3,23,34,.48),inset 0 -6px 0 rgba(0,12,25,.68),0 5px 0 -1px #06292c,0 9px 0 -2px rgba(221,179,104,.58),0 17px 33px #001522a1,0 35px 62px #000d1990,0 0 23px #ffdc9152!important;
-webkit-backdrop-filter:blur(11px) saturate(1.24);backdrop-filter:blur(11px) saturate(1.24)
}
body.zm-unified-v7 #main :is(.zm-card,.zm-article,.zm-history-card){
background:radial-gradient(ellipse at 9% -13%,rgba(255,255,245,.39),transparent 65%),linear-gradient(152deg,rgba(99,181,151,.48),rgba(24,85,79,.61) 40%,rgba(4,23,39,.89))!important;
border-color:rgba(255,230,170,.92)!important;
box-shadow:inset 0 2px 0 rgba(255,255,255,.88),inset 0 6px 0 rgba(232,255,241,.20),inset 4px 0 0 rgba(217,255,242,.19),inset -4px 0 0 rgba(3,20,33,.55),inset 0 -6px 0 rgba(0,10,23,.71),0 5px 0 -1px #072b30,0 9px 0 -2px rgba(211,174,100,.53),0 18px 33px #00101db5,0 31px 56px #000c199c,0 0 25px #ffe09d56!important;
-webkit-backdrop-filter:blur(11px) saturate(1.23);backdrop-filter:blur(11px) saturate(1.23)
}
@media(hover:hover) and (pointer:fine){
body.zm-unified-v7 #main :is(.zm-card,.zm-article,.zm-history-card):is(:hover,:focus-within){
translate:0 -6px;rotate:y -2deg;
box-shadow:inset 0 2px 0 #ffffffeb,inset 0 6px 0 #e2ffe157,inset 4px 0 0 #eaffec57,inset -4px 0 0 #071824ba,inset 0 -6px 0 #000b19d9,0 6px 0 -1px #06252f,0 11px 0 -2px #f5ca87ad,0 21px 38px #000e20bc,0 37px 67px #000a1a99,0 0 36px #ffe1a88c!important
}}
@media(max-width:700px){
body.zm-unified-v7 #main :is(.zm-section-head,#zm-company-comprehensive>h2,.zm-history-topic>summary,.zm-card,.zm-article,.zm-history-card){
-webkit-backdrop-filter:blur(3px);backdrop-filter:blur(3px)
}}
@media(prefers-reduced-motion:reduce){
body.zm-unified-v7 #main :is(.zm-card,.zm-article,.zm-history-card){animation:none!important;transition:none!important;translate:none!important;rotate:none!important}
}
</style>'''
def sha(b):return hashlib.sha256(b).hexdigest()
def stage(run):
    if not re.fullmatch(r'[0-9]{1,20}',run):raise RuntimeError('Invalid run')
    return BACKUP/run
def guard():
    if pwd.getpwuid(os.getuid()).pw_name!='zomorod2':raise RuntimeError('Wrong user')
    if not HOME.is_file() or HOME.is_symlink() or HOME.parent.is_symlink() or BACKUP.is_symlink():raise RuntimeError('Unsafe path')
def patch(b):
    s=b.decode('utf-8')
    assert len(b)>40000 and s.count('</head>')==1 and s.count('</main>')==1
    assert 'zm-company-cinematic-glass-20261018' in s
    assert 'zm-history-company-content-20261018' in s and 'zm-unified-v7-20261018' in s
    assert MARKER not in s
    n=s.replace('</head>',STYLE+'</head>',1).encode()
    assert n.replace(STYLE.encode(),b'',1)==b
    return n
def atomic(path,b,mode):
    temp=None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent,prefix='.zm-thick-',delete=False) as f:
            temp=Path(f.name);f.write(b);f.flush();os.fsync(f.fileno())
        os.chmod(temp,mode);os.replace(temp,path)
    finally:
        if temp is not None and temp.exists():temp.unlink()
def test():
    s=('<html><head></head><body><!-- zm-unified-v7-20261018 --><!-- zm-history-company-content-20261018 -->'
       '<style id="zm-company-cinematic-glass-20261018"></style><main></main></body></html>'+'x'*41000).encode()
    assert patch(s).replace(STYLE.encode(),b'',1)==s
    assert all(x in STYLE for x in ('backdrop-filter','inset 0 -6px','0 9px 0 -2px','prefers-reduced-motion'))
    print('THICK_GLASS_SELFTEST=passed',flush=True)
def apply(run,expected):
    guard()
    if not re.fullmatch(r'[0-9a-f]{64}',expected):raise RuntimeError('Bad sha')
    old=HOME.read_bytes()
    if sha(old)!=expected:raise RuntimeError('Concurrent edit')
    new=patch(old);d=stage(run)
    if d.exists() or d.is_symlink():raise RuntimeError('Backup path exists')
    d.mkdir(parents=True,mode=0o700)
    mode=HOME.stat().st_mode&0o777
    atomic(d/'before.html',old,0o600)
    if sha((d/'before.html').read_bytes())!=expected:raise RuntimeError('Backup invalid')
    (d/'manifest.json').write_text(json.dumps({'before':expected,'after':sha(new),'mode':mode}))
    if sha(HOME.read_bytes())!=expected:raise RuntimeError('Concurrent change')
    atomic(HOME,new,mode)
    if sha(HOME.read_bytes())!=sha(new):raise RuntimeError('Write mismatch')
    print('THICK_GLASS_PUBLISHED=yes',flush=True)
def verify(run):
    guard();d=stage(run);m=json.loads((d/'manifest.json').read_text())
    old=(d/'before.html').read_bytes();now=HOME.read_bytes()
    assert sha(old)==m['before'] and sha(now)==m['after']
    assert now.replace(STYLE.encode(),b'',1)==old
    print('THICK_GLASS_CSS_ONLY_VERIFIED=yes',flush=True)
def rollback(run):
    guard();d=stage(run)
    if not (d/'manifest.json').is_file():return
    m=json.loads((d/'manifest.json').read_text());old=(d/'before.html').read_bytes()
    if sha(old)!=m['before']:raise RuntimeError('Bad backup')
    if sha(HOME.read_bytes())==m['before']:return
    if sha(HOME.read_bytes())!=m['after']:raise RuntimeError('Unsafe concurrent edit')
    atomic(HOME,old,m['mode'])
    assert sha(HOME.read_bytes())==m['before']
    print('THICK_GLASS_ROLLED_BACK=yes',flush=True)
if __name__=='__main__':
    if sys.argv[1:]==['selftest']:test()
    elif len(sys.argv)==4 and sys.argv[1]=='apply':apply(sys.argv[2],sys.argv[3])
    elif len(sys.argv)==3 and sys.argv[1]=='verify':verify(sys.argv[2])
    elif len(sys.argv)==3 and sys.argv[1]=='rollback':rollback(sys.argv[2])
    else:raise SystemExit('selftest | apply RUN SHA | verify RUN | rollback RUN')