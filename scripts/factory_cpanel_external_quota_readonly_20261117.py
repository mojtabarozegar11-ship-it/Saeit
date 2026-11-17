#!/usr/bin/env python3
"""Only numeric accounting from cPanel DiskUsage API2 and Quota UAPI.

No access to file contents, no printing names/owners/paths/email/DB names.
API2 is deprecated but remains the documented read-only endpoint for
outside-home MySQL, PostgreSQL and mail archive usage.
"""
import json
import os
from pathlib import Path
import pwd
import shutil
import subprocess
import sys
import time

USER="zomorod2"
SAFE_NUMERIC=("quotaused", "mysql", "pgsql", "mailman", "quotalimit")


def call_quota():
    p=subprocess.run(["uapi", "--output=json", "Quota", "get_quota_info"],
                     stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                     text=True,timeout=35,check=False)
    if p.returncode:raise RuntimeError("UAPI_QUOTA_FAILED")
    result=json.loads(p.stdout).get("result",{})
    data=result.get("data",{}) if isinstance(result,dict) else {}
    if not isinstance(data,dict):raise RuntimeError("UAPI_QUOTA_SCHEMA")
    fields={}
    for k in ("megabyte_limit","megabytes_used","megabytes_remain","inodes_used"):
        x=data.get(k)
        if isinstance(x,(int,float)) and not isinstance(x,bool):fields[k]=x
    if len(fields)<3:raise RuntimeError("UAPI_QUOTA_NUMERIC_MISSING")
    return fields


def cpapi2_numeric():
    exe=shutil.which("cpapi2")
    if not exe:
        candidate=Path("/usr/local/cpanel/bin/cpapi2")
        if candidate.is_file() and os.access(candidate,os.X_OK):
            exe=str(candidate)
    if not exe:
        return {"available":False,"reason":"CPAPI2_NOT_INSTALLED"}
    try:
        p=subprocess.run([exe,"--user="+USER,"DiskUsage",
                          "fetchdiskusagewithextras"],
                         stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,
                         timeout=135,check=False)
    except (OSError,subprocess.TimeoutExpired):
        return {"available":False,"reason":"CPAPI2_TIMEOUT_OR_EXEC_ERROR"}
    if p.returncode or len(p.stdout)>8_000_000:
        return {"available":False,"reason":"CPAPI2_FAILED_OR_TOO_LARGE"}
    try:
        result=json.loads(p.stdout).get("cpanelresult",{})
        if not isinstance(result,dict):raise ValueError("DATA_NOT_DICT")
        event=result.get("event",{})
        rows=result.get("data",[])
        if not isinstance(rows,list) or not rows:
            raise ValueError("DATA_MISSING")
        if isinstance(event,dict) and event.get("result") not in (1,"1",True):
            raise ValueError("EVENT_NOT_SUCCESS")
        item=rows[0]
        if not isinstance(item,dict):raise ValueError("ROW_NOT_DICT")
        numeric={}
        for key in SAFE_NUMERIC:
            val=item.get(key)
            if isinstance(val,(int,float)) and not isinstance(val,bool):
                numeric[key+"_bytes"]=int(val)
        home=item.get("homedir")
        if isinstance(home,dict):
            for key in ("contained_usage","user_contained_usage"):
                value=home.get(key)
                if isinstance(value,(int,float)) and not isinstance(value,bool):
                    numeric["home_"+key+"_bytes"]=int(value)
        mail_archive=item.get("mailarchives")
        if isinstance(mail_archive,(int,float)) and not isinstance(mail_archive,bool):
            numeric["mailarchives_bytes"]=int(mail_archive)
        if not numeric:
            raise ValueError("NO_NUMERIC_USAGE")
        return {"available":True,"fields":numeric,
                "returned_rows":len(rows),"uses_deprecated_readonly_api2":True}
    except (ValueError,TypeError,KeyError):
        return {"available":False,"reason":"CPAPI2_SCHEMA_NOT_RECOGNIZED"}


def main():
    if pwd.getpwuid(os.geteuid()).pw_name != USER:
        raise RuntimeError("WRONG_ACCOUNT")
    start=time.monotonic()
    before=call_quota()
    api=cpapi2_numeric()
    after=call_quota()
    if before.get("megabyte_limit")!=after.get("megabyte_limit"):
        raise RuntimeError("ACCOUNT_QUOTA_LIMIT_CHANGED")
    report={
        "schema":"moj.factory.cpanel.external-quota-accounting.v1",
        "read_only":True,
        "no_sensitive_names_reported":True,
        "quota_before":before,
        "api2_extras":api,
        "quota_after":after,
        "account_quota_megabytes_are_cpanel_uapi_values":True,
        "api2_values_bytes_are_not_home_du_bytes":True,
        "files_created":0,"files_deleted":0,
        "safe_to_delete":False,
        "elapsed_seconds":round(time.monotonic()-start,2),
    }
    print("MOJ_CPANEL_EXTERNAL_QUOTA="+json.dumps(report,sort_keys=True),flush=True)


if __name__=="__main__":
    try:main()
    except Exception as exc:
        print("MOJ_CPANEL_EXTERNAL_QUOTA_FAILED="+type(exc).__name__+":"+str(exc)[:80],
              file=sys.stderr,flush=True)
        sys.exit(1)
