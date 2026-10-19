"""Enable short-lived HSTS only inside MojPlayWin's own Passenger process.

This does not modify shared Django settings or other websites' WSGI entrypoints.
"""
import ast
import fcntl
import hashlib
import os
import pathlib
import subprocess
import sys
import tempfile
import urllib.request
import time

APP=pathlib.Path("/home/zomorod2/mojplaywin.com")
WSGI=APP/"passenger_wsgi.py"
VAULT=pathlib.Path("/home/zomorod2/.mpw-commerce-two-books")
EXPECTED_SHA="36d419e86643edbe422a181259d304f3ff7f7c7be6740c1f376009765273d9ab"
MARKER="# Dedicated public site runtime; staging retains its independent safety checks."
INSERT="# Only this Passenger app uses Django HSTS; sibling sites retain their own policy.\nos.environ['SECURE_HSTS_SECONDS']='86400'\n"

def atomic_write(data):
    fd,tmp=tempfile.mkstemp(dir=str(APP),prefix=".mpw-main-hsts-")
    try:
        with os.fdopen(fd,"wb") as f:
            f.write(data);f.flush();os.fsync(f.fileno())
        os.chmod(tmp,WSGI.stat().st_mode & 0o777)
        os.replace(tmp,WSGI)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)

def test_isolated_process():
    code=r"""
import os,sys
from django.core import checks
os.chdir('/home/zomorod2/Saeit-staging')
sys.path.insert(0,os.getcwd())
os.environ['SECURE_HSTS_SECONDS']='86400'
os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings')
import django;django.setup()
from django.conf import settings
result=checks.run_checks(include_deployment_checks=True)
assert settings.SECURE_HSTS_SECONDS==86400
assert settings.SECURE_HSTS_INCLUDE_SUBDOMAINS is False
assert settings.SECURE_HSTS_PRELOAD is False
assert not [i for i in result if i.id=='security.W004']
print('MPW_DJANGO_HSTS_WARNING=RESOLVED')
"""
    p=subprocess.run([sys.executable,"-c",code],cwd="/home/zomorod2/Saeit-staging",capture_output=True,text=True,timeout=35)
    if p.returncode or "MPW_DJANGO_HSTS_WARNING=RESOLVED" not in p.stdout:
        raise RuntimeError("Django main-only HSTS settings verification failed")

def test_https():
    request=urllib.request.Request("https://mojplaywin.com/store/",headers={
        "Cache-Control":"no-store","User-Agent":"MojPlayWin-HSTS-release-readiness/1"})
    with urllib.request.urlopen(request,timeout=12) as response:
        assert response.status==200
        assert "max-age=86400" in response.headers.get("Strict-Transport-Security","")
        assert response.read(120000).decode("utf8","replace").count('class="mpw-crypto-buy"')==2

def main():
    assert APP.is_dir() and VAULT.is_dir()
    assert WSGI.is_file() and not WSGI.is_symlink()
    with (VAULT/"main-hsts-lock").open("a+") as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        raw=WSGI.read_bytes()
        assert hashlib.sha256(raw).hexdigest()==EXPECTED_SHA, "Main Passenger entrypoint changed"
        orig=raw.decode("utf8")
        assert orig.count(MARKER)==1
        assert "SECURE_HSTS_SECONDS" not in orig
        new=orig.replace(MARKER,INSERT+MARKER,1).encode("utf8")
        ast.parse(new.decode("utf8"))
        backup=VAULT/("original-main-passenger-"+EXPECTED_SHA[:20]+".bak")
        if backup.exists():
            assert backup.read_bytes()==raw
        else:
            fd=os.open(str(backup),os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
            with os.fdopen(fd,"wb") as f:
                f.write(raw);f.flush();os.fsync(f.fileno())
        try:
            atomic_write(new)
            test_isolated_process()
            (APP/"tmp/restart.txt").touch(mode=0o600)
            for tries in range(4):
                try:
                    test_https()
                    break
                except Exception:
                    if tries==3:raise
                    time.sleep(2)
            print("MPW_PASSENGER_HSTS=PASS;main_only=true;django_warning_resolved=true;payments_untouched=true",flush=True)
        except Exception:
            if WSGI.read_bytes()==new:
                atomic_write(raw)
                (APP/"tmp/restart.txt").touch(mode=0o600)
            print("MPW_PASSENGER_HSTS=ROLLBACK",flush=True)
            raise

if __name__=="__main__":main()
