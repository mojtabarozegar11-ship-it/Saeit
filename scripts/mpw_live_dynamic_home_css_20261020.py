#!/usr/bin/env python3
"""Main-only PHP GET shell homepage CSS unification; finance, auth, sibling paths untouched."""
import hashlib,os,sys,re,json,stat,tempfile,subprocess
from pathlib import Path
ROOT=Path('/home/zomorod2/mojplaywin.com')
PHP=ROOT/'design-preview-20261017/_mpw_dynamic_main_shell_20261019.php'
CSS=ROOT/'mpw-editorial/revenue/assets/home-shared-v1.css'
BEFORE='    return $body;\n}\n\nfunction layoutParts(): array {'
INSERT="""    // Shared homepage CSS applies only to this root-domain GET-only page renderer.
    if (!str_contains($body,'/mpw-editorial/revenue/assets/home-shared-v1.css')) {
        $body=takeOne($body,'~</head\\\\s*>~i',
          '<link rel="stylesheet" href="/mpw-editorial/revenue/assets/home-shared-v1.css?v=20261020"></head>',
          'actual main homepage CSS',true);
    }
"""
def fail(s):raise RuntimeError(s)
def sha(b):return hashlib.sha256(b).hexdigest()
def guard():
    if ROOT.is_symlink() or ROOT.resolve()!=ROOT or not (ROOT/'.htaccess').is_file() or PHP.is_symlink() or not PHP.is_file():fail('Wrong root')
    if CSS.is_symlink() or not CSS.is_file() or CSS.stat().st_size<1500:fail('Home CSS not verified')
    ht=(ROOT/'.htaccess').read_text('utf8','replace')
    if '_mpw_dynamic_main_shell_20261019.php' not in ht:fail('Main-only route identity missing')
def transform(raw):
    text=raw.decode('utf8')
    if text.count(BEFORE)!=1 or text.count('MPW_HOME_UNIFICATION_RELEASE_20261020')!=1:fail('Wrong live PHP variant')
    if 'actual main homepage CSS' in text:fail('Already synchronized')
    text=text.replace(BEFORE,INSERT+BEFORE,1)
    return text.encode('utf8')
def php_lint(data):
    fd,p=tempfile.mkstemp(suffix='.php',dir=PHP.parent,prefix='.mpw-main-only-php-')
    try:
        with os.fdopen(fd,'wb') as o:o.write(data)
        out=subprocess.run(['php','-l',p],capture_output=True,text=True,timeout=20)
        if out.returncode:fail('PHP lint rejected: '+out.stderr[-320:])
    finally:
        if os.path.exists(p):os.unlink(p)
def atomic(data):
    fd,p=tempfile.mkstemp(dir=PHP.parent,prefix='.mpw-shell-stage-')
    try:
        os.fchmod(fd,stat.S_IMODE(PHP.stat().st_mode))
        with os.fdopen(fd,'wb') as out:out.write(data);out.flush();os.fsync(out.fileno())
        os.replace(p,PHP)
    finally:
        if os.path.exists(p):os.unlink(p)
def backup(run):
    if not re.fullmatch(r'[0-9]{8,20}',run):fail('Invalid run')
    return ROOT.parent/('.mpw-php-home-css-'+run+'.bak')
def publish(run):
    guard();raw=PHP.read_bytes();new=transform(raw);php_lint(new)
    dest=backup(run)
    if dest.exists() or dest.is_symlink():fail('Backup collision')
    with dest.open('xb') as out:os.fchmod(out.fileno(),0o600);out.write(raw);out.flush();os.fsync(out.fileno())
    if sha(PHP.read_bytes())!=sha(raw):fail('Concurrent edit')
    atomic(new)
    if sha(PHP.read_bytes())!=sha(new):fail('Write verification mismatch')
    print('MPW_19_DYNAMIC_ROUTES_HOMEPAGE_CSS_INSTALLED='+json.dumps({'before':sha(raw),'after':sha(new),'php_lint':True,'main_only':True,'checkout_unchanged':True}))
def rollback(run):
    guard();p=backup(run)
    if p.is_symlink() or not p.is_file():fail('Wrong backup')
    raw=p.read_bytes();new=transform(raw)
    if sha(PHP.read_bytes())!=sha(new):fail('Refuse rollback concurrent PHP edit')
    atomic(raw)
    if sha(PHP.read_bytes())!=sha(raw):fail('Restore failed')
    print('MPW_DYNAMIC_HOMEPAGE_CSS_ROLLBACK=PASS')
def selftest():
    sample=('<?php\n// MPW_HOME_UNIFICATION_RELEASE_20261020\nfunction foo() {\n'+BEFORE)
    s=transform(sample.encode()).decode()
    assert s.count('actual main homepage CSS')==1 and s.count('return $body;')==1
    print('MPW_DYNAMIC_THEME_PATCH_SELFTEST=PASS')
if __name__=='__main__':
    if len(sys.argv)==2 and sys.argv[1]=='selftest':selftest()
    elif len(sys.argv)==3 and sys.argv[1] in ('publish','rollback'):(publish if sys.argv[1]=='publish' else rollback)(sys.argv[2])
    else:raise SystemExit('selftest|publish RUN_ID|rollback RUN_ID')
