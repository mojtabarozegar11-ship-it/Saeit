#!/usr/bin/env python3
"""MojPlayWin footer visual completion, fail-closed static CSS only.

Edits only 2 already-served built stylesheet assets and matching gzip variants.
No .htaccess, Python app, JavaScript, shared Passenger, or protected child files.
Selectors require MojPlayWin-specific markup.
"""
from pathlib import Path
import gzip,hashlib,json,os,pwd,re,stat,sys,tempfile

HOME=Path('/home/zomorod2')
APP=HOME/'Saeit-staging'
DOC=HOME/'mojplaywin.com'
SITE=APP/'staticfiles/site'
DATA={
 'mojplaywin.0044ba34e437.css':(
    '524e161d23b4848e10722d55cb054b1d6fc5ed6be303a14fc93dbcbfe255e1ca',
    '\n/* MPW_FOOTER_FIVE_PAGES_20261018 main-only legacy pages */\n'
    'body > header.mpw-header ~ footer.mpw-footer::after{'
    'content:"Mojtaba Roozegar";box-sizing:border-box;grid-column:1/-1;'
    'flex-basis:100%;display:block;width:100%;text-align:center;'
    'padding:16px 10px 6px;margin-top:14px;'
    'border-top:1px solid rgba(218,176,89,.4);'
    'color:#f2cb76;font-size:clamp(1.05rem,2vw,1.4rem);'
    'font-weight:900;letter-spacing:.06em;'
    'text-shadow:0 1px 0 #4b3418,0 2px 0 #241805,0 5px 14px rgba(214,173,85,.55)}\n'),
 'site-standard-v2.69714b9b949e.css':(
    '433034dfe023548e54d21e062ff903309fe3eab3acc1dfc1f1a26fa13954ecc4',
    '\n/* MPW_FOOTER_FIVE_PAGES_20261018 shop-only */\n'
    'body.mojplaywin-store footer.mw-site-footer::after{'
    'content:"Mojtaba Roozegar";box-sizing:border-box;grid-column:1/-1;'
    'flex-basis:100%;display:block;width:100%;text-align:center;'
    'padding:16px 10px 6px;margin-top:14px;'
    'border-top:1px solid rgba(218,176,89,.4);'
    'color:#f2cb76;font-size:clamp(1.05rem,2vw,1.4rem);'
    'font-weight:900;letter-spacing:.06em;'
    'text-shadow:0 1px 0 #4b3418,0 2px 0 #241805,0 5px 14px rgba(214,173,85,.55)}\n')
}
MARK='MPW_FOOTER_FIVE_PAGES_20261018'
def checksum(data):return hashlib.sha256(data).hexdigest()
def location(runid):
    if not re.fullmatch(r'[0-9]{9,20}',runid):raise RuntimeError('Unsafe run ID')
    return HOME/('.mpw-css-footer-'+runid)
def guard():
    if pwd.getpwuid(os.getuid()).pw_name!='zomorod2':raise RuntimeError('Wrong user')
    for folder in (APP,DOC,SITE):
        if not folder.is_dir() or folder.is_symlink():raise RuntimeError('Unsafe root '+str(folder))
    w=DOC/'passenger_wsgi.py'
    if not w.is_file() or w.is_symlink() or 'Saeit-staging' not in w.read_text(errors='replace'):
        raise RuntimeError('WSGI mapping changed')
    candidates=[]
    for name,(expected,addon) in DATA.items():
        css=SITE/name
        zipped=SITE/(name+'.gz')
        if not css.is_file() or css.is_symlink() or not zipped.is_file() or zipped.is_symlink():
            raise RuntimeError('Missing static asset '+name)
        raw=css.read_bytes()
        gz=zipped.read_bytes()
        if checksum(raw)!=expected:raise RuntimeError('Concurrent CSS change '+name)
        if gzip.decompress(gz)!=raw:raise RuntimeError('Compressed variant diverges '+name)
        if MARK.encode() in raw:raise RuntimeError('Already applied '+name)
        candidates.extend([
          (css,raw,raw+addon.encode(),stat.S_IMODE(css.stat().st_mode)),
          (zipped,gz,gzip.compress(raw+addon.encode(),mtime=0),stat.S_IMODE(zipped.stat().st_mode))
        ])
    if len(candidates)!=4:raise RuntimeError('Unexpected file count')
    return candidates
def atomic(path,data,mode):
    if not path.is_file() or path.is_symlink():raise RuntimeError('Unsafe target')
    fd,temp=tempfile.mkstemp(prefix='.mpw-founder-css-',dir=path.parent)
    try:
        os.fchmod(fd,mode)
        with os.fdopen(fd,'wb') as f:
            f.write(data);f.flush();os.fsync(f.fileno())
        os.replace(temp,path)
    finally:
        if os.path.exists(temp):os.unlink(temp)
def install(runid):
    items=guard()
    dest=location(runid)
    if dest.exists() or dest.is_symlink():raise RuntimeError('Backup collision')
    dest.mkdir(mode=0o700)
    info=[]
    for i,(path,before,after,mode) in enumerate(items):
        save=dest/('%02d.original'%i)
        with save.open('xb') as f:f.write(before);f.flush();os.fsync(f.fileno())
        os.chmod(save,0o600)
        info.append({'path':str(path),'old':checksum(before),'new':checksum(after),'mode':mode,'backup':save.name})
    manifest=dest/'manifest.json'
    manifest.write_text(json.dumps(info,indent=2))
    os.chmod(manifest,0o600)
    changed=[]
    try:
        for path,before,after,mode in items:
            if checksum(path.read_bytes())!=checksum(before):raise RuntimeError('Concurrent edit before write')
            atomic(path,after,mode)
            changed.append((path,before,after,mode))
            if checksum(path.read_bytes())!=checksum(after):raise RuntimeError('Bad CSS checksum after write')
        for name in DATA:
            if gzip.decompress((SITE/(name+'.gz')).read_bytes())!=(SITE/name).read_bytes():
                raise RuntimeError('Compressed asset mismatch after write')
    except Exception:
        for path,before,after,mode in reversed(changed):
            if path.is_file() and not path.is_symlink() and checksum(path.read_bytes())==checksum(after):
                atomic(path,before,mode)
        (dest/'FAILED').write_text('recovered')
        raise
    (dest/'INSTALLED').write_text('true')
    print('MPW_FIVE_CSS_PUBLISHED=4 MAIN_ONLY=true PASSENGER_RESTART=false BACKUP='+str(dest),flush=True)
def rollback(runid):
    dest=location(runid)
    if not dest.is_dir() or dest.is_symlink():raise RuntimeError('Missing backup directory')
    rows=json.loads((dest/'manifest.json').read_text())
    for x in rows:
        path=Path(x['path']);old=(dest/x['backup']).read_bytes()
        if checksum(old)!=x['old']:raise RuntimeError('Backup changed')
        current=checksum(path.read_bytes())
        if current not in (x['old'],x['new']):raise RuntimeError('Unknown edit - do not overwrite')
    for x in rows:
        path=Path(x['path'])
        if checksum(path.read_bytes())==x['new']:
            atomic(path,(dest/x['backup']).read_bytes(),x['mode'])
    (dest/'ROLLED_BACK').write_text('true')
    print('MPW_CSS_FOOTER_ROLLBACK=PASS',flush=True)
def selftest():
    assert len(DATA)==2
    assert all(len(item[0])==64 for item in DATA.values())
    assert all(MARK in item[1] and 'Mojtaba Roozegar' in item[1] for item in DATA.values())
    assert 'body.mojplaywin-store footer.mw-site-footer::after' in DATA['site-standard-v2.69714b9b949e.css'][1]
    assert 'body > header.mpw-header ~ footer.mpw-footer::after' in DATA['mojplaywin.0044ba34e437.css'][1]
    assert all(gzip.decompress(gzip.compress(b'hello',mtime=0))==b'hello' for _ in (1,))
    print('MPW_FOOTER_CSS_SELFTEST=PASS')
if __name__=='__main__':
    command=sys.argv[1] if len(sys.argv)>1 else ''
    if command=='selftest':selftest()
    elif command=='audit':print('MPW_CSS_PREFLIGHT=PASS files='+str(len(guard())))
    elif command=='install' and len(sys.argv)==3:install(sys.argv[2])
    elif command=='rollback' and len(sys.argv)==3:rollback(sys.argv[2])
    else:raise SystemExit('selftest|audit|install RUNID|rollback RUNID')
