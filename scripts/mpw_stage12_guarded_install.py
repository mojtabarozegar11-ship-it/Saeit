"""Guarded live install of tested buyer-order schema. NO payment activation.

Only MojPlayWin, only a package already installed in disabled mode.
No product, order, wallet or payment flag is activated by this operation.
"""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import os
import pwd
import shutil
import subprocess
import sys
import tempfile


HOME=Path("/home/zomorod2")
SITE=HOME/"Saeit-staging"
STAGING=HOME/".mpw-cart-stage12"
VENV=HOME/"virtualenv/Saeit-staging/3.11/bin/python"
EXPECTED=(
    "mpw_commerce/models.py",
    "mpw_commerce/urls.py",
    "mpw_commerce/buyer_orders.py",
    "mpw_commerce/migrations/0003_commerceorderrequest.py",
)


def demand(test,message):
    if not test:
        raise RuntimeError(message)


def run(args):
    env=os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"]="1"
    env["DJANGO_SETTINGS_MODULE"]="config.settings"
    v=subprocess.run(args,cwd=SITE,env=env,capture_output=True,
                     text=True,timeout=150,check=False)
    if v.returncode:
        raise RuntimeError("Isolated Django verification failed; no checkout release")
    return v.stdout


def atomic(path,content):
    fd,tmp=tempfile.mkstemp(prefix=".mpw-stage12-",dir=str(path.parent))
    try:
        with os.fdopen(fd,"wb") as f:
            f.write(content);f.flush();os.fsync(f.fileno())
        os.chmod(tmp,path.stat().st_mode & 0o777 if path.exists() else 0o640)
        os.replace(tmp,path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def main():
    demand(pwd.getpwuid(os.getuid()).pw_name=="zomorod2","Wrong owner")
    demand(SITE.is_dir() and not SITE.is_symlink(),"Unexpected application")
    demand(VENV.is_file(),"No current virtualenv")
    demand((SITE/"mpw_commerce/.mpw_inert_release_marker").read_text().strip()
           =="MPW-STAGE4-20261015","Installed commerce version changed")
    source=STAGING/"source"
    demand(source.is_dir() and not source.is_symlink(),"Missing isolated staging")
    for rel in EXPECTED:
        f=source/rel
        demand(f.is_file() and not f.is_symlink(),"Missing approved artifact")
        demand(f.stat().st_size<150000,"Unexpected oversized source")
    for rel in EXPECTED[:2]:
        active=SITE/rel
        original=HOME/".mpw-commerce-stage3-20261015/code"/rel
        demand(active.is_file() and original.is_file(),"No original baseline")
        demand(hashlib.sha256(active.read_bytes()).digest()
               ==hashlib.sha256(original.read_bytes()).digest(),
               "Live commerce code changed since stage 4")
    for rel in EXPECTED[2:]:
        demand(not (SITE/rel).exists(),"Do not overwrite a new commerce file")
    recent=sorted((HOME/".mpw-private-db-backups").glob("*/manifest.json"),
                  key=lambda p:p.stat().st_mtime,reverse=True)
    demand(bool(recent),"Private backup not found")
    info=json.loads(recent[0].read_text())
    age=(datetime.now(timezone.utc)-
         datetime.fromisoformat(info["timestamp_utc"])).total_seconds()
    demand(0<=age<3600,"Fresh production SQL backup required")
    archive=recent[0].parent/"mysql-full.sql.gz"
    demand(archive.is_file() and hashlib.sha256(archive.read_bytes()).hexdigest()
           ==info["archive_sha256"],"Backup hash mismatch")
    demand("code_rollback_checksums" in info,"Missing source rollback manifest")
    os.environ["DJANGO_SETTINGS_MODULE"]="config.settings"
    import django
    django.setup()
    from django.conf import settings
    from django.db import connection
    from django.db.migrations.recorder import MigrationRecorder
    from django.urls import reverse
    demand("mpw_commerce" in settings.INSTALLED_APPS,"Commerce app not installed")
    demand(connection.vendor=="mysql","Not the verified MySQL database")
    demand(reverse("mpw_commerce:invoice")=="/commerce/checkout/invoice/",
           "Customer URLconf mismatch")
    demand(all(getattr(settings,k,False) is False for k in (
        "MPW_COMMERCE_RELEASE_READY",
        "MPW_COMMERCE_INVOICING_ENABLED",
        "MPW_COMMERCE_SETTLEMENT_ENABLED",
        "MPW_COMMERCE_REAL_RPC_ENABLED",
        "MPW_COMMERCE_CUSTOMER_HTTP_ENABLED",
        "MPW_COMMERCE_DOWNLOADS_ENABLED",
        "MPW_COMMERCE_AUTORECONCILE_ENABLED",
    )),"Checkout payment flags must remain off")
    migrations=MigrationRecorder(connection).applied_migrations()
    demand(("mpw_commerce","0002_buyerwalletchallenge") in migrations,
           "Existing commerce schema drift")
    demand(("mpw_commerce","0003_commerceorderrequest") not in migrations,
           "Schema already changed; refuse second deployment")

    checkpoint=STAGING/"rollback"
    demand(not checkpoint.exists(),"Existing deployment rollback source")
    checkpoint.mkdir(mode=0o700)
    for rel in EXPECTED[:2]:
        saved=checkpoint/rel
        saved.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(SITE/rel,saved)
        saved.chmod(0o600)
    for rel in EXPECTED:
        target=SITE/rel
        demand(not target.is_symlink(),"Symlink target forbidden")
        atomic(target,(source/rel).read_bytes())
    print("MPW_STAGE12_CODE_DEPLOYED_WITH_PREVIOUS_VERSION_SAVED=True")
    try:
        run([str(VENV),"-m","django","check"])
        run([str(VENV),"-m","django","makemigrations",
             "mpw_commerce","--check","--dry-run"])
        run([str(VENV),"-m","django","migrate","mpw_commerce","--noinput"])
        verify=r"""
import django
django.setup()
from django.conf import settings
from django.db import connection
from django.db.migrations.recorder import MigrationRecorder
from django.urls import reverse
from core.models import Order,PaymentIntent
from mpw_commerce.models import CommerceOrderRequest,CommerceInvoice,CommerceReceipt
assert ('mpw_commerce','0003_commerceorderrequest') in MigrationRecorder(connection).applied_migrations()
assert CommerceOrderRequest._meta.db_table in connection.introspection.table_names()
assert reverse('mpw_commerce:order')=='/commerce/checkout/order/'
assert all(getattr(settings,k,False) is False for k in (
'MPW_COMMERCE_RELEASE_READY','MPW_COMMERCE_INVOICING_ENABLED',
'MPW_COMMERCE_SETTLEMENT_ENABLED','MPW_COMMERCE_CUSTOMER_HTTP_ENABLED',
'MPW_COMMERCE_REAL_RPC_ENABLED','MPW_COMMERCE_DOWNLOADS_ENABLED'))
assert CommerceOrderRequest.objects.count()==0
assert CommerceInvoice.objects.count()==0
assert CommerceReceipt.objects.count()==0
print('MPW_STAGE12_CUSTOMER_ORDER_ROUTE_REGISTERED=True')
print('MPW_STAGE12_NO_REAL_CUSTOMER_SALES=True')
print('MPW_STAGE12_ALL_PAYMENT_FLAGS_OFF=True')
"""
        for line in run([str(VENV),"-c",verify]).splitlines():
            if line.startswith("MPW_STAGE12_"):
                print(line)
        # Restart only MojPlayWin's verified Passenger application.
        passenger=HOME/"mojplaywin.com"
        startup=passenger/"passenger_wsgi.py"
        demand(startup.is_file() and str(SITE) in startup.read_text(),
               "Unexpected Passenger Django mapping")
        restart=passenger/"tmp/restart.txt"
        demand(restart.parent.is_dir() and not restart.is_symlink(),
               "Passenger restart directory unavailable")
        restart.touch()
        print("MPW_STAGE12_PASSENGER_RESTART_REQUESTED=True")
    except Exception:
        # Maintain Django migration history if the schema was applied.
        # Disable the NEW buyer URL only, never drop possibly used tables.
        if (SITE/"mpw_commerce/urls.py").exists():
            atomic(SITE/"mpw_commerce/urls.py",
                   (checkpoint/"mpw_commerce/urls.py").read_bytes())
        print("MPW_STAGE12_BUYER_ORDER_ROUTE_REVERTED_ON_FAILURE=True")
        raise


if __name__=="__main__":
    main()
