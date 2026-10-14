"""Guarded release of ONLY the MojPlayWin merchant wallet proof page.

Run as cPanel user zomorod2 via verified VPS relay. This is NOT a checkout
release: no Product/Order status changes, payments, wallet operations or AI calls.
Preserves the active code/configuration in a private backup, requires a full
successful MySQL dump before changing any runtime settings, and can restore
those settings from the checkpoint. Never logs DB credentials.
"""
from pathlib import Path
from datetime import datetime, timezone
import argparse
import gzip
import json
import os
import shutil
import subprocess
import sys
import tempfile

HOME = Path("/home/zomorod2")
SITE = HOME / "Saeit-staging"
WSGI_ROOT = HOME / "mojplaywin.com"
STAGING = HOME / ".mpw-proof-drop" / "source"
BACKUPS = HOME / ".mpw-proof-backups"
POINTER = HOME / ".mpw-proof-drop" / "last-release-backup"
VENV = HOME / "virtualenv/Saeit-staging/3.11/bin/python"
CRYPTO = HOME / ".mpw-proof-crypto-py311/bin/python"
PROOF_APP = "mpw_native_checkout"
SETTINGS_MARKER = "# MPW_MERCHANT_WALLET_OWNERSHIP_ONLY_V1"
URL_MARKER = "# MPW_MERCHANT_WALLET_ROUTE_ONLY_V1"

SETTINGS_SNIPPET = """
# MPW_MERCHANT_WALLET_OWNERSHIP_ONLY_V1
MPW_MERCHANT_WALLET_PROOF_ENABLED = env.bool("MPW_MERCHANT_WALLET_PROOF_ENABLED", default=False)
MPW_WALLET_PROOF_OWNER_ID = env.int("MPW_WALLET_PROOF_OWNER_ID", default=0)
MPW_NATIVE_CRYPTO_HELPER_PYTHON = env("MPW_NATIVE_CRYPTO_HELPER_PYTHON", default="")
if MPW_MERCHANT_WALLET_PROOF_ENABLED:
    INSTALLED_APPS.append("mpw_native_checkout")
"""
URL_SNIPPET = """
# MPW_MERCHANT_WALLET_ROUTE_ONLY_V1
from django.conf import settings as mpw_wallet_settings
if getattr(mpw_wallet_settings, "MPW_MERCHANT_WALLET_PROOF_ENABLED", False) is True:
    urlpatterns += [path("", include("mpw_native_checkout.merchant_wallet_urls"))]
"""


def fail(message):
    raise RuntimeError(message)


def ensure_environment():
    import pwd
    if pwd.getpwuid(os.getuid()).pw_name != "zomorod2":
        fail("Wrong server user")
    for path in (SITE, WSGI_ROOT, STAGING, BACKUPS.parent):
        if not path.is_dir() or path.is_symlink():
            fail("Expected private deployment path missing")
    if not (WSGI_ROOT / "passenger_wsgi.py").is_file():
        fail("Passenger startup file missing")
    if not (WSGI_ROOT / ".htaccess").read_text().find(
            "PassengerAppRoot /home/zomorod2/mojplaywin.com") >= 0:
        fail("Domain Passenger root no longer matches verified mapping")
    start=(WSGI_ROOT / "passenger_wsgi.py").read_text()
    if "/home/zomorod2/Saeit-staging" not in start:
        fail("Active WSGI path changed; abort")
    for file in ("config/settings.py","config/urls.py",".env"):
        if not (SITE/file).is_file():
            fail("Active configuration missing")
    for file in ("models.py","wallet_ownership.py","merchant_wallet_views.py",
                 "merchant_wallet_urls.py","crypto_subprocess_verify.py",
                 "migrations/0003_merchantwalletchallenge_merchantwalletproof.py",
                 "templates/mpw_native_checkout/merchant_wallet_proof.html"):
        if not (STAGING/PROOF_APP/file).is_file():
            fail("Required release code incomplete")
    for program in (VENV, CRYPTO):
        if not program.is_file():
            fail("Required separate Python interpreter unavailable")


def run(args, *, cwd=SITE, env=None, stdout=None):
    result=subprocess.run(
        [str(x) for x in args],cwd=cwd,env=env,
        stdin=subprocess.DEVNULL,stdout=stdout or subprocess.PIPE,
        stderr=subprocess.PIPE,check=False,timeout=150,
    )
    if result.returncode:
        fail("Guarded subprocess failed: " + Path(str(args[0])).name)
    return result


def active_env():
    env=os.environ.copy()
    env["DJANGO_SETTINGS_MODULE"]="config.settings"
    env["PYTHONDONTWRITEBYTECODE"]="1"
    env["PYTHONPATH"]=str(SITE)
    return env


def backup_mysql(destination, connection_settings):
    db=connection_settings
    if "mysql" not in db["ENGINE"]:
        fail("Expected MySQL database missing")
    program=shutil.which("mysqldump") or shutil.which("mariadb-dump")
    if not program:
        fail("SQL backup client unavailable")
    cmd=[program,"--single-transaction","--quick","--skip-lock-tables",
         "--no-tablespaces","--default-character-set=utf8mb4",
         "--user="+str(db["USER"])]
    if db.get("HOST"):
        cmd.append("--host="+str(db["HOST"]))
    if db.get("PORT"):
        cmd.append("--port="+str(db["PORT"]))
    unix_socket=db.get("OPTIONS",{}).get("unix_socket")
    if unix_socket:
        cmd.append("--socket="+str(unix_socket))
    name=str(db["NAME"])
    if not name or name.startswith("-"):
        fail("Unsafe database name")
    cmd.append(name)
    env=os.environ.copy()
    env["MYSQL_PWD"]=str(db.get("PASSWORD",""))
    path=destination/"full-mysql-before-wallet-page.sql.gz"
    # Stream the dump through Python's compressor (passing a gzip fd straight
    # to mysqldump would silently bypass gzip, producing an invalid backup).
    with tempfile.TemporaryFile() as errors:
        proc=subprocess.Popen(
            cmd,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,
            stderr=errors,env=env,cwd=SITE,
        )
        try:
            with gzip.open(path,"wb",compresslevel=5) as archive:
                shutil.copyfileobj(proc.stdout,archive,length=1024*1024)
            exit_code=proc.wait(timeout=120)
        except Exception:
            proc.kill()
            proc.wait()
            raise
    path.chmod(0o600)
    if exit_code != 0 or path.stat().st_size < 512:
        fail("Database backup failed or incomplete")
    with gzip.open(path,"rb") as archived:
        head=archived.read(512)
    if b"--" not in head and b"CREATE" not in head:
        fail("SQL backup content is not recognizable")
    print("MYSQL_BACKUP_WRITTEN_PRIVATE_AND_GZIP_VERIFIED")


def copy_release(candidate):
    source=STAGING/PROOF_APP
    target=SITE/PROOF_APP
    if source.is_symlink() or target.is_symlink():
        fail("Unsafe module symlink")
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(source,target,ignore=shutil.ignore_patterns("__pycache__","*.pyc"))
    for p in target.rglob("*"):
        if p.is_file():
            p.chmod(0o640)
    # These are shared production checkout helpers. Preserve the active copies
    # even when this staging branch contains newer code; the proof page must
    # not replace code used by any existing payment path.
    for filename in ("mojplaywin_native_chain_verify.py","mojplaywin_purchase_events.py"):
        dest=SITE/"scripts"/filename
        if dest.is_symlink() or not dest.is_file():
            fail("Required active checkout helper missing; no replacement attempted")
    print("PROOF_MODULE_INSTALLED_ACTIVE_CHECKOUT_HELPERS_PRESERVED")


def write_atomic(path,text,permissions):
    import secrets
    temporary=path.with_name(path.name+"."+secrets.token_hex(8)+".tmp")
    with temporary.open("x",encoding="utf-8") as fh:
        fh.write(text)
        fh.flush()
        os.fsync(fh.fileno())
    temporary.chmod(permissions)
    temporary.replace(path)


def restart_passenger():
    target=WSGI_ROOT/"tmp"/"restart.txt"
    if not target.parent.is_dir() or target.parent.is_symlink():
        fail("Passenger restart directory missing")
    target.touch()


def restore(backup):
    if not backup.is_dir() or not str(backup.resolve()).startswith(str(BACKUPS.resolve())+"/"):
        fail("Unsafe rollback path")
    for name,original in (
        ("settings.py", SITE/"config/settings.py"),
        ("urls.py", SITE/"config/urls.py"),
        (".env", SITE/".env"),
    ):
        saved=backup/name
        if not saved.is_file():
            fail("Backup missing required configuration")
        shutil.copy2(saved,original)
    source=backup/"app_previous"
    dest=SITE/PROOF_APP
    if dest.exists():
        shutil.rmtree(dest)
    if source.is_dir():
        shutil.copytree(source,dest)
    restart_passenger()
    print("WALLET_PAGE_CONFIG_ROLLED_BACK_NO_ORDERS_CHANGED")


def activate():
    ensure_environment()
    BACKUPS.mkdir(mode=0o700,parents=True,exist_ok=True)
    checkpoint=BACKUPS/datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    checkpoint.mkdir(mode=0o700,exist_ok=False)
    for name,original in (
        ("settings.py",SITE/"config/settings.py"),
        ("urls.py",SITE/"config/urls.py"),
        (".env",SITE/".env"),
    ):
        shutil.copy2(original,checkpoint/name)
        (checkpoint/name).chmod(0o600)
    previous=SITE/PROOF_APP
    if previous.is_dir():
        shutil.copytree(previous,checkpoint/"app_previous",
                        ignore=shutil.ignore_patterns("__pycache__","*.pyc"))

    try:
        env=active_env()
        # Deliberately obtain credentials only inside this process.
        sys.path.insert(0,str(SITE))
        os.environ["DJANGO_SETTINGS_MODULE"]="config.settings"
        import django
        django.setup()
        from django.conf import settings
        from django.contrib.auth import get_user_model
        from core.models import Product
        from django.db import connection
        from django.db.migrations.recorder import MigrationRecorder
        owners=list(get_user_model().objects.filter(is_superuser=True,is_active=True)
                    .values_list("pk",flat=True))
        if len(owners)!=1 or not Product.objects.filter(pk=72,active=False).exists():
            fail("Ownership identity or inactive ebook release gate unexpectedly changed")
        recorder=MigrationRecorder(connection)
        if ("core","0039_educationassessment_educationattempt_and_more") not in recorder.applied_migrations():
            fail("Missing required existing Django schema")
        backup_mysql(checkpoint,settings.DATABASES["default"])
        copy_release(checkpoint)

        # Shadow settings imports the existing app but not its URLs or payments.
        shadow=HOME/".mpw-proof-shadow"
        shadow_settings=shadow/"shadow_settings.py"
        if not shadow_settings.is_file():
            fail("Reviewed shadow settings missing")
        env["DJANGO_SETTINGS_MODULE"]="shadow_settings"
        env["PYTHONPATH"]=str(shadow)+os.pathsep+str(SITE)
        run((VENV,"-m","django","check","--settings=shadow_settings"),env=env)
        run((VENV,"-m","django","migrate",PROOF_APP,
             "--settings=shadow_settings","--noinput"),env=env)
        print("PROOF_DATABASE_SCHEMA_CREATED_OWN_APP_ONLY")

        config=SITE/"config/settings.py"
        urls=SITE/"config/urls.py"
        settings_text=config.read_text()
        urls_text=urls.read_text()
        if SETTINGS_MARKER in settings_text or URL_MARKER in urls_text:
            fail("Existing merchant verification release marker found")
        write_atomic(config, settings_text+"\n"+SETTINGS_SNIPPET,0o640)
        write_atomic(urls, urls_text+"\n"+URL_SNIPPET,0o640)

        dot=SITE/".env"
        dot_lines=dot.read_text().splitlines()
        flags={
            "MPW_MERCHANT_WALLET_PROOF_ENABLED":"True",
            "MPW_WALLET_PROOF_OWNER_ID":str(owners[0]),
            "MPW_NATIVE_CRYPTO_HELPER_PYTHON":str(CRYPTO),
        }
        for key in flags:
            if any(line.strip().startswith(key+"=") for line in dot_lines):
                fail("Existing environment key requires manual review")
        dot_lines.extend(k+"="+v for k,v in flags.items())
        write_atomic(dot,"\n".join(dot_lines)+"\n",0o600)

        env=active_env()
        run((VENV,"-m","django","check"),env=env)
        # Process-local request test: authenticated owner only, HTTPS and
        # host-restricted. Does not save login state or make blockchain calls.
        code = """
from django.test import RequestFactory
from django.contrib.auth import get_user_model
from mpw_native_checkout.merchant_wallet_views import merchant_wallet_page
from django.urls import resolve
from django.conf import settings
from django.db import connection
from mpw_native_checkout.wallet_ownership import proven_assets
u=get_user_model().objects.filter(is_superuser=True,is_active=True).get()
r=RequestFactory().get('/merchant/wallet-proof/',secure=True,HTTP_HOST='mojplaywin.com')
r.user=u
assert resolve('/merchant/wallet-proof/').url_name=='page'
response=merchant_wallet_page(r)
assert response.status_code==200
assert b'ETH' in response.content and b'TRX' in response.content
assert proven_assets()=={'ETH':False,'TRX':False}
print('MERCHANT_ADMIN_PAGE_HTTPS_DJANGO_RENDER_OK')
"""
        run((VENV,"-c",
             "import django;django.setup();exec("+repr(code)+")"),
            env=env)
        POINTER.parent.mkdir(parents=True,exist_ok=True)
        write_atomic(POINTER,str(checkpoint)+"\n",0o600)
        restart_passenger()
        print("OWNER_WALLET_PROOF_PAGE_ACTIVATED_CHECKOUT_STILL_DISABLED")
    except Exception:
        restore(checkpoint)
        raise


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--activate",action="store_true")
    parser.add_argument("--rollback",action="store_true")
    args=parser.parse_args()
    if not (args.activate ^ args.rollback):
        parser.error("Specify exactly one operation")
    if args.activate:
        activate()
    else:
        if not POINTER.is_file():
            fail("No validated rollback checkpoint")
        restore(Path(POINTER.read_text().strip()))


if __name__=="__main__":
    main()
