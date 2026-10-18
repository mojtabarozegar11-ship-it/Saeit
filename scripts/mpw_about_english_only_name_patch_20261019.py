#!/usr/bin/env python3
"""Remove exactly one parenthesized Persian spelling from ONLY MojPlayWin's live /about/.
No changes to other content, routes, templates, Passenger or independent child sites.
"""
from pathlib import Path
import hashlib, json, os, pwd, re, stat, sys, tempfile

HOME = Path('/home/zomorod2')
ROOT = HOME / 'mojplaywin.com'
PAGE = ROOT / 'design-preview-20261017/mpw-ten-editorials-20261018/pages/about.html'
ROUTES = ROOT / '.htaccess'
OLD = 'Mojtaba Roozegar (مجتبی روزگار)'.encode('utf-8')
NEW = b'Mojtaba Roozegar'
MARKER = b'MPW_ABOUT_RESEARCH_80_20_V1'

def digest(data):
    return hashlib.sha256(data).hexdigest()

def run_id(value):
    if not re.fullmatch(r'[0-9]{9,20}', value):
        raise RuntimeError('Invalid GitHub run id')
    return value

def checkpoint(value):
    if not re.fullmatch(r'[0-9a-f]{64}', value):
        raise RuntimeError('Invalid public page SHA')
    return value

def root_checks():
    if pwd.getpwuid(os.getuid()).pw_name != 'zomorod2':
        raise RuntimeError('Unexpected remote SSH account')
    for path in (ROOT, PAGE.parent, PAGE.parent.parent, PAGE.parent.parent.parent):
        if not path.is_dir() or path.is_symlink():
            raise RuntimeError('Unsafe or missing About parent')
    if not PAGE.is_file() or PAGE.is_symlink() or not ROUTES.is_file() or ROUTES.is_symlink():
        raise RuntimeError('Unexpected About file or route ownership')
    rules = ROUTES.read_text('utf-8', errors='replace')
    condition = 'RewriteCond %{REQUEST_URI} ^/about/$'
    destination = 'RewriteRule ^.*$ /design-preview-20261017/mpw-ten-editorials-20261018/pages/about.html [END,QSD]'
    if condition not in rules or destination not in rules or rules.index(condition)>rules.index(destination):
        raise RuntimeError('Main About public route changed, refusing file edit')
    wsgi = ROOT / 'passenger_wsgi.py'
    if not wsgi.is_file() or wsgi.is_symlink() or 'Saeit-staging' not in wsgi.read_text(errors='replace'):
        raise RuntimeError('Passenger mapping changed')
    
def compose(before):
    if not (50_000 <= len(before) <= 1_500_000):
        raise RuntimeError('Unexpected About page size')
    if before.count(OLD)!=1:
        raise RuntimeError('Persian founder spelling not exactly once, refusing edit')
    if MARKER not in before or b'MojPlayWin' not in before:
        raise RuntimeError('Unexpected About document, refusing edit')
    if before.count(b'<main')!=1 or before.count(b'</main>')!=1:
        raise RuntimeError('Unexpected About document landmarks')
    after=before.replace(OLD, NEW, 1)
    if after.replace(NEW,OLD,1)!=before:
        # NEW occurs before the target as well. Use byte-slice proof instead.
        pos=before.index(OLD)
        if after[:pos]!=before[:pos] or after[pos+len(NEW):]!=before[pos+len(OLD):]:
            raise RuntimeError('Modification is not an exact one-span deletion')
    if b'\xd9\x85\xd8\xac\xd8\xaa\xd8\xa8\xdb\x8c \xd8\xb1\xd9\x88\xd8\xb2\xda\xaf\xd8\xa7\xd8\xb1' in after:
        raise RuntimeError('Persian name still present')
    if after.count(b'Mojtaba Roozegar') != before.count(b'Mojtaba Roozegar'):
        raise RuntimeError('English spelling changed')
    return after

def prepare(expected):
    root_checks()
    raw=PAGE.read_bytes()
    if digest(raw)!=checkpoint(expected):
        raise RuntimeError('Current file differs from exact public /about/ page; no changes')
    return raw,compose(raw)

def backup_folder(rid):
    return HOME / ('.mpw-about-name-only-' + run_id(rid))

def atomic(path,data,mode):
    if not path.is_file() or path.is_symlink():
        raise RuntimeError('Not an approved normal file')
    fd,temp=tempfile.mkstemp(prefix='.mpw-about-name-', dir=path.parent)
    try:
        os.fchmod(fd,mode)
        with os.fdopen(fd,'wb') as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp,path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)

def install(rid,expected):
    before,after=prepare(expected)
    folder=backup_folder(rid)
    if folder.exists() or folder.is_symlink():
        raise RuntimeError('Backup collision')
    folder.mkdir(mode=0o700)
    back=folder/'about.original.html'
    with back.open('xb') as f:
        f.write(before)
        f.flush()
        os.fsync(f.fileno())
    os.chmod(back,0o600)
    mode=stat.S_IMODE(PAGE.stat().st_mode)
    info={'file':str(PAGE),'before':digest(before),'after':digest(after),'mode':mode}
    manifest=folder/'manifest.json'
    manifest.write_text(json.dumps(info))
    os.chmod(manifest,0o600)
    if digest(PAGE.read_bytes())!=info['before']:
        raise RuntimeError('Concurrent About edit before apply')
    try:
        atomic(PAGE,after,mode)
        if digest(PAGE.read_bytes())!=info['after']:
            raise RuntimeError('About verification failed')
    except Exception:
        if PAGE.is_file() and not PAGE.is_symlink() and digest(PAGE.read_bytes())==info['after']:
            atomic(PAGE,before,mode)
        raise
    print('ABOUT_FOUNDER_NAME_UPDATED=1 ENGLISH_PRESERVED=true OTHER_FILES_CHANGED=false BACKUP='+str(folder),flush=True)

def rollback(rid):
    folder=backup_folder(rid)
    if not folder.is_dir() or folder.is_symlink():
        print('ABOUT_NO_INSTALL_TO_ROLLBACK',flush=True)
        return
    manifest=folder/'manifest.json'
    back=folder/'about.original.html'
    if not manifest.is_file() or not back.is_file() or manifest.is_symlink() or back.is_symlink():
        raise RuntimeError('Unsafe recovery checkpoint')
    data=json.loads(manifest.read_text())
    original=back.read_bytes()
    if digest(original)!=data['before']:
        raise RuntimeError('Backup corrupted')
    live=PAGE.read_bytes()
    if digest(live)==data['before']:
        print('ABOUT_ALREADY_ORIGINAL',flush=True)
        return
    if digest(live)!=data['after']:
        raise RuntimeError('Concurrent changes since deploy, refuse rollback overwrite')
    atomic(PAGE,original,data['mode'])
    print('ABOUT_FOUNDER_NAME_ROLLBACK=PASS',flush=True)

def selftest():
    sample=(b'<main>MPW_ABOUT_RESEARCH_80_20_V1 MojPlayWin '+b'x'*51000+b'Mojtaba Roozegar ('+'مجتبی روزگار'.encode()+b') </main>')
    after=compose(sample)
    assert after==sample.replace(OLD,NEW,1)
    assert after.count(NEW)==sample.count(NEW)
    assert OLD not in after
    print('EXACT_ENGLISH_NAME_SELFTEST=PASS',flush=True)

if __name__=='__main__':
    mode=sys.argv[1] if len(sys.argv)>1 else ''
    if mode=='selftest':
        selftest()
    elif mode=='audit' and len(sys.argv)==3:
        original,new=prepare(sys.argv[2])
        print('ABOUT_EXACT_PUBLIC_SHA=PASS old='+digest(original)+' new='+digest(new),flush=True)
    elif mode=='install' and len(sys.argv)==4:
        install(sys.argv[2],sys.argv[3])
    elif mode=='rollback' and len(sys.argv)==3:
        rollback(sys.argv[2])
    else:
        raise SystemExit('Usage: selftest | audit PUBLIC_SHA | install RUNID PUBLIC_SHA | rollback RUNID')
