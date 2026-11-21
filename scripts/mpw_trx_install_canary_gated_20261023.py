#!/usr/bin/env python3
"""Atomic additive install of merchant TRX integration on known cPanel staging app.

Only new source modules and two tiny Django config additions. Financial route
is OFF until explicit merchant-canary release flags are configured separately.
Back up every touched existing file and roll back if Django cannot import.
No DB migration, wallet keys, wallet broadcasts or merchant order writes.
"""
from __future__ import annotations
import json,os,shutil,subprocess,sys,tempfile,hashlib
from pathlib import Path

APP=Path("/home/zomorod2/Saeit-staging")
PUBLIC=Path("/home/zomorod2/mojplaywin.com")
BACKUP_BASE=Path("/home/zomorod2/.local/share/mpw-trx-rollbacks")
SOURCE=Path(sys.argv[1]) if len(sys.argv)>1 else None
PYTHON="/home/zomorod2/virtualenv/Saeit-staging/3.11/bin/python"

ALLOWED=(
    "services/mpw_trx_walletless_core.py",
    "services/mpw_tron_independent_solidified_rpc.py",
    "services/mpw_tron_readonly_deposit_candidates.py",
    "services/mpw_trx_walletless_checkout_ui.py",
    "services/mpw_trx_walletless_one_tap_ui.py",
    "services/mpw_walletless_django_test_bridge.py",
    "services/mpw_walletless_commercial_intent.py",
    "services/mpw_trx_commercial_chain.py",
    "services/mpw_trx_reconcile_cursor.py",
    "services/mpw_trx_commercial_web.py",
    "scripts/mpw_tron_public_dual_probe_readonly_20261023.py",
    "scripts/mpw_trx_commercial_reconcile_cron.py",
)
URL_MARK="# MPW_GATED_NATIVE_TRX_ROUTE_20261023"
SETTINGS_MARK="# MPW_GATED_NATIVE_TRX_SETTINGS_20261023"
URL_ADD="""

# MPW_GATED_NATIVE_TRX_ROUTE_20261023
from services.mpw_trx_commercial_web import (
    start_order as _mpw_trx_start, show_invoice as _mpw_trx_invoice,
    invoice_status as _mpw_trx_status, reconcile_invoice as _mpw_trx_reconcile,
    download_paid as _mpw_trx_download,
)
urlpatterns += [
    path("commerce/trx-easy/start/<int:product_id>/",_mpw_trx_start,name="mpw_trx_easy_start"),
    path("commerce/trx-easy/invoice/<int:invoice_id>/",_mpw_trx_invoice,name="mpw_trx_easy_invoice"),
    path("commerce/trx-easy/status/<int:invoice_id>/",_mpw_trx_status,name="mpw_trx_easy_status"),
    path("commerce/trx-easy/reconcile/<int:invoice_id>/",_mpw_trx_reconcile,name="mpw_trx_easy_reconcile"),
    path("commerce/trx-easy/download/<int:invoice_id>/",_mpw_trx_download,name="mpw_trx_easy_download"),
]
"""
SETTINGS_ADD="""

# MPW_GATED_NATIVE_TRX_SETTINGS_20261023
# Both merchant canary and deliberate public enablement are required.
import os as _mpw_trx_os
MPW_WALLETLESS_TRX_PUBLIC_ENABLED = _mpw_trx_os.environ.get(
    "MPW_WALLETLESS_TRX_PUBLIC_ENABLED","0"
) == "1"
MPW_WALLETLESS_TRX_MERCHANT_CANARY_PASSED = _mpw_trx_os.environ.get(
    "MPW_WALLETLESS_TRX_MERCHANT_CANARY_PASSED","0"
) == "1"
"""

def install():
    if (SOURCE is None or not SOURCE.is_dir() or SOURCE.is_symlink()
        or not APP.is_dir() or APP.is_symlink() or PUBLIC.is_symlink()
        or not Path(PYTHON).is_file()):
        raise RuntimeError("Expected trusted staging paths missing")
    passenger=PUBLIC/"passenger_wsgi.py"
    if not passenger.is_file() or "APP='/home/zomorod2/Saeit-staging'" not in passenger.read_text("utf8","replace"):
        raise RuntimeError("Unrecognized MojPlayWin Passenger source")
    conf=APP/"config/urls.py"
    settings=APP/"config/settings.py"
    if any(p.is_symlink() or not p.is_file() or p.stat().st_size>250000 for p in (conf,settings)):
        raise RuntimeError("Unexpected existing Django config")
    if (not conf.read_text("utf8").count("urlpatterns")
        or len(settings.read_text("utf8"))<100):
        raise RuntimeError("Unexpected Django settings and routes")
    # All code in source bundle must be allowlisted; refuse surprise content.
    received=sorted(str(p.relative_to(SOURCE)) for p in SOURCE.rglob("*.py"))
    if received!=sorted(ALLOWED):
        raise RuntimeError("Unexpected deployment bundle")
    for rel in ALLOWED:
        path=SOURCE/rel
        if path.is_symlink() or not path.is_file() or path.stat().st_size>160000:
            raise RuntimeError("Unsafe source payload")
        compile(path.read_text("utf8"),str(path),"exec")
    BACKUP_BASE.mkdir(mode=0o700,parents=True,exist_ok=True)
    if BACKUP_BASE.is_symlink():
        raise RuntimeError("Unsafe backup root")
    backup=Path(tempfile.mkdtemp(prefix="trx-guarded-",dir=str(BACKUP_BASE)))
    os.chmod(backup,0o700)
    touched=[]
    try:
        for rel in [*ALLOWED,"config/urls.py","config/settings.py"]:
            target=APP/rel
            target.parent.mkdir(parents=True,exist_ok=True)
            if target.is_symlink():
                raise RuntimeError("Cannot overwrite symlink")
            if target.exists():
                saved=backup/rel
                saved.parent.mkdir(parents=True,exist_ok=True)
                shutil.copy2(target,saved)
            touched.append(rel)
        for rel in ALLOWED:
            src=SOURCE/rel
            dst=APP/rel
            temporary=dst.with_name(dst.name+".mpw-tmp")
            if temporary.exists() or temporary.is_symlink():
                raise RuntimeError("Pre-existing staging temporary file")
            shutil.copy2(src,temporary)
            os.chmod(temporary,0o644)
            os.replace(temporary,dst)
        for target,marker,addition in (
            (conf,URL_MARK,URL_ADD),(settings,SETTINGS_MARK,SETTINGS_ADD),
        ):
            body=target.read_text("utf8")
            if marker not in body:
                temporary=target.with_name(target.name+".mpw-tmp")
                if temporary.exists() or temporary.is_symlink():
                    raise RuntimeError("Unexpected temporary config")
                temporary.write_text(body.rstrip()+"\n"+addition,encoding="utf8")
                os.chmod(temporary,target.stat().st_mode&0o777)
                os.replace(temporary,target)
        # Production route import must succeed, but its merchant release guard
        # MUST stay off. Reading URL config here creates no customer orders.
        test_script=(
            "import os,django;"
            "os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings');"
            "django.setup();"
            "from django.conf import settings;"
            "from django.urls import resolve;"
            "from services.mpw_trx_commercial_web import COMMERCIAL_URLPATTERNS;"
            "assert len(COMMERCIAL_URLPATTERNS)==5;"
            "assert resolve('/commerce/trx-easy/start/72/').url_name=='mpw_trx_easy_start';"
            "assert not settings.MPW_WALLETLESS_TRX_PUBLIC_ENABLED;"
            "assert not settings.MPW_WALLETLESS_TRX_MERCHANT_CANARY_PASSED;"
            "from services.mpw_walletless_commercial_intent import _commercial_db;"
            "print('GUARDED_TRX_IMPORT_ROUTES=PASS')"
        )
        env=os.environ.copy()
        env["DJANGO_SETTINGS_MODULE"]="config.settings"
        env["MPW_WALLETLESS_TRX_PUBLIC_ENABLED"]="0"
        env["MPW_WALLETLESS_TRX_MERCHANT_CANARY_PASSED"]="0"
        result=subprocess.run(
            [PYTHON,"-B","-c",test_script],cwd=str(APP),env=env,
            stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
            timeout=80,check=False,
        )
        if result.returncode!=0 or b"GUARDED_TRX_IMPORT_ROUTES=PASS" not in result.stdout:
            raise RuntimeError("Django route and canary gate smoke test failed")
        return {"status":"GUARDED_APP_INSTALL_PASSED",
                "installed_modules":len(ALLOWED),
                "url_mounted":True,"public_payment_enabled":False,
                "new_financial_writes":0,"rollback_saved":True,
                "backup_id":backup.name}
    except Exception:
        for rel in reversed(touched):
            dest=APP/rel
            old=backup/rel
            if old.exists():
                shutil.copy2(old,dest)
            elif dest.exists():
                dest.unlink()
        raise

if __name__=="__main__":
    try:
        print("MPW_TRX_STAGE_INSTALL="+json.dumps(install(),sort_keys=True))
    except Exception as exc:
        print("MPW_TRX_STAGE_INSTALL="+json.dumps({
            "status":"ROLLED_BACK_OR_REFUSED",
            "error_class":type(exc).__name__,
            "payment_enabled":False,
        },sort_keys=True))
        raise SystemExit(2)
