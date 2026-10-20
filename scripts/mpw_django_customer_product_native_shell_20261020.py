#!/usr/bin/env python3
"""Main MojPlayWin branded Django product, login, register templates share exact home shell.
No changes to Django views, payment, public routing, DB, secrets or child subsite assets.
"""
import os,re,sys,json,stat,hashlib,tempfile
from pathlib import Path
APP=Path('/home/zomorod2/Saeit-staging')
ROOT=Path('/home/zomorod2/mojplaywin.com')
HOME=ROOT/'design-preview-20261017/production-home-20261017.html'
CSS=ROOT/'mpw-editorial/revenue/assets/home-shared-v1.css'
FILES={'brandbase':APP/'core/templates/brands/mojplaywin/base.html',
       'login':APP/'mpw_commerce/templates/mpw_commerce/customer_login.html',
       'register':APP/'mpw_commerce/templates/mpw_commerce/customer_register.html'}
HEAD=re.compile(r'<header\b(?=[^>]*\bclass=["\x27]mw-site-nav["\x27])[^>]*>[\s\S]*?</header\s*>',re.I)
FOOT=re.compile(r'<footer\b(?=[^>]*\bclass=["\x27]mw-site-footer["\x27])[^>]*>[\s\S]*?</footer\s*>',re.I)
BRAND_HEAD=re.compile(r'<header\b(?=[^>]*\bclass=["\x27]mpw-header["\x27])[^>]*>[\s\S]*?</header\s*>',re.I)
BRAND_FOOT=re.compile(r'<footer\b(?=[^>]*\bclass=["\x27]mpw-footer["\x27])[^>]*>[\s\S]*?</footer\s*>',re.I)
MARK='data-mpw-django-home-20261020="true"'
LINK='<link rel="stylesheet" href="/mpw-editorial/revenue/assets/home-shared-v1.css?v=20261020">'
def fail(s):raise RuntimeError(s)
def sha(b):return hashlib.sha256(b).hexdigest()
def one(pattern,text,title):
    matches=list(pattern.finditer(text))
    if len(matches)!=1:fail('Expected one '+title+', got '+str(len(matches)))
    return matches[0]
def guard():
    if APP.is_symlink() or ROOT.is_symlink() or ROOT.resolve()!=ROOT or not HOME.is_file() or HOME.is_symlink():fail('Wrong MojPlayWin root')
    p=ROOT/'passenger_wsgi.py'
    if not p.is_file() or p.is_symlink() or "APP='/home/zomorod2/Saeit-staging'" not in p.read_text('utf8','replace'):fail('Wrong Passenger app')
    if CSS.is_symlink() or not CSS.is_file() or CSS.stat().st_size<1500:fail('Homepage CSS missing')
    for key,path in FILES.items():
        if not path.is_file() or path.is_symlink() or path.parent.is_symlink():fail('Unverified brand-only file '+key)
def shell():
    raw=HOME.read_text('utf8')
    header=one(HEAD,raw,'homepage header').group(0)
    footer=one(FOOT,raw,'homepage footer').group(0)
    if '12 Revenue Tools' not in header or 'Mojtaba Roozegar' not in footer:fail('Homepage brand identity drift')
    if any(x in header+footer for x in ('{%','{{')):fail('Unsafe Django source syntax in homepage shell')
    return header.replace('<header ','<header '+MARK+' ',1),footer
def transform(name,raw,h,f):
    text=raw.decode('utf8')
    if MARK in text or LINK in text:fail('Already unified '+name)
    if text.lower().count('</head>')!=1:fail('Unexpected HEAD '+name)
    if name=='brandbase':
        header=one(BRAND_HEAD,text,'branded product header')
        text=text[:header.start()]+h+text[header.end():]
        footer=one(BRAND_FOOT,text,'branded product footer')
        text=text[:footer.start()]+f+text[footer.end():]
        if "mpw-founder-footer-final" not in raw.decode('utf8'):fail('Original footer identity unknown')
    else:
        if text.count('<body><main>')!=1 or text.count('</main></body>')!=1:fail('Auth template structure drift '+name)
        text=text.replace('<body><main>','<body>'+h+'<main>',1)
        text=text.replace('</main></body>','</main>'+f+'</body>',1)
        if text.count('{% csrf_token %}')!=1 or text.count('<form method="post"')!=1:fail('CSRF or user form lost '+name)
    text=text.replace('</head>',LINK+'</head>',1)
    if text.count(MARK)!=1 or text.count(LINK)!=1 or text.count('</main>')!=raw.decode('utf8').count('</main>'):fail('Structure changed '+name)
    return text.encode('utf8')
def validate_templates(changes):
    os.chdir(APP);sys.path.insert(0,str(APP));os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings')
    import django;django.setup()
    from django.template import Template
    for content in changes.values():Template(content.decode('utf8'))
def atomic(dest,data):
    fd,temp=tempfile.mkstemp(dir=dest.parent,prefix='.mpw-django-theme-')
    try:
        os.fchmod(fd,stat.S_IMODE(dest.stat().st_mode))
        with os.fdopen(fd,'wb') as out:out.write(data);out.flush();os.fsync(out.fileno())
        os.replace(temp,dest)
    finally:
        if os.path.exists(temp):os.unlink(temp)
def backup(run):
    if not re.fullmatch(r'[0-9]{8,20}',run):fail('Invalid run')
    return ROOT.parent/('.mpw-django-home-shell-'+run)
def publish(run):
    guard();h,f=shell()
    old={key:path.read_bytes() for key,path in FILES.items()}
    changes={key:transform(key,v,h,f) for key,v in old.items()}
    validate_templates(changes)
    b=backup(run)
    if b.exists() or b.is_symlink():fail('Backup collision')
    b.mkdir(mode=0o700);meta={}
    for key,v in old.items():
        with (b/(key+'.orig')).open('xb') as out:os.fchmod(out.fileno(),0o600);out.write(v)
        meta[key]={'original':sha(v),'published':sha(changes[key])}
    (b/'manifest.json').write_text(json.dumps({'run':run,'checks':meta}))
    os.chmod(b/'manifest.json',0o600)
    applied=[]
    try:
        for key,path in FILES.items():
            if sha(path.read_bytes())!=meta[key]['original']:fail('Concurrent template edit')
            atomic(path,changes[key]);applied.append(key)
            if sha(path.read_bytes())!=meta[key]['published']:fail('Published checksum failed')
    except BaseException:
        for key in reversed(applied):
            if sha(FILES[key].read_bytes())==meta[key]['published']:atomic(FILES[key],old[key])
        raise
    print('MPW_DJANGO_MAIN_ACCOUNT_AND_PRODUCT_HOMEPAGE_TEMPLATE='+json.dumps({'templates':list(FILES),'django_compile':True,'home_shell_exact':True,'finance_untouched':True,'other_subsites_untouched':True}))
def rollback(run):
    guard();b=backup(run)
    if b.is_symlink() or not b.is_dir():fail('Backup unavailable')
    obj=json.loads((b/'manifest.json').read_text())
    if obj.get('run')!=run:fail('Mismatched release ID')
    original={}
    for key,path in FILES.items():
        bk=b/(key+'.orig')
        if bk.is_symlink() or not bk.is_file() or sha(bk.read_bytes())!=obj['checks'][key]['original']:fail('Bad backup')
        if sha(path.read_bytes())!=obj['checks'][key]['published']:fail('Concurrent edits; refuse rollback')
        original[key]=bk.read_bytes()
    for key,v in original.items():atomic(FILES[key],v)
    print('MPW_DJANGO_HOME_TEMPLATE_ROLLBACK=PASS')
def selftest():
    h='<header '+MARK+'>Home header</header>';f='<footer>© Mojtaba Roozegar</footer>'
    src='<!doctype html><html lang="en"><head></head><body><main><form method="post">{% csrf_token %}<input name="username"></form></main></body></html>'
    assert transform('login',src.encode(),h,f).count(MARK.encode())==1
    print('MPW_DJANGO_HOME_SHELL_BOUNDED_SELFTEST=PASS')
if __name__=='__main__':
    if len(sys.argv)==2 and sys.argv[1]=='selftest':selftest()
    elif len(sys.argv)==3 and sys.argv[1] in ('publish','rollback'):(publish if sys.argv[1]=='publish' else rollback)(sys.argv[2])
    else:raise SystemExit('selftest|publish RUN_ID|rollback RUN_ID')
