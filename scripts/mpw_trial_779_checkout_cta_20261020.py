#!/usr/bin/env python3
"""Main-host-only MojPlayWin trial product CTA, reversible template-only patch."""
import hashlib
import json
import os
import pwd
import stat
import sys
import tempfile
from pathlib import Path

ROOT=Path("/home/zomorod2/Saeit-staging")
TARGET=ROOT/"core/templates/brands/mojplaywin/product.html"
WSGI=Path("/home/zomorod2/mojplaywin.com/passenger_wsgi.py")
BACKUP=Path("/home/zomorod2/.private_mojplaywin_main_agents")
RUN="mpw-native-trx-micro-trial-cta-20261020-v1"
SOURCE=BACKUP/(RUN+".bak")
MANIFEST=BACKUP/(RUN+".json")
OLD="{% if product.pk == 72 or product.pk == 225 %}"
NEW=('{% if product.pk == 779 %}\n'
     '<p>This is a one-page USD 0.03 digital PDF trial. Sign in, verify your own TRON wallet, '
     'and pay only the exact TRX amount shown on your order-specific invoice. '
     'Private download is unlocked only after verified blockchain settlement.</p>\n'
     '<a class="primary" href="/commerce/book/779/">Buy trial PDF with TRX</a>\n'
     '<a href="/accounts/register/">New customer? Create an account</a>\n'
     '{% elif product.pk == 72 or product.pk == 225 %}')

def digest(b):return hashlib.sha256(b).hexdigest()

def guard():
    if pwd.getpwuid(os.getuid()).pw_name != "zomorod2":
        raise RuntimeError("Wrong cPanel user")
    for path in (ROOT,BACKUP):
        if not path.is_dir() or path.is_symlink():
            raise RuntimeError("Untrusted application or backup directory")
    if stat.S_IMODE(BACKUP.stat().st_mode)&0o077:
        raise RuntimeError("Backup directory is not private")
    if not TARGET.is_file() or TARGET.is_symlink() or TARGET.parent.is_symlink():
        raise RuntimeError("Template location unsafe")
    if not WSGI.is_file() or WSGI.is_symlink() or "APP='/home/zomorod2/Saeit-staging'" not in WSGI.read_text('utf8','replace'):
        raise RuntimeError("Incorrect Passenger application root")

def transformed(original):
    text=original.decode("utf8")
    if text.count(OLD)!=1 or "product.pk == 779" in text:
        raise RuntimeError("Unexpected existing store template: no rewrite")
    return text.replace(OLD,NEW,1).encode("utf8")

def compile_template(candidate):
    os.chdir(ROOT);sys.path.insert(0,str(ROOT))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE","config.settings")
    import django;django.setup()
    from django.template import Template
    from django.template.loader import get_template
    from django.conf import settings
    # Compile against the live Django template engine, not a standalone substitute.
    engine=settings.TEMPLATES
    assert len(engine)>0
    from django.template import engines
    engines["django"].from_string(candidate.decode("utf8"))
    assert '<a class="primary" href="/commerce/book/779/">' in candidate.decode("utf8")

def report(tag,item):
    print(tag+"="+json.dumps(item,sort_keys=True,default=str),flush=True)

def preview():
    guard()
    before=TARGET.read_bytes()
    after=transformed(before)
    compile_template(after)
    report("MPW_MICRO_CTA_PREVIEW",{"changed_file":"core/templates/brands/mojplaywin/product.html",
        "before_sha":digest(before),"after_sha":digest(after),
        "trial_id":779,"main_store_only":True,"siblings_untouched":True})

def atomic(data):
    fd,name=tempfile.mkstemp(prefix=".mpw-trial-cta-",dir=str(TARGET.parent))
    try:
        os.fchmod(fd,stat.S_IMODE(TARGET.stat().st_mode))
        with os.fdopen(fd,'wb') as f:
            f.write(data);f.flush();os.fsync(f.fileno())
        os.replace(name,TARGET)
    finally:
        if os.path.exists(name):os.unlink(name)

def publish():
    guard()
    before=TARGET.read_bytes()
    after=transformed(before)
    compile_template(after)
    if SOURCE.exists() or MANIFEST.exists() or SOURCE.is_symlink() or MANIFEST.is_symlink():
        raise RuntimeError("Release backup already exists")
    with SOURCE.open('xb') as f:
        os.fchmod(f.fileno(),0o600);f.write(before);f.flush();os.fsync(f.fileno())
    info={"run":RUN,"before":digest(before),"after":digest(after),
          "path":"core/templates/brands/mojplaywin/product.html","trial_id":779}
    with MANIFEST.open('x',encoding='utf8') as f:
        os.fchmod(f.fileno(),0o600);json.dump(info,f);f.flush();os.fsync(f.fileno())
    if digest(TARGET.read_bytes())!=info["before"]:
        raise RuntimeError("Concurrent edit detected")
    atomic(after)
    if digest(TARGET.read_bytes())!=info["after"]:
        raise RuntimeError("Template hash mismatch")
    report("MPW_MICRO_CTA_PUBLISHED",{"file":info["path"],"trial_id":779,
      "no_payment_or_product_write":True,"no_passenger_restart":True})

def verify():
    guard()
    if not SOURCE.is_file() or not MANIFEST.is_file() or SOURCE.is_symlink() or MANIFEST.is_symlink():
        raise RuntimeError("Missing sealed release evidence")
    info=json.loads(MANIFEST.read_text('utf8'))
    before=SOURCE.read_bytes()
    if info["run"]!=RUN or info["path"]!="core/templates/brands/mojplaywin/product.html":
        raise RuntimeError("Unexpected release manifest")
    if digest(before)!=info["before"] or digest(TARGET.read_bytes())!=info["after"]:
        raise RuntimeError("Live template not release hash")
    if digest(transformed(before))!=info["after"]:
        raise RuntimeError("Template changed outside allowed line")
    compile_template(TARGET.read_bytes())
    from django.test import Client
    # Django internal fresh process: prove only sample 779 has new checkout CTA.
    client=Client(raise_request_exception=True)
    statuses={}
    for pk in (72,225,779):
        resp=client.get("/store/product/%s/" % pk,secure=True,HTTP_HOST="mojplaywin.com")
        html=resp.content.decode("utf8","replace")
        statuses[pk]=resp.status_code
        if resp.status_code!=200:raise RuntimeError("Product route failed")
        if ("/commerce/book/779/" in html) != (pk==779):
            raise RuntimeError("CTA leaked to another book or missing for test")
    report("MPW_MICRO_CTA_VERIFIED",{"product_statuses":statuses,
      "exclusive_trial_cta":True,"url":"https://mojplaywin.com/store/product/779/",
      "checkout":"/commerce/book/779/"})

def rollback():
    guard()
    if not SOURCE.is_file() or not MANIFEST.is_file():raise RuntimeError("Missing backup")
    info=json.loads(MANIFEST.read_text('utf8'))
    original=SOURCE.read_bytes()
    if digest(TARGET.read_bytes())!=info["after"] or digest(original)!=info["before"]:
        raise RuntimeError("Concurrent edit; refusing rollback")
    atomic(original)
    print("MPW_MICRO_CTA_ROLLBACK=PASS")

def selftest():
    assert OLD in NEW and "product.pk == 779" in NEW
    test=b"prefix "+OLD.encode()+b" suffix"
    assert transformed(test).count(b"/commerce/book/779/")==1
    assert b"product.pk == 72 or product.pk == 225" in transformed(test)
    print("MPW_MICRO_CTA_SELFTEST=PASS")

if __name__=="__main__":
    tasks={"selftest":selftest,"preview":preview,"publish":publish,
           "verify":verify,"rollback":rollback}
    if len(sys.argv)!=2 or sys.argv[1] not in tasks:
        raise SystemExit("selftest|preview|publish|verify|rollback")
    tasks[sys.argv[1]]()
