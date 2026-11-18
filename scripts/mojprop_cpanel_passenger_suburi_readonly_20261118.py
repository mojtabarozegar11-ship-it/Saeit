#!/usr/bin/env python3
"""Private cPanel domain sub-URI installation readiness (READ ONLY).

Checks only target mojplaywin.com and target /moj-prop-v141 path. No site
files edited, no cPanel registration, no secrets, DB or customer content read.
"""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

HOME=Path("/home/zomorod2")
DOMAIN=HOME/"mojplaywin.com"
TARGET="moj-prop-v141"
app_stage=HOME/".mojprop-private-payment-stage-44248836810"
report={
 "schema":"mojprop.private.passenger_suburi_readonly.v1",
 "target_domain":"mojplaywin.com",
 "target_uri":"/moj-prop-v141",
 "target_docroot_exists":DOMAIN.is_dir() and not DOMAIN.is_symlink(),
 "target_suburi_folder_absent":False,
 "target_passenger_wsgi_present":(DOMAIN/"passenger_wsgi.py").is_file(),
 "app_stage_readable":app_stage.is_dir() and
    (app_stage/"mojprop_isolated/wsgi.py").is_file(),
 "cpanel_passengerapps_uapi_available":False,
 "cpanel_passengerapps_register_count":None,
 "existing_target_registered":None,
 "cloudlinux_selector_available":False,
 "cloudlinux_python_list_success":False,
 "target_htaccess_sha256":None,
 "domain_htaccess_present":False,
 "reads_only":True,
 "customer_data_read":False,
 "payment_enabled":False,
 "site_rewrites_changed":False,
}
try:
 if os.getuid()!=HOME.stat().st_uid:
  raise RuntimeError("Unexpected owner context")
 target=DOMAIN/TARGET
 report["target_suburi_folder_absent"]=not target.exists() and not target.is_symlink()
 ht=DOMAIN/".htaccess"
 if ht.is_file() and not ht.is_symlink():
  report["domain_htaccess_present"]=True
  # Only public-domain routing config hash, no content or secrets printed.
  if ht.stat().st_size<=500000:
   report["target_htaccess_sha256"]=hashlib.sha256(ht.read_bytes()).hexdigest()
 uapi=shutil.which("uapi")
 if uapi:
  p=subprocess.run([uapi,"--output=json","PassengerApps","list_applications"],
      stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,timeout=18,check=False)
  if p.returncode==0 and len(p.stdout)<300000:
   o=json.loads(p.stdout)
   status=o.get("result") if type(o) is dict else None
   if type(status) is dict and status.get("status")==1:
    report["cpanel_passengerapps_uapi_available"]=True
    apps=status.get("data")
    if type(apps) is dict:
     apps=apps.get("applications",[])
    if type(apps) is list:
     report["cpanel_passengerapps_register_count"]=len(apps)
     report["existing_target_registered"]=any(
        TARGET in str(x.get("app_uri","") or x.get("url","") or x.get("app_path",""))
        for x in apps if type(x) is dict)
 selector=shutil.which("cloudlinux-selector")
 if selector:
  report["cloudlinux_selector_available"]=True
  p=subprocess.run([selector,"--json","--interpreter","python","--get"],
      stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,timeout=15,check=False)
  if p.returncode==0 and len(p.stdout)<400000:
   try:
    d=json.loads(p.stdout)
    report["cloudlinux_python_list_success"]=type(d) in (list,dict)
   except (ValueError,UnicodeError):
    pass
except Exception as e:
 report["error_kind"]=type(e).__name__
 report["error_summary"]=str(e)[:120]
finally:
 print("MOJPROP_PASSENGER_SUBURI_PREFLIGHT="+json.dumps(report,sort_keys=True))
if not (report["target_docroot_exists"] and report["app_stage_readable"]
        and report["reads_only"]):
 raise SystemExit(1)
