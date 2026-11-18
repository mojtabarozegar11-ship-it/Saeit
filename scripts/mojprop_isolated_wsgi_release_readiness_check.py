#!/usr/bin/env python3
"""Offline isolated client-facing WSGI assurance, zero production interactions."""
import json
import os
from pathlib import Path
import stat
import tempfile
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

with tempfile.TemporaryDirectory(prefix="mojprop-v141-isolated-wsgi-ci-") as d:
 root=Path(d)
 root.chmod(0o700)
 ledger=root/"merchant.sqlite3"
 ledger.touch(mode=0o600)
 ledger.chmod(0o600)
 secret=root/"secret.key"
 secret.write_text("ci-disposable-only-not-a-merchant-secret-" + "r"*48)
 secret.chmod(0o600)
 assert stat.S_IMODE(root.stat().st_mode)==0o700
 os.environ["MOJPROP_V141_LEDGER_PATH"]=str(ledger)
 os.environ["DJANGO_SETTINGS_MODULE"]="mojprop_isolated.settings"
 from mojprop_isolated.wsgi import application
 from django.apps import apps
 from django.conf import settings
 from django.core.checks import run_checks
 from django.core.management import call_command
 from django.db import connection
 assert connection.vendor=="sqlite"
 connection.ensure_connection()
 assert getattr(connection,"transaction_mode",None)=="IMMEDIATE"
 assert not apps.is_installed("core")
 assert not any(e.is_serious() for e in run_checks())
 call_command("migrate",interactive=False,verbosity=0)
 from django.contrib.auth import get_user_model
 from django.test import Client
 test_user=get_user_model().objects.create_user(
     username="fake-ci-no-real-buyer",password="CI-Only-VeryStrong-Synthetic-Password-1234")
 client=Client(HTTP_HOST="mojplaywin.com")
 login=client.get("/moj-prop-v141/login/",secure=True)
 assert login.status_code==200
 assert b"Private buyer account" in login.content
 assert b"csrfmiddlewaretoken" in login.content
 # Passenger may mount the isolated application under a sub-URI and strip
 # '/moj-prop-v141' from PATH_INFO. Simulate SCRIPT_NAME faithfully.
 mount_login=client.get("/login/",secure=True,
                        SCRIPT_NAME="/moj-prop-v141",
                        HTTP_X_FORWARDED_PROTO="https")
 assert mount_login.status_code==200
 assert b"csrfmiddlewaretoken" in mount_login.content
 mount_receipt=client.get("/payment/MOJPROP01-"+("0"*32)+"/",
                          secure=True,SCRIPT_NAME="/moj-prop-v141",
                          HTTP_X_FORWARDED_PROTO="https")
 assert mount_receipt.status_code==302
 assert "/moj-prop-v141/login/" in mount_receipt["Location"]

 ref="MOJPROP01-"+"0"*32
 private_path="/moj-prop-v141/payment/"+ref+"/"
 unauth=client.get(private_path,secure=True)
 assert unauth.status_code==302
 assert "/moj-prop-v141/login/" in unauth["Location"]
 client.force_login(test_user)
 no_order=client.get(private_path,secure=True)
 assert no_order.status_code==404
 no_demo=client.get("/moj-prop-v141/statement/CI-UNKNOWN/",secure=True)
 assert no_demo.status_code==404
 dash=client.get("/moj-prop-v141/",secure=True)
 assert dash.status_code==200
 assert b"My account" in dash.content
 assert b"No reviewable orders" in dash.content
 assert b"csrfmiddlewaretoken" in dash.content
 assert "no-store" in dash["Cache-Control"]
 assert "noindex" in dash["X-Robots-Tag"]
 assert client.get("/",secure=True,SCRIPT_NAME="/moj-prop-v141").status_code==200
 assert client.get("/moj-prop-v141/?page=0",secure=True).status_code==404
 assert client.get("/moj-prop-v141/?page=2",secure=True).status_code==404
 assert client.get("/moj-prop-v141/?page=1&page=1",secure=True).status_code==404
 assert client.post("/moj-prop-v141/",secure=True).status_code==405
 assert client.head("/moj-prop-v141/",secure=True).content==b""
 assert client.get("/moj-prop-v141/logout/",secure=True).status_code==405
 assert client.post("/moj-prop-v141/logout/",secure=True).status_code==302
 assert client.get("/moj-prop-v141/",secure=True).status_code==302
 from prop_firm.plan1_v141_native_checkout import _release_enabled
 assert _release_enabled() is False
 from prop_firm.plan1_v141_native_checkout import _require_serializable_payment_write
 _require_serializable_payment_write()
 print("MOJPROP_V141_STANDALONE_WSGI_CHECK="+json.dumps({
   "no_legacy_core_db":True,"private_sqlite":True,
   "sqlite_immediate_transactions":True,
   "migrations_successful":True,
   "private_login_get_200":True,
   "passenger_suburi_login_200":True,
   "passenger_suburi_private_invoice_requires_auth":True,
   "csrf_token_present":True,"visitor_invoice_requires_login":True,
   "unknown_buyer_invoice_404":True,
   "unknown_trading_account_404":True,
   "public_checkout_disabled":True,
   "money_transferred":False,
   "production_customer_data_accessed":False
 },sort_keys=True))
