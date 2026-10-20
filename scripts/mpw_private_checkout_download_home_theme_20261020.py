#!/usr/bin/env python3
"""Main-only customer secure checkout and purchased downloads homepage visual shell.
Preserve payment form, chain confirmation JS, CSRF, entitlement and all price content.
"""
import os,sys,re,json,stat,hashlib,tempfile
from pathlib import Path
ROOT=Path('/home/zomorod2/mojplaywin.com')
APP=Path('/home/zomorod2/Saeit-staging')
HOME=ROOT/'design-preview-20261017/production-home-20261017.html'
CSS=ROOT/'mpw-editorial/revenue/assets/home-shared-v1.css'
FILES={'product_checkout':APP/'mpw_commerce/templates/mpw_commerce/product_checkout.html',
       'purchased_downloads':APP/'mpw_commerce/templates/mpw_commerce/purchased_downloads.html'}
H=re.compile(r'<header\b(?=[^>]*\bclass=["\x27]mw-site-nav["\x27])[^>]*>[\s\S]*?</header\s*>',re.I)
F=re.compile(r'<footer\b(?=[^>]*\bclass=["\x27]mw-site-footer["\x27])[^>]*>[\s\S]*?</footer\s*>',re.I)
BODY=re.compile(r'<body\b[^>]*>',re.I)
MARK='data-mpw-buyer-native-home-20261020="v1"'
LINK='<link rel="stylesheet" href="/mpw-editorial/revenue/assets/home-shared-v1.css?v=20261020">'
def fail(m):raise RuntimeError(m)
def sha(b):return hashlib.sha256(b).hexdigest()
def one(pattern,text,label):
    x=list(pattern.finditer(text))
    if len(x)!=1:fail('Expected one '+label+', got '+str(len(x)))
    return x[0]
def guard():
    if ROOT.is_symlink() or ROOT.resolve()!=ROOT or APP.is_symlink() or HOME.is_symlink() or not HOME.is_file():fail('Unexpected site identity')
    w=ROOT/'passenger_wsgi.py'
    if not w.is_file() or w.is_symlink() or "APP='/home/zomorod2/Saeit-staging'" not in w.read_text('utf8','replace'):fail('Wrong app root')
    if not CSS.is_file() or CSS.is_symlink():fail('Home style not released')
    for k,p in FILES.items():
        if not p.is_file() or p.is_symlink() or p.parent.is_symlink():fail('Protected template invalid '+k)
def shell():
    raw=HOME.read_text('utf8','replace')
    h=one(H,raw,'home header').group(0);f=one(F,raw,'home footer').group(0)
    if '12 Revenue Tools' not in h or 'Mojtaba Roozegar' not in f:fail('Canonical home shell identity incomplete')
    if '{{' in h+f or '{%' in h+f:fail('Invalid Django syntax risk')
    return h.replace('<header ','<header '+MARK+' ',1),f
def transform(kind,raw,h,f):
    src=raw.decode('utf8')
    if MARK in src or LINK in src or src.count('</head>')!=1 or src.count('</main>')!=1:fail('Checkout document already modified or unexpected')
    o=one(BODY,src,'buyer body')
    out=src[:o.end()]+h+src[o.end():]
    out=out.replace('</main>','</main>'+f,1).replace('</head>',LINK+'</head>',1)
    if out.count(MARK)!=1 or out.count(LINK)!=1 or out.count('<main')!=src.count('<main'):fail('Unexpected body mutation')
    for protected in ('{% csrf_token %}','<form','payment','download','<script'):
        if out.count(protected)!=src.count(protected):fail('Commerce asset content modified: '+protected)
    if kind=='product_checkout' and ('{% csrf_token %}' not in out or '<script' not in out):fail('Order security components missing')
    return out.encode('utf8')
def compile_django(pages):
    os.chdir(APP);sys.path.insert(0,str(APP));os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings')
    import django;django.setup()
    from django.template import Template
    for v in pages.values():Template(v.decode('utf8'))
def atomic(path,data):
    fd,t=tempfile.mkstemp(dir=path.parent,prefix='.mpw-private-buyer-shell-')
    try:
        os.fchmod(fd,stat.S_IMODE(path.stat().st_mode))
        with os.fdopen(fd,'wb') as f:f.write(data);f.flush();os.fsync(f.fileno())
        os.replace(t,path)
    finally:
        if os.path.exists(t):os.unlink(t)
def backup(run):
    if not re.fullmatch(r'[0-9]{8,20}',run):fail('Invalid run id')
    return ROOT.parent/('.mpw-private-buyer-theme-'+run)
def publish(run):
    guard();h,f=shell()
    old={k:p.read_bytes() for k,p in FILES.items()}
    newer={k:transform(k,v,h,f) for k,v in old.items()}
    compile_django(newer)
    d=backup(run)
    if d.exists() or d.is_symlink():fail('Backup collision')
    d.mkdir(mode=0o700);checks={}
    for k,raw in old.items():
        p=d/(k+'.bak')
        with p.open('xb') as out:os.fchmod(out.fileno(),0o600);out.write(raw)
        checks[k]={'old':sha(raw),'new':sha(newer[k])}
    (d/'manifest.json').write_text(json.dumps({'run':run,'checks':checks}))
    os.chmod(d/'manifest.json',0o600)
    written=[]
    try:
        for k,p in FILES.items():
            if sha(p.read_bytes())!=checks[k]['old']:fail('Concurrent buyer file edit')
            atomic(p,newer[k]);written.append(k)
            if sha(p.read_bytes())!=checks[k]['new']:fail('Write integrity mismatch')
    except BaseException:
        for k in reversed(written):
            if sha(FILES[k].read_bytes())==checks[k]['new']:atomic(FILES[k],old[k])
        raise
    print('MPW_SECURE_BUYER_CHECKOUT_AND_DOWNLOADS_HOME_TEMPLATE='+json.dumps({'exact_templates':list(FILES),'amounts_untouched':True,'payment_js_preserved':True,'csrf_preserved':True,'sibling_sites_unmodified':True}))
def rollback(run):
    guard();d=backup(run)
    if d.is_symlink() or not d.is_dir():fail('No backup')
    meta=json.loads((d/'manifest.json').read_text())
    if meta.get('run')!=run:fail('Wrong release')
    original={}
    for k,p in FILES.items():
        b=d/(k+'.bak')
        if b.is_symlink() or not b.is_file() or sha(b.read_bytes())!=meta['checks'][k]['old']:fail('Bad backup')
        if sha(p.read_bytes())!=meta['checks'][k]['new']:fail('Concurrent change')
        original[k]=b.read_bytes()
    for k,v in original.items():atomic(FILES[k],v)
    print('MPW_SECURE_BUYER_HOME_TEMPLATE_ROLLBACK=PASS')
def selftest():
    s='<!doctype html><html><head></head><body><main><form method="post">{% csrf_token %}<script>var payment=1</script></form></main></body></html>'
    h='<header '+MARK+'>Home</header>';f='<footer>Brand</footer>'
    out=transform('product_checkout',s.encode(),h,f)
    assert b'csrf_token' in out and b'payment=1' in out and out.count(MARK.encode())==1
    print('MPW_CHECKOUT_HOME_THEME_BOUNDED_SELFTEST=PASS')
if __name__=='__main__':
    if len(sys.argv)==2 and sys.argv[1]=='selftest':selftest()
    elif len(sys.argv)==3 and sys.argv[1] in ('publish','rollback'):(publish if sys.argv[1]=='publish' else rollback)(sys.argv[2])
    else:raise SystemExit('selftest|publish RUN_ID|rollback RUN_ID')
