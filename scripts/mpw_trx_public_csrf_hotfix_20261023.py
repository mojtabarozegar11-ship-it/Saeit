"""Repair same-origin checkout CSRF referrer behavior with rollback backup."""
import hashlib,os,pwd,shutil,stat,sys,tempfile
from pathlib import Path

APP=Path('/home/zomorod2/Saeit-staging')
PUBLIC=Path('/home/zomorod2/mojplaywin.com')
BACKUP_ROOT=Path('/home/zomorod2/.local/share/mpw-trx-rollbacks')
REL='services/mpw_trx_commercial_web.py'
OLD_SHA256='a4ccf0fae59672f13b025804d355bb9f2908dbfce409b3ad6ebac85240f9dd70'
NEW_SHA256='706d140d35f3462b6b862f909dc02f6557d601dcc50d5d1fc53d0e1dfffc16ac'
MARK='MPW_PUBLIC_TRX_CUSTOMERS_20261023'

def digest(data): return hashlib.sha256(data).hexdigest()
def put(path,data):
    if path.is_symlink(): raise RuntimeError('Refuse symlink target')
    tmp=path.with_name(path.name+'.csrf-hotfix-tmp')
    if tmp.exists() or tmp.is_symlink(): raise RuntimeError('Concurrent hotfix detected')
    tmp.write_bytes(data)
    os.chmod(tmp,stat.S_IMODE(path.stat().st_mode))
    os.replace(tmp,path)

def assert_release_state():
    if pwd.getpwuid(os.getuid()).pw_name!='zomorod2': raise RuntimeError('Wrong cPanel account')
    for p in (APP,PUBLIC,BACKUP_ROOT):
        if p.is_symlink() or not p.is_dir(): raise RuntimeError('Expected production directories missing or unsafe')
    if "APP='/home/zomorod2/Saeit-staging'" not in (PUBLIC/'passenger_wsgi.py').read_text():
        raise RuntimeError('Passenger app root changed')
    settings=(APP/'config/settings.py').read_text()
    if MARK not in settings or 'MPW_WALLETLESS_TRX_PUBLIC_RELEASE_AUTHORIZED = True' not in settings or 'MPW_TRX_PUBLIC_PRODUCT_IDS = (72, 225, 879)' not in settings:
        raise RuntimeError('Public release authorization or allowlist is not installed')
    if 'MPW_WALLETLESS_TRX_PUBLIC_ENABLED = _mpw_trx_os.environ.get("MPW_WALLETLESS_TRX_PUBLIC_ENABLED", "1") == "1"' not in settings:
        raise RuntimeError('Public checkout flag is not active')

def verify_runtime():
    code='''from django.http import HttpResponse\nfrom services.mpw_trx_commercial_web import _nocache\nr=_nocache(HttpResponse("ok"))\nassert r["Referrer-Policy"]=="same-origin"\nassert r["Cache-Control"]=="private, no-store, max-age=0"\nprint("PUBLIC_TRX_CSRF_SAME_ORIGIN_REFERRER=PASS")\n'''
    p=subprocess_run([str(APP.parent/'virtualenv'/'Saeit-staging'/'3.11'/'bin'/'python'),'-B','-c',code],cwd=APP)
    if p.returncode or 'PUBLIC_TRX_CSRF_SAME_ORIGIN_REFERRER=PASS' not in p.stdout:
        raise RuntimeError('Live Django response header verification failed: '+p.stderr[-1000:])
    print(p.stdout.strip())

def subprocess_run(args,*,cwd):
    import subprocess
    return subprocess.run(args,cwd=cwd,capture_output=True,text=True,timeout=35)

def main():
    if len(sys.argv)!=2: raise SystemExit('usage: hotfix.py SOURCE_DIR')
    source=Path(sys.argv[1])
    assert_release_state()
    target=APP/REL
    proposed=(source/REL).read_bytes()
    compile(proposed.decode('utf8'),REL,'exec')
    if digest(proposed)!=NEW_SHA256: raise RuntimeError('Unexpected release source hash')
    current=target.read_bytes()
    if digest(current)==NEW_SHA256:
        verify_runtime();print('PUBLIC_TRX_CSRF_HOTFIX=ALREADY_ACTIVE');return
    if digest(current)!=OLD_SHA256: raise RuntimeError('Live checkout module changed independently')
    backup=Path(tempfile.mkdtemp(prefix='trx-public-csrf-',dir=BACKUP_ROOT));os.chmod(backup,0o700)
    saved=backup/Path(REL);saved.parent.mkdir(parents=True,exist_ok=True)
    saved.write_bytes(current);os.chmod(saved,0o600)
    try:
        if target.read_bytes()!=current: raise RuntimeError('Concurrent source edit')
        put(target,proposed)
        if digest(target.read_bytes())!=NEW_SHA256: raise RuntimeError('Installed source hash mismatch')
        (APP/'tmp').mkdir(exist_ok=True);(APP/'tmp/restart.txt').touch()
        (PUBLIC/'tmp').mkdir(exist_ok=True);(PUBLIC/'tmp/restart.txt').touch()
        verify_runtime()
        print('PUBLIC_TRX_CSRF_HOTFIX=ACTIVE; CSRF_ENFORCEMENT=UNCHANGED; CROSS_ORIGIN_REFERRER=SUPPRESSED; BACKUP='+backup.name)
    except BaseException:
        if target.is_file() and not target.is_symlink() and digest(target.read_bytes())==NEW_SHA256:
            put(target,current)
            (APP/'tmp/restart.txt').touch();(PUBLIC/'tmp/restart.txt').touch()
            print('PUBLIC_TRX_CSRF_HOTFIX=ROLLED_BACK')
        raise

if __name__=='__main__':main()
