"""Scope a strict hash-based CSP to authenticated two-book checkout pages only."""
import ast
import hashlib
import os
import pathlib
import re
import subprocess
import sys
import tempfile
import fcntl

ROOT=pathlib.Path("/home/zomorod2/Saeit-staging")
PRIVATE=pathlib.Path("/home/zomorod2/.mpw-commerce-two-books")
SOURCE=ROOT/"mpw_commerce/product_checkout_page.py"
EXPECTED_SHA="28f4934a8f8c15b367eda5f8cdd32d941d32f20c64e5ba06adb4cb2294c03106"

HELPER=r'''
def _apply_two_book_strict_csp(response):
    """Allow exactly the hashed, server-rendered script and style elements."""
    import base64
    import hashlib
    import re
    body = response.content
    scripts = re.findall(rb"<script(?:\s[^>]*)?>(.*?)</script\s*>", body, re.I | re.S)
    styles = re.findall(rb"<style(?:\s[^>]*)?>(.*?)</style\s*>", body, re.I | re.S)
    if len(scripts) != 1 or len(styles) != 1 or b'<meta charset="utf-8">' not in body:
        raise RuntimeError("Checkout markup changed; CSP cannot be safely hashed")
    def source_hash(raw):
        return "'sha256-" + base64.b64encode(hashlib.sha256(raw).digest()).decode("ascii") + "'"
    policy = (
        "default-src 'none'; "
        "script-src 'self' " + source_hash(scripts[0]) + "; "
        "style-src 'self' " + source_hash(styles[0]) + "; "
        "connect-src 'self'; img-src 'self' data:; "
        "font-src 'self' data:; form-action 'self'; "
        "base-uri 'self'; object-src 'none'; "
        "upgrade-insecure-requests"
    )
    tag = ('<meta http-equiv="Content-Security-Policy" content="' +
           policy + '">').encode("ascii")
    response.content = body.replace(b'<meta charset="utf-8">',
                                    b'<meta charset="utf-8">\n' + tag, 1)
    response["X-Robots-Tag"] = "noindex, nofollow"
    return response
'''

def safe_write(data):
    fd,temp=tempfile.mkstemp(dir=str(SOURCE.parent),prefix=".mpw-strict-csp-")
    try:
        with os.fdopen(fd,"wb") as stream:
            stream.write(data);stream.flush();os.fsync(stream.fileno())
        os.chmod(temp,SOURCE.stat().st_mode & 0o777)
        os.replace(temp,SOURCE)
    finally:
        if os.path.exists(temp):os.unlink(temp)

def live_checkout_smoke():
    payload=r'''
import os,sys,re,base64,hashlib,json
os.chdir("/home/zomorod2/Saeit-staging");sys.path.insert(0,os.getcwd())
os.environ.setdefault("DJANGO_SETTINGS_MODULE","config.settings")
import django;django.setup()
from django.test import RequestFactory
from core.models import Product
from mpw_commerce.product_checkout_page import product_checkout_page
for pk in (72,225):
    p=Product.objects.select_related("owner").get(pk=pk)
    req=RequestFactory().get("/commerce/book/"+str(pk)+"/",secure=True,HTTP_HOST="mojplaywin.com")
    req.user=p.owner
    response=product_checkout_page(req,pk)
    html=response.content
    assert response.status_code==200
    assert response["Cache-Control"].find("no-store")>=0
    assert response.get("X-Robots-Tag")=="noindex, nofollow"
    assert html.count(b'http-equiv="Content-Security-Policy"')==1
    policy=re.search(rb'<meta http-equiv="Content-Security-Policy" content="([^"]+)">',html)
    assert policy and b"default-src 'none'" in policy.group(1)
    assert b"connect-src 'self'" in policy.group(1)
    for tag in (b"script",b"style"):
        contents=re.findall(b"<"+tag+b"(?:\\s[^>]*)?>(.*?)</"+tag+b"\\s*>",html,re.I|re.S)
        assert len(contents)==1
        key=b"'sha256-"+base64.b64encode(hashlib.sha256(contents[0]).digest())+b"'"
        assert key in policy.group(1)
    assert b"Ethereum mainnet" in html and b"TRON mainnet" in html
    print("MPW_STRICT_CSP_CHECKOUT="+json.dumps({"book_id":pk,"status":response.status_code,
       "inline_script_hash_verified":True,"inline_style_hash_verified":True,
       "wallet_options_present":True}),flush=True)
'''
    result=subprocess.run([sys.executable,"-c",payload],cwd=str(ROOT),capture_output=True,text=True,timeout=45)
    if result.returncode or result.stdout.count("MPW_STRICT_CSP_CHECKOUT=")!=2:
        raise RuntimeError("Checkout CSP release validation failed")
    for line in result.stdout.splitlines():
        if line.startswith("MPW_STRICT_CSP_CHECKOUT="):print(line,flush=True)

def main():
    assert ROOT.is_dir() and PRIVATE.is_dir() and not ROOT.is_symlink()
    assert SOURCE.is_file() and not SOURCE.is_symlink()
    with (PRIVATE/"csp-scoped-release.lock").open("a+") as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        original=SOURCE.read_bytes()
        if hashlib.sha256(original).hexdigest()!=EXPECTED_SHA:
            raise RuntimeError("Checkout view differs from audited source")
        code=original.decode("utf8")
        needle='    return render(request, "mpw_commerce/product_checkout.html", {'
        if code.count(needle)!=1:
            raise RuntimeError("Cannot safely identify checkout render")
        code=code.replace(
            "from decimal import Decimal\n",
            "from decimal import Decimal\n"+HELPER+"\n",1)
        code=code.replace(needle,
            '    response = render(request, "mpw_commerce/product_checkout.html", {',1)
        tail='        "discount_percent": discount_percent,\n    })'
        if code.count(tail)!=1:
            raise RuntimeError("Checkout return block drift")
        code=code.replace(tail,
            '        "discount_percent": discount_percent,\n    })\n    return _apply_two_book_strict_csp(response)',1)
        compiled=code.encode("utf8")
        ast.parse(code)
        backup=PRIVATE/("checkout-view-"+EXPECTED_SHA[:19]+".bak")
        if backup.exists():
            assert backup.read_bytes()==original
        else:
            fd=os.open(str(backup),os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
            with os.fdopen(fd,"wb") as stream:
                stream.write(original);stream.flush();os.fsync(stream.fileno())
        try:
            safe_write(compiled)
            live_checkout_smoke()
            site=pathlib.Path("/home/zomorod2/mojplaywin.com")
            assert "PassengerAppRoot /home/zomorod2/mojplaywin.com" in (site/".htaccess").read_text("utf8","replace")
            (site/"tmp/restart.txt").touch(mode=0o600)
            print("MPW_CSP_RELEASE=SUCCESS;books=72,225;other_hosts_unmodified=true;money_untouched=true",flush=True)
        except Exception:
            if SOURCE.read_bytes()==compiled:
                safe_write(original)
            print("MPW_CSP_RELEASE=ROLLED_BACK",flush=True)
            raise

if __name__=="__main__":main()
