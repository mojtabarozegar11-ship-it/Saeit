#!/usr/bin/env python3
"""Atomic 19 exact-root GET route bridge for the main MojPlayWin domain only.

The Django/Passenger process is not restarted. The browser's main-only GET HTML
is rebranded while original Django responses and cookies are preserved.
"""
from pathlib import Path
import hashlib,json,os,pwd,re,stat,sys,tempfile

HOME=Path('/home/zomorod2')
ROOT=HOME/'mojplaywin.com'
APP=HOME/'Saeit-staging'
HT=ROOT/'.htaccess'
TARGET=ROOT/'design-preview-20261017/_mpw_dynamic_main_shell_20261019.php'
EXPECTED_HT='ad715102ab237d8ed63d807b8f30065fb341a8785f02d5644af6fc826c6936ea'
ROUTES=(
'store','games','ai','contact','support','privacy','terms','cookies',
'products','blockchain','commerce','crypto-payments','global-business',
'research-lab','canada-vision','agro-industry','agriculture','education','weather')
START='# MPW_MAIN_19_EXACT_DYNAMIC_SHELL_20261019_BEGIN'
END='# MPW_MAIN_19_EXACT_DYNAMIC_SHELL_20261019_END'
RULES=f'''
{START}
# GET-only MojPlayWin root paths; never matches any child site route.
RewriteCond %{{REQUEST_METHOD}} ^GET$
RewriteCond %{{QUERY_STRING}} !(^|&)__mpw_template_passthru=1(&|$)
RewriteCond %{{REQUEST_URI}} ^/({"|".join(ROUTES)})/$
RewriteRule ^.*$ /design-preview-20261017/_mpw_dynamic_main_shell_20261019.php?__mpw_template_route=%1 [END,QSA]
{END}
'''
def sha(raw):return hashlib.sha256(raw).hexdigest()
def valid_run(v):
    if not re.fullmatch(r'[0-9]{9,20}',v):raise RuntimeError('Invalid deployment run id')
    return v
def valid_sha(v):
    if not re.fullmatch(r'[0-9a-f]{64}',v):raise RuntimeError('Invalid source checksum')
    return v
def staged(run):
    return HOME/('.mpw-main-shell-staging-'+valid_run(run)+'.php')
def backup_path(run):
    return HOME/('.mpw-main-shell-backup-'+valid_run(run))
def inspect(run,hashsum):
    if pwd.getpwuid(os.getuid()).pw_name!='zomorod2':raise RuntimeError('Unexpected cPanel user')
    for p in (HOME,ROOT,APP,TARGET.parent):
        if not p.is_dir() or p.is_symlink():raise RuntimeError('Invalid deployment folder')
    wsgi=ROOT/'passenger_wsgi.py'
    if not wsgi.is_file() or wsgi.is_symlink() or 'Saeit-staging' not in wsgi.read_text(errors='replace'):
        raise RuntimeError('Django owner no longer matches baseline')
    if not HT.is_file() or HT.is_symlink():raise RuntimeError('Unsafe routing')
    old=HT.read_bytes()
    if sha(old)!=EXPECTED_HT or START.encode() in old:raise RuntimeError('Concurrent .htaccess edit, fail closed')
    if old.count(b'RewriteEngine On')!=1:raise RuntimeError('Unexpected rewrite configuration')
    if TARGET.exists() or TARGET.is_symlink():raise RuntimeError('Target already exists')
    source=staged(run)
    if not source.is_file() or source.is_symlink():raise RuntimeError('PHP source not staged')
    raw=source.read_bytes()
    if len(raw)<10000 or sha(raw)!=valid_sha(hashsum) or not raw.startswith(b'<?php'):
        raise RuntimeError('PHP payload mismatch')
    if b'Site-only GET response renderer' not in raw or b'MPW_MAIN_19' in old:
        raise RuntimeError('Unexpected bridge payload')
    if len(ROUTES)!=19 or len(set(ROUTES))!=19 or any('/' in x for x in ROUTES):
        raise RuntimeError('Route allowlist incorrect')
    if not (ROOT/'design-preview-20261017/mpw-ten-editorials-20261018/pages/research.html').is_file():
        raise RuntimeError('Main MojPlayWin shell source missing')
    new=old.replace(b'RewriteEngine On',b'RewriteEngine On\n'+RULES.encode(),1)
    if new==old or new.replace(b'\n'+RULES.encode(),b'',1)!=old:
        raise RuntimeError('Non-additive rewrite change')
    return source,raw,old,new
def atomic(path,data,mode,create=False):
    if path.is_symlink() or (not create and not path.is_file()):
        raise RuntimeError('Unsafe atomic target')
    fd,t=tempfile.mkstemp(prefix='.mpw-main-shell-',dir=path.parent)
    try:
        os.fchmod(fd,mode)
        with os.fdopen(fd,'wb') as file:
            file.write(data);file.flush();os.fsync(file.fileno())
        os.replace(t,path)
    finally:
        if os.path.exists(t):os.unlink(t)
def install(run,hashsum):
    source,raw,old,new=inspect(run,hashsum)
    backup=backup_path(run)
    if backup.exists() or backup.is_symlink():raise RuntimeError('Backup already exists')
    backup.mkdir(mode=0o700)
    original=backup/'original.htaccess'
    with original.open('xb') as file:file.write(old);file.flush();os.fsync(file.fileno())
    os.chmod(original,0o600)
    mode=stat.S_IMODE(HT.stat().st_mode)
    info={'old':sha(old),'new':sha(new),'php':sha(raw),'mode':mode,
        'routes':list(ROUTES),'target':str(TARGET)}
    manifest=backup/'manifest.json'
    manifest.write_text(json.dumps(info,indent=2))
    os.chmod(manifest,0o600)
    did_install=False
    try:
        if sha(HT.read_bytes())!=info['old']:raise RuntimeError('Concurrent edit before commit')
        atomic(TARGET,raw,0o644,create=True)
        if sha(TARGET.read_bytes())!=info['php']:raise RuntimeError('Bridge install checksum mismatch')
        atomic(HT,new,mode)
        did_install=True
        if sha(HT.read_bytes())!=info['new']:raise RuntimeError('Rewrite commit checksum mismatch')
    except Exception:
        if did_install and sha(HT.read_bytes())==info['new']:
            atomic(HT,old,mode)
        if TARGET.is_file() and not TARGET.is_symlink() and sha(TARGET.read_bytes())==info['php']:
            TARGET.unlink()
        (backup/'FAILED').write_text('automatic rollback')
        raise
    (backup/'INSTALLED').write_text('yes')
    print('MPW_DYNAMIC_MAIN_19_INSTALLED=PASS no_passenger_restart=true no_shared_app_edit=true BACKUP='+str(backup),flush=True)
def rollback(run):
    backup=backup_path(run)
    if not backup.is_dir() or backup.is_symlink():
        print('MPW_DYNAMIC_MAIN_NO_INSTALL_TO_ROLL_BACK')
        return
    manifest=backup/'manifest.json'
    original=backup/'original.htaccess'
    if not manifest.is_file() or not original.is_file() or manifest.is_symlink() or original.is_symlink():
        raise RuntimeError('Unsafe backup')
    info=json.loads(manifest.read_text())
    old=original.read_bytes()
    if sha(old)!=info['old']:raise RuntimeError('Backup corruption')
    current=sha(HT.read_bytes())
    if current not in (info['old'],info['new']):raise RuntimeError('Concurrent route change: do not clobber')
    if TARGET.is_file() and (TARGET.is_symlink() or sha(TARGET.read_bytes())!=info['php']):
        raise RuntimeError('Concurrent bridge change: do not clobber')
    if current==info['new']:atomic(HT,old,info['mode'])
    if TARGET.is_file():TARGET.unlink()
    (backup/'ROLLED_BACK').write_text('yes')
    print('MPW_DYNAMIC_MAIN_19_ROLLBACK=PASS',flush=True)
def selftest():
    assert len(ROUTES)==19 and len(set(ROUTES))==19
    assert len(EXPECTED_HT)==64
    assert RULES.count('RewriteRule')==1
    assert '^GET$' in RULES and '__mpw_template_passthru=1' in RULES
    for protected in ('/taniya/','/farnaz/','/saman/','/zahra/','/roham/','/picm/'):
        assert protected not in RULES
    assert len(RULES)<1300
    print('MPW_DYNAMIC_MAIN_EXACT19_SELFTEST=PASS',flush=True)
if __name__=='__main__':
    cmd=sys.argv[1] if len(sys.argv)>1 else ''
    if cmd=='selftest':selftest()
    elif cmd=='audit' and len(sys.argv)==4:
        source,raw,old,new=inspect(sys.argv[2],sys.argv[3])
        print('MPW_MAIN_ONLY_19_PREFLIGHT=PASS old='+sha(old)+' new='+sha(new)+' php='+sha(raw),flush=True)
    elif cmd=='install' and len(sys.argv)==4:install(sys.argv[2],sys.argv[3])
    elif cmd=='rollback' and len(sys.argv)==3:rollback(sys.argv[2])
    else:raise SystemExit('selftest | audit RUNID SHA | install RUNID SHA | rollback RUNID')
