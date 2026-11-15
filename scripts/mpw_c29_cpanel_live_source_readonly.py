#!/usr/bin/env python3
"""Bounded, strictly read-only real cPanel source/Passenger parity inspector.

Only pre-approved fixed source paths. Never reads databases, logs, emails,
environment secrets, .env, keys or customer files. Never writes on cPanel.
Git blob hashes allow exact match against GitHub sources without disclosing
code or credentials.
"""
import hashlib
import json
import os
from pathlib import Path

ROOTS = (
    Path("/home/zomorod2/Saeit"),
    Path("/home/zomorod2/Saeit-staging"),
    Path("/home/zomorod2/mojplaywin.com"),
    Path("/home/zomorod2/public_html"),
)
SOURCE_FILES = (
    "manage.py",
    "passenger_wsgi.py",
    "config/urls.py",
    "core/financial_brand_pages.py",
    "core/signal_commercial_catalog.py",
    "core/tron_gateway_web.py",
    "core/tron_gateway_invoice.py",
    "core/mojtaba_signal_paid_access.py",
    "prop_firm/plans.py",
    "prop_firm/portal.py",
    "services/mpw_trx_guest_commerce.py",
    "services/mpw_trx_guest_delivery.py",
    "services/mpw_trx_public_catalog.py",
    "services/mpw_trx_public_pages.py",
    "services/mpw_trx_commercial_context.py",
    "services/mpw_trx_asset_integrity.py",
    "services/mpw_trx_commercial_web.py",
    "services/mpw_walletless_commercial_intent.py",
    "mpw_commerce/downloads.py",
    "mpw_commerce/urls.py",
    "core/mojplaywin_dynamic_catalog.py",
    "core/mojplaywin_checkout_route.py",
    "core/mojplaywin_product_detail.py",
    "core/mojplaywin_views.py",
    "core/signal_entitlement_contract.py",
    "core/signal_product_plans.py",
    "core/tron_tenant_policy.py",
    "prop_firm/rules.py",
    "prop_firm/challenge_commerce.py",
    "prop_firm/policy_integrity.py",
)
MAX_FILE = 300000

def can_read(root, path):
    if (root.is_symlink() or not root.is_dir() or
            path.is_symlink() or not path.is_file()):
        return False
    current = path.parent
    while current != root:
        if current.is_symlink() or root not in current.parents:
            return False
        current = current.parent
    return True

def file_audit(root, relative):
    path=root/relative
    if not can_read(root,path):
        return {"present": False}
    try:
        stat=path.stat()
        if not 0 < stat.st_size <= MAX_FILE:
            return {"present":True,"safety":"size_out_of_scope"}
        content=path.read_bytes()
        if len(content)!=stat.st_size:
            return {"present":True,"safety":"changed_during_read"}
        git_blob=hashlib.sha1(
            b"blob "+str(len(content)).encode("ascii")+bytes([0])+content
        ).hexdigest()
        markers={
            "moj_prop_router": b"moj-prop/" in content,
            "ten_plan_moj_prop": b"CHALLENGE_PLANS" in content,
            "signal_brand_pages": b"BRANDS" in content and b"financial" in content,
            "native_trx_gateway": b"TronGatewayInvoice" in content,
            "one_bot_paid_entitlement": b"paid_signal_access" in content,
            "mpw_email_recovery": b"recovery" in content,
        }
        return {"present":True,"bytes":len(content),"git_blob_sha1":git_blob,
                "source_features":{k:v for k,v in markers.items() if v}}
    except (PermissionError, OSError, ValueError):
        return {"present":False,"safety":"unreadable"}

def public_bootstrap(root):
    if root.name != "mojplaywin.com":
        return {}
    result={}
    for filename in ("passenger_wsgi.py",".htaccess"):
        path=root/filename
        if not can_read(root,path) or path.stat().st_size>20000:
            result[filename]={"present":False}
            continue
        text=path.read_bytes()
        result[filename]={
            "present":True,
            "mentions_Saeit_staging": b"/home/zomorod2/Saeit-staging" in text,
            "mentions_Saeit_root": b"/home/zomorod2/Saeit" in text,
            "mentions_mojplaywin_root": b"/home/zomorod2/mojplaywin.com" in text,
            "passenger_app_root_declared": b"PassengerAppRoot" in text,
        }
    return result

def main():
    if os.geteuid() == 0 or os.environ.get("PYTHONDONTWRITEBYTECODE") != "1":
        raise SystemExit("READONLY_CPANEL_UNTRUSTED_RUNTIME")
    result={"mode":"READ_ONLY_GIT_BLOB_SOURCE_PARITY",
            "writes":0,"customer_data_read":False,
            "emails_read":False,"payments_read":False,"secrets_read":False,
            "roots":[]}
    for root in ROOTS:
        if root.is_symlink() or not root.is_dir():
            result["roots"].append({"root":str(root),"exists":False})
            continue
        files={k:file_audit(root,k) for k in SOURCE_FILES}
        result["roots"].append({"root":str(root),"exists":True,
                                "files":files,"public_bootstrap":public_bootstrap(root)})
    print("MPW_C29_PRODUCTION_SOURCE_PARITY="+json.dumps(result,sort_keys=True))
if __name__=="__main__":
    main()
