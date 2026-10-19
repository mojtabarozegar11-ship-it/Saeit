#!/usr/bin/env python3
"""Correct the founder profile heading order in only one exact MojPlayWin file."""
import hashlib,json,os,re,stat,sys,tempfile
from pathlib import Path

ROOT=Path("/home/zomorod2/mojplaywin.com")
PAGE=ROOT/"design-preview-20261017/mpw-ten-editorials-20261018/pages/about-mojtaba-rozegar.html"
RULES=ROOT/".htaccess"
MARK="MPW_FOUNDER_HEADING_A11Y_20261019"
OLD_FIRST='<h2 id="mpw-professor-title">Professor Mojtaba Roozegar</h2>'
NEW_FIRST='<h1 id="mpw-professor-title">Professor Mojtaba Roozegar</h1>'
OLD_LATE='<h1>Professor Mojtaba Roozegar</h1>'
NEW_LATE='<h2>Research background and leadership principles</h2>'
def fail(m):raise RuntimeError(m)
def sha(b):return hashlib.sha256(b).hexdigest()
def targets(rid):
    if not re.fullmatch(r'[0-9]{9,20}',rid):fail('Invalid run ID')
    return ROOT.parent/('.mpw-founder-heading-'+rid+'.bak'),ROOT.parent/('.mpw-founder-heading-'+rid+'.json')
def patch(src):
    if MARK in src:fail('Already installed')
    if src.count(OLD_FIRST)!=1 or src.count(OLD_LATE)!=1:fail('Original profile headings drifted')
    if len(re.findall(r'<h1\b',src,flags=re.I))!=1:fail('Original H1 count drifted')
    if src.index(OLD_FIRST)>src.index(OLD_LATE):fail('Headings already reordered')
    for tag in ('official_profile_20261016','mpw-ten-heading-about-mojtaba-rozegar',
                'mpw-research30-title-about-mojtaba-rozegar'):
        if tag not in src:fail('Source section missing: '+tag)
    result=src.replace(OLD_LATE,NEW_LATE,1).replace(OLD_FIRST,NEW_FIRST,1)
    result=result.replace('</body>','<!-- '+MARK+' -->\n</body>',1)
    if len(re.findall(r'<h1\b',result,flags=re.I))!=1:fail('Post-repair H1 invalid')
    main=re.search(r'<main\b[^>]*>',result,re.I)
    first=re.search(r'<h[1-6]\b',result[main.end():],re.I) if main else None
    if not first or result[main.end()+first.start():].lower().find('<h1')!=0:
        fail('H1 still not first heading inside main')
    return result
def atomic(raw,mode):
    fd,tmp=tempfile.mkstemp(dir=PAGE.parent,prefix='.mpw-founder-h1-')
    try:
        os.fchmod(fd,mode)
        with os.fdopen(fd,'wb') as f:
            f.write(raw);f.flush();os.fsync(f.fileno())
        os.replace(tmp,PAGE)
    finally:
        if os.path.lexists(tmp):os.unlink(tmp)
def guard():
    if ROOT.resolve()!=ROOT or not ROOT.is_dir() or ROOT.is_symlink():fail('Unexpected site root')
    if not PAGE.is_file() or PAGE.is_symlink() or PAGE.parent.is_symlink() or not RULES.is_file():
        fail('Unsafe page')
    rules=RULES.read_text('utf-8',errors='replace')
    if '/design-preview-20261017/mpw-ten-editorials-20261018/pages/about-mojtaba-rozegar.html' not in rules:
        fail('Founder live route mapping does not point to exact file')
def install(rid):
    guard()
    backup,manifest=targets(rid)
    if backup.exists() or manifest.exists():fail('Run already exists')
    old=PAGE.read_bytes()
    new=patch(old.decode('utf-8')).encode('utf-8')
    with backup.open('xb') as f:
        os.fchmod(f.fileno(),0o600);f.write(old);f.flush();os.fsync(f.fileno())
    record={'rid':rid,'old':sha(old),'new':sha(new)}
    with manifest.open('x') as f:
        os.fchmod(f.fileno(),0o600);json.dump(record,f);f.flush();os.fsync(f.fileno())
    if PAGE.read_bytes()!=old:fail('Concurrent founder edit')
    atomic(new,stat.S_IMODE(PAGE.stat().st_mode))
    if sha(PAGE.read_bytes())!=record['new']:fail('Written file hash drifted')
    print('MPW_FOUNDER_HEADING_INSTALL='+json.dumps(record))
def rollback(rid):
    guard()
    backup,manifest=targets(rid)
    record=json.loads(manifest.read_text())
    old=backup.read_bytes()
    if record['rid']!=rid or record['old']!=sha(old) or record['new']!=sha(PAGE.read_bytes()):
        fail('Unsafe rollback')
    atomic(old,stat.S_IMODE(PAGE.stat().st_mode))
    if sha(PAGE.read_bytes())!=record['old']:fail('Rollback mismatch')
    print('MPW_FOUNDER_HEADING_ROLLBACK=PASS')
if __name__=='__main__':
    if len(sys.argv)!=3:fail('install|rollback RUN_ID')
    {'install':install,'rollback':rollback}[sys.argv[1]](sys.argv[2])
