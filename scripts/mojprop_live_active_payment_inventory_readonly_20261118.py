#!/usr/bin/env python3
"""Read-only, privacy-preserving actual cPanel MojProp checkout topology.

Prints only source presence booleans and coarse counts. No customer data,
DB access, env/secrets access, files written or migrations performed.
Run on the owner's existing cPanel account through pinned SSH stdin.
"""
import json
import os
import pathlib
import subprocess

BASE = pathlib.Path("/home/zomorod2")
APP = BASE / "Saeit-staging"
DOCROOT = BASE / "mojplaywin.com"

def regular(p):
    try:
        return p.is_file() and not p.is_symlink()
    except OSError:
        return False

def source_flag(p, fragment):
    try:
        if not regular(p) or p.stat().st_size > 150000:
            return False
        return fragment in p.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False

def apps_info():
    try:
        raw = subprocess.run(
            ["uapi", "--output=json", "PassengerApps", "list_applications"],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            timeout=15, check=False,
        )
        if raw.returncode or len(raw.stdout) > 350000:
            return {"uapi_ok": False}
        payload = json.loads(raw.stdout)
        root = payload.get("result") if isinstance(payload,dict) else None
        if not isinstance(root,dict) or root.get("status") != 1:
            return {"uapi_ok": False}
        records = root.get("data")
        if isinstance(records,dict):
            records=records.get("applications",[])
        if not isinstance(records,list):
            return {"uapi_ok": True, "count_known":False}
        domains = [x for x in records if isinstance(x,dict)]
        # Never print app credentials, paths, user records or other domains.
        return {"uapi_ok":True,"count_known":True,
                "application_count":len(domains),
                "mojplaywin_mapping_present":any(
                    "mojplaywin.com" in str(x.get("domain","")).lower()
                    for x in domains)}
    except (OSError,ValueError,subprocess.TimeoutExpired):
        return {"uapi_ok":False}

def inspect():
    if not (APP.is_dir() and not APP.is_symlink()
            and DOCROOT.is_dir() and not DOCROOT.is_symlink()):
        return {"schema":"mojprop.live.payment_inventory.readonly.v1",
                "read_only":True,"roots_verified":False}
    urls = APP / "config/urls.py"
    codepaths = {
        "new_native_checkout": APP/"prop_firm/plan1_v141_native_checkout.py",
        "native_watcher":APP/"prop_firm/plan1_v141_native_watcher.py",
        "native_models":APP/"prop_firm/plan1_v141_native_payment_models.py",
        "native_db_migration":APP/"prop_firm/migrations/0012_v141_native_trx_receipt.py",
        "private_invoice_view":APP/"core/mojprop_v141_native_receipt_view.py",
        "private_invoice_template":APP/"templates/mojprop/v141-native-trx-invoice.html",
        "native_admin_command":APP/"prop_firm/management/commands/mojprop_reconcile_native_trx.py",
        "existing_walletless_bridge":APP/"core/crown_tron_receipts.py",
        "existing_owner_wallet_reference":APP/"services/mojtaba_tron_owner_receiver.py",
        "root_wsgi":DOCROOT/"passenger_wsgi.py",
    }
    try:
        st=os.statvfs(APP)
        free_mib=(st.f_bavail*st.f_frsize)//(1024*1024)
    except OSError:
        free_mib=None
    return {
        "schema":"mojprop.live.payment_inventory.readonly.v1",
        "read_only":True,"customer_records_accessed":False,
        "database_connected":False,"roots_verified":True,
        "files_present":{k:regular(p) for k,p in codepaths.items()},
        "url_native_payment_present":source_flag(urls, 'moj-prop-v141/payment/'),
        "url_public_interest_present":source_flag(urls, 'moj-prop-intake/'),
        "root_wsgi_safe_present":regular(DOCROOT/"passenger_wsgi.py"),
        "main_static_mojprop_present":(DOCROOT/"moj-prop").is_dir(),
        "free_mib_coarse":None if free_mib is None else
           ("0-256" if free_mib<257 else "257-512" if free_mib<513
            else "513-1024" if free_mib<1025 else "1025-4096" if free_mib<4097
            else ">4096"),
        "passenger":apps_info()
    }

if __name__=="__main__":
    print("MOJPROP_LIVE_PAYMENT_INVENTORY="+json.dumps(inspect(),sort_keys=True))
