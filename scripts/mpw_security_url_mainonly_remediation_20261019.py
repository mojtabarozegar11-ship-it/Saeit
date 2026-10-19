"""Only MojPlayWin: Apache TLS/content policy + remove duplicate crypto URL include.
Atomic backups, post-deploy Django/HTTP tests, full rollback on failed tests.
"""
import hashlib
import os
import pathlib
import subprocess
import sys
import tempfile
import time
import urllib.request
import urllib.error

APP=pathlib.Path("/home/zomorod2/mojplaywin.com")
CODE=pathlib.Path("/home/zomorod2/Saeit-staging")
VAULT=pathlib.Path("/home/zomorod2/.mpw-commerce-two-books")
APACHE=APP/".htaccess"
URLS=CODE/"config/urls.py"
OLD_APACHE_SHA="571b920aa3ff59ca52d25dc5091a3c2477d9b9eed18d497ea78cb5c4efd2b028"
OLD_URLS_SHA="0419665105ecc50c562bd693d3c5def691d1b504e12e130233fbb5463bfec032"
TAG="MPW_MAIN_SHOP_SECURITY_HEADERS_20261019"
DUP='# MPW_TWO_BOOKS_GATED_COMMERCE_ROUTES_V1\nurlpatterns += [path("", include("mpw_commerce.urls"))]\n'
ADD=(f"\n# {TAG} BEGIN\n"
     "<IfModule mod_setenvif.c>\n"
     "SetEnvIfNoCase Host \"^(www\\\\.)?mojplaywin\\\\.com$\" MPW_MAIN_STORE_HOST=1\n"
     "</IfModule>\n"
     "<IfModule mod_headers.c>\n"
     "Header always set Strict-Transport-Security \"max-age=86400\" env=MPW_MAIN_STORE_HOST\n"
     "Header always set Content-Security-Policy \"base-uri 'self'; object-src 'none'; frame-ancestors 'none'; upgrade-insecure-requests\" env=MPW_MAIN_STORE_HOST\n"
     "</IfModule>\n"
     f"# {TAG} END\n")
# Use unambiguous host regex with single regex escaping in file.
ADD=ADD.replace("www\\\\.", "www\\.").replace("mojplaywin\\\\.", "mojplaywin\\.")

def digest(data):
    return hashlib.sha256(data).hexdigest()

def atomically_replace(path,data):
    mode=path.stat().st_mode & 0o777
    fd, tmp=tempfile.mkstemp(dir=str(path.parent),prefix=".mpw-shop-sec-")
    try:
        with os.fdopen(fd,"wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.chmod(tmp,mode)
        os.replace(tmp,path)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)

def original_backup(label,data):
    p=VAULT/(label+"-"+digest(data)[:20]+".bak")
    if p.exists():
        if p.read_bytes()!=data: raise RuntimeError("Unexpected backup collision")
    else:
        fd=os.open(str(p),os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
        with os.fdopen(fd,"wb") as f:
            f.write(data);f.flush();os.fsync(f.fileno())

def reload_main_only():
    h=(APP/".htaccess").read_text("utf8","replace")
    w=(APP/"passenger_wsgi.py").read_text("utf8","replace")
    assert "PassengerAppRoot /home/zomorod2/mojplaywin.com" in h
    assert "APP='/home/zomorod2/Saeit-staging'" in w
    restart=APP/"tmp/restart.txt"
    assert restart.parent.is_dir() and not restart.parent.is_symlink()
    restart.touch(mode=0o600)

def django_check():
    code=r"""
import os,sys
os.chdir('/home/zomorod2/Saeit-staging')
sys.path.insert(0,os.getcwd())
os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings')
import django;django.setup()
from django.core import checks
from django.urls import resolve,reverse
r=checks.run_checks()
assert not [w for w in r if w.id=='urls.W005'],[w.id for w in r]
for url in ['/commerce/book/72/','/commerce/book/225/','/commerce/checkout/order/']:
    assert resolve(url).namespaces==['mpw_commerce']
assert reverse('mpw_commerce:book',kwargs={'pk':72})=='/commerce/book/72/'
print('MPW_COMMERCE_URL_NAMESPACE=UNIQUE')
"""
    job=subprocess.run([sys.executable,"-c",code],cwd=str(CODE),capture_output=True,text=True,timeout=30)
    if job.returncode or "MPW_COMMERCE_URL_NAMESPACE=UNIQUE" not in job.stdout:
        raise RuntimeError("Django unique URL routing check failed")

def http_assert():
    for trial in range(6):
        time.sleep(2)
        details=[]
        try:
            for path in ("/store/","/accounts/login/","/commerce/book/72/"):
                req=urllib.request.Request('https://mojplaywin.com'+path,headers={"Cache-Control":"no-cache","User-Agent":"MPW-Shop-Security-Release-Test"})
                with urllib.request.urlopen(req,timeout=12) as response:
                    if response.status!=200:raise RuntimeError("Live page unhealthy")
                    sts=response.headers.get("Strict-Transport-Security","")
                    csp=response.headers.get("Content-Security-Policy","")
                    if "max-age=86400" not in sts or "object-src 'none'" not in csp:
                        raise RuntimeError("Security headers absent from live application")
                    if path=="/store/":
                        html=response.read(120000).decode("utf8","replace")
                        if html.count('class="mpw-crypto-buy"')!=2:
                            raise RuntimeError("Customer buy links missing")
                    details.append(path)
            if len(details)==3:return
        except Exception:
            if trial==5:raise
    raise RuntimeError("Public header acceptance did not pass")

def main():
    os.umask(0o077)
    assert APP.is_dir() and CODE.is_dir() and VAULT.is_dir()
    assert APP.resolve()==pathlib.Path("/home/zomorod2/mojplaywin.com")
    for p in (APACHE,URLS):
        assert p.is_file() and not p.is_symlink()
    import fcntl
    with (VAULT/"security-remediation.lock").open("a+") as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        old_a=APACHE.read_bytes()
        old_u=URLS.read_bytes()
        if digest(old_a)!=OLD_APACHE_SHA or digest(old_u)!=OLD_URLS_SHA:
            raise RuntimeError("Source changed from inspected baseline; no write performed")
        sa=old_a.decode("utf8")
        su=old_u.decode("utf8")
        if TAG in sa or su.count(DUP)!=1:
            raise RuntimeError("Unexpected duplicate patch or URL drift")
        new_a=(sa+ADD).encode("utf8")
        new_u=su.replace(DUP,"").encode("utf8")
        import ast
        ast.parse(new_u.decode("utf8"))
        original_backup("main-htaccess",old_a)
        original_backup("commerce-urls",old_u)
        try:
            atomically_replace(APACHE,new_a)
            atomically_replace(URLS,new_u)
            django_check()
            reload_main_only()
            http_assert()
            print("MPW_SECURITY_FIX=PASS;hsts=86400;csp=enabled;duplicate_routes=removed;books_untouched=true",flush=True)
        except Exception as e:
            if APACHE.read_bytes()==new_a:atomically_replace(APACHE,old_a)
            if URLS.read_bytes()==new_u:atomically_replace(URLS,old_u)
            reload_main_only()
            print("MPW_SECURITY_ROLLBACK=APPLIED;cause="+type(e).__name__,flush=True)
            raise

if __name__=="__main__":main()
