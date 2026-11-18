#!/usr/bin/env python3
"""On-owner-cPanel PRIVATE native MOJ PROP WSGI readiness and Django key bootstrap.

This is NOT a public deployment, buyer signup, funds collection or commerce
activation. It never changes the 16GB production MariaDB, existing web root,
.htaccess, DNS, Passenger app registry, or paid merchant toggles.
"""
import json
import os
from pathlib import Path
import secrets
import stat
import sys

HOME=Path("/home/zomorod2")
STAGE=HOME/".mojprop-private-payment-stage-44248836810"
PRIVATE=HOME/".mojprop-native-v141-isolated-20261118"
DB=PRIVATE/"merchant.sqlite3"
SECRET=PRIVATE/"secret.key"
NEEDED=(
 "mojprop_isolated/settings.py","mojprop_isolated/urls.py",
 "mojprop_isolated/wsgi.py",
 "prop_firm/plan1_v141_native_checkout.py",
 "prop_firm/management/commands/mojprop_reconcile_native_trx.py",
 "templates/mojprop/v141-isolated-login.html",
 "core/mojprop_v141_native_receipt_view.py",
)
report={
 "schema":"mojprop.private.cpanel.real_wsgi_readiness.v1",
 "source_sha":"98994b85661459a9d719094207d59e6940e93131",
 "staged_app_verified":False, "private_merchant_db_verified":False,
 "django_secret_on_private_host":False, "effective_serializable_sqlite":False,
 "models_match_migrated_schema":False, "wsgi_callable_booted":False,
 "login_http_200":False,"csrf_present":False,
 "anonymous_invoice_requires_auth":False,
 "unknown_invoice_not_found":False,
 "paid_invoices_found":None,
 "public_files_modified":False,"customer_data_written":False,
 "live_payment_activated":False,"funds_moved":False,
}
try:
 os.umask(0o077)
 assert os.getuid()==HOME.stat().st_uid
 assert STAGE.is_dir() and not STAGE.is_symlink()
 assert all((STAGE/p).is_file() and not (STAGE/p).is_symlink()
            for p in NEEDED)
 assert PRIVATE.is_dir() and not PRIVATE.is_symlink()
 assert stat.S_IMODE(PRIVATE.stat().st_mode)==0o700
 assert DB.is_file() and not DB.is_symlink()
 assert stat.S_IMODE(DB.stat().st_mode)==0o600
 assert STAGE.stat().st_uid==os.getuid()
 assert DB.stat().st_uid==os.getuid()
 report["staged_app_verified"]=True
 report["private_merchant_db_verified"]=True
 if not SECRET.exists():
  # 512 bits, generated ON the private merchant host, never in GitHub logs.
  fd=os.open(str(SECRET),os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW|os.O_WRONLY,0o600)
  with os.fdopen(fd,"w") as f:
   f.write(secrets.token_urlsafe(64)+"\n")
   f.flush()
   os.fsync(f.fileno())
 assert not SECRET.is_symlink() and SECRET.is_file()
 assert SECRET.stat().st_uid==os.getuid()
 assert stat.S_IMODE(SECRET.stat().st_mode)==0o600
 assert len(SECRET.read_text("utf8").strip())>=64
 report["django_secret_on_private_host"]=True

 # Always override any accidental release flags in this isolated process.
 for k in ("MOJPROP_V141_NATIVE_TRX_RELEASE_ENABLED",
           "MOJPROP_TRX_GLOBAL_LEDGER_RECONCILED",
           "MOJPROP_TRX_AUTORECONCILE_ENABLED",
           "MOJ_PROP_V141_PORTFOLIO_ENABLED"):
  os.environ[k]="0"
 os.environ["MOJPROP_V141_LEDGER_PATH"]=str(DB)
 os.environ["DJANGO_SETTINGS_MODULE"]="mojprop_isolated.settings"
 os.environ["PYTHONDONTWRITEBYTECODE"]="1"
 sys.dont_write_bytecode=True
 sys.path.insert(0,str(STAGE))
 from mojprop_isolated.wsgi import application
 if not callable(application):
  raise RuntimeError("Real cPanel WSGI application not callable")
 report["wsgi_callable_booted"]=True
 from django.apps import apps
 from django.db import connection
 from django.test import Client
 from django.core.checks import run_checks
 from prop_firm.plan1_v141_native_checkout import _release_enabled
 if _release_enabled():
  raise RuntimeError("Payment release enabled unexpectedly")
 connection.ensure_connection()
 if connection.vendor!="sqlite" or getattr(connection,"transaction_mode",None)!="IMMEDIATE":
  raise RuntimeError("Private ledger missing effective serialized transactions")
 report["effective_serializable_sqlite"]=True
 if any(e.is_serious() for e in run_checks()):
  raise RuntimeError("Django private WSGI runtime checks failed")
 from django.db.migrations.recorder import MigrationRecorder
 applied=set(MigrationRecorder(connection).applied_migrations())
 if ("prop_firm","0012_v141_native_trx_receipt") not in applied:
  raise RuntimeError("Real merchant ledger missing migration 0012")
 report["models_match_migrated_schema"]=True
 from prop_firm.plan1_v141_native_payment_models import PropV141NativeOrder
 num=PropV141NativeOrder.objects.count()
 report["paid_invoices_found"]=num
 if num!=0:
  raise RuntimeError("Unexpected active invoice in owner empty ledger")
 client=Client(HTTP_HOST="mojplaywin.com")
 r=client.get("/moj-prop-v141/login/", secure=True,
              HTTP_X_FORWARDED_PROTO="https")
 report["login_http_200"]=r.status_code==200
 report["csrf_present"]=b"csrfmiddlewaretoken" in r.content
 guest=client.get("/moj-prop-v141/payment/MOJPROP01-"+("0"*32)+"/",
                  secure=True,HTTP_X_FORWARDED_PROTO="https")
 report["anonymous_invoice_requires_auth"]=(
     guest.status_code==302 and "/moj-prop-v141/login/" in guest["Location"])
 report["unknown_invoice_not_found"]=not PropV141NativeOrder.objects.filter(
     reference="MOJPROP01-"+("0"*32)).exists()
 if not all((report[k] is True for k in (
   "wsgi_callable_booted","login_http_200","csrf_present",
   "anonymous_invoice_requires_auth","models_match_migrated_schema"))):
  raise RuntimeError("Private WSGI verification incomplete")
except Exception as exc:
 report["error_kind"]=type(exc).__name__
 report["error_summary"]=str(exc).replace(str(HOME),"<owner-host>")[:160]
finally:
 print("MOJPROP_PRIVATE_CPANEl_WSGI_READINESS="+json.dumps(report,sort_keys=True))
if not report["anonymous_invoice_requires_auth"]:
 raise SystemExit(1)
