#!/usr/bin/env python3
"""Replace exactly one MojPlayWin-owned PHP presentation script, no route edits."""
from pathlib import Path
import hashlib,json,os,pwd,re,stat,sys,tempfile

HOME=Path('/home/zomorod2')
ROOT=HOME/'mojplaywin.com'
TARGET=ROOT/'design-preview-20261017/_mpw_dynamic_main_shell_20261019.php'
HT=ROOT/'.htaccess'
OLD_SHA='147f5fd696628d5ea15ea05bb64e59cea343ee64d45d46ca1c931cb68e6e43cc'
ROUTE_MARK='MPW_MAIN_19_EXACT_DYNAMIC_SHELL_20261019_BEGIN'
def sha(raw):return hashlib.sha256(raw).hexdigest()
def valid_run(v):
    if not re.fullmatch(r'[0-9]{9,20}',v):raise RuntimeError('Unsafe workflow identifier')
    return v
def valid_hash(v):
    if not re.fullmatch(r'[0-9a-f]{64}',v):raise RuntimeError('Unsafe hash')
    return v
def stage(run):return HOME/('.mpw-main-shell-staging-'+valid_run(run)+'.php')
def backup(run):return HOME/('.mpw-main-education-meta-backup-'+valid_run(run))
def prepare(run,expected):
    if pwd.getpwuid(os.getuid()).pw_name!='zomorod2':raise RuntimeError('Wrong owner')
    if not TARGET.is_file() or TARGET.is_symlink() or not HT.is_file() or HT.is_symlink():
        raise RuntimeError('Unexpected presentation bridge')
    if ROUTE_MARK not in HT.read_text('utf8',errors='replace'):
        raise RuntimeError('Main-only route removed')
    original=TARGET.read_bytes()
    if sha(original)!=OLD_SHA:raise RuntimeError('Concurrent PHP change; no overwrite')
    p=stage(run)
    if not p.is_file() or p.is_symlink():raise RuntimeError('No private staged payload')
    new=p.read_bytes()
    if sha(new)!=valid_hash(expected):raise RuntimeError('Staged source hash mismatch')
    if len(new)<17000 or b'MPW_MAIN_ONLY_BRIDGE_SELFTEST=PASS' not in new:
        raise RuntimeError('Wrong PHP source')
    if b'MojPlayWin education, practical skills' not in new:
        raise RuntimeError('Education metadata correction not present')
    return original,new,stat.S_IMODE(TARGET.stat().st_mode)
def atomic(path,raw,mode):
    if path.is_symlink() or not path.is_file():raise RuntimeError('Unsafe path')
    fd,p=tempfile.mkstemp(prefix='.mpw-education-meta-',dir=path.parent)
    try:
        os.fchmod(fd,mode)
        with os.fdopen(fd,'wb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
        os.replace(p,path)
    finally:
        if os.path.exists(p):os.unlink(p)
def install(run,expected):
    old,new,mode=prepare(run,expected)
    folder=backup(run)
    if folder.exists() or folder.is_symlink():raise RuntimeError('Backup path exists')
    folder.mkdir(mode=0o700)
    original=folder/'previous.php'
    with original.open('xb') as f:f.write(old);f.flush();os.fsync(f.fileno())
    os.chmod(original,0o600)
    meta={'before':sha(old),'after':sha(new),'mode':mode}
    (folder/'manifest.json').write_text(json.dumps(meta))
    if sha(TARGET.read_bytes())!=meta['before']:raise RuntimeError('Race before commit')
    try:
        atomic(TARGET,new,mode)
        if sha(TARGET.read_bytes())!=meta['after']:raise RuntimeError('New PHP hash mismatch')
    except Exception:
        if sha(TARGET.read_bytes())==meta['after']:atomic(TARGET,old,mode)
        raise
    print('MPW_EDUCATION_META_ONLY_INSTALLED=PASS NO_ROUTE_CHANGES=true NO_PASSENGER_RESTART=true BACKUP='+str(folder),flush=True)
def rollback(run):
    folder=backup(run)
    if not folder.is_dir() or folder.is_symlink():
        print('MPW_EDUCATION_META_NO_INSTALL')
        return
    data=json.loads((folder/'manifest.json').read_text())
    old=(folder/'previous.php').read_bytes()
    if sha(old)!=data['before']:raise RuntimeError('Corrupted backup')
    actual=sha(TARGET.read_bytes())
    if actual==data['before']:return
    if actual!=data['after']:raise RuntimeError('Concurrent update; refuse rollback')
    atomic(TARGET,old,data['mode'])
    print('MPW_EDUCATION_META_ROLLBACK=PASS',flush=True)
def selftest():
    assert len(OLD_SHA)==64
    assert ROUTE_MARK and len(ROUTE_MARK)>18
    print('MPW_EDUCATION_META_SAFETY_SELFTEST=PASS')
if __name__=='__main__':
    a=sys.argv[1] if len(sys.argv)>1 else ''
    if a=='selftest':selftest()
    elif a=='audit' and len(sys.argv)==4:
        old,new,mode=prepare(sys.argv[2],sys.argv[3])
        print('MPW_EDUCATION_META_PREFLIGHT=PASS '+sha(old)+' -> '+sha(new))
    elif a=='install' and len(sys.argv)==4:install(sys.argv[2],sys.argv[3])
    elif a=='rollback' and len(sys.argv)==3:rollback(sys.argv[2])
    else:raise SystemExit('selftest | audit RUN SHA | install RUN SHA | rollback RUN')
