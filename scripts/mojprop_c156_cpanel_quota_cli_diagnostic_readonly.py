#!/usr/bin/env python3
"""C156 differentiate cPanel API availability vs parsing, without printing errors.

One documented UAPI StatsBar::get_stats plus one *deprecated read-only*
cPanel API 2 StatsBar::stat fallback (only if the binary exists).
Neither call uses shell, password, HTTP token, browser, database, email,
file contents or modifications. Raw stdout/stderr are NEVER printed.
This only infers an account quota when a valid same-unit diskusage
count/max pair is actually returned; it never authorizes backups or deploy.
"""
from __future__ import annotations
import json
import math
import os
import pwd
import re
import stat
import subprocess

OWNER="zomorod2"
UAPI="/usr/local/cpanel/bin/uapi"
CPAPI2="/usr/local/cpanel/bin/cpapi2"
MAX_BYTES=65536
TIMEOUT=15
DISPLAY="diskusage|mysqldiskusage"
NUMBER=re.compile(r"^(?:0|[1-9][0-9]{0,12})(?:\.[0-9]{1,3})?$")
ALLOWED_UNITS=frozenset(("MB","GB","KB","TB","B","bytes"))

CALLS={
    "uapi_statsbar": [UAPI,"--output=json","StatsBar","get_stats",
                      "display="+DISPLAY],
    "cpapi2_statsbar": [CPAPI2,"--output=json","--user=zomorod2","StatsBar","stat",
                       "display="+DISPLAY,"warnings=0","warninglevel=87",
                       "warnout=0","infinityimg=/dev/null",
                       "infinitylang=infinity","rowcounter=even"],
}
CLASSIFICATIONS=("binary_missing","binary_not_regular_or_executable",
    "process_failed","timeout_or_os_error","response_missing_or_oversize",
    "invalid_json","schema_unrecognized","api_status_failed",
    "success_no_matching_quota","success_numeric_quota")


def _numeric(raw):
    if type(raw) in (int,float) and math.isfinite(raw) and 0<=raw<1e13:
        return float(raw)
    if type(raw) is str and NUMBER.fullmatch(raw):
        return float(raw)
    return None


def _safe_stat(row, expected):
    out={"found":False,"unit":None,"used":None,
         "limit":None,"percent_used":None}
    if type(row) is not dict or row.get("id")!=expected:
        return out
    unit=row.get("units")
    if unit not in ALLOWED_UNITS:
        return out
    used=_numeric(row.get("count") if row.get("count") is not None
                  else row.get("_count"))
    if used is None:
        return out
    out.update(found=True,unit=unit,used=round(used,3))
    limit=_numeric(row.get("max") if row.get("max") is not None
                   else row.get("_max"))
    if limit and limit>0:
        out["limit"]=round(limit,3)
        out["percent_used"]=round(100*used/limit,3)
    return out


def _parse_response(raw: object, variant: str):
    """No raw messages, identifiers, names, user-supplied fields or errors."""
    if type(raw) is not dict:
        return "schema_unrecognized",None
    if variant=="uapi_statsbar":
        envelope=raw.get("result")
        if type(envelope) is not dict:
            return "schema_unrecognized",None
        if envelope.get("status") not in (True,1):
            return "api_status_failed",None
        rows=envelope.get("data")
    elif variant=="cpapi2_statsbar":
        envelope=raw.get("cpanelresult")
        if type(envelope) is not dict:
            return "schema_unrecognized",None
        if envelope.get("module")!="StatsBar" or envelope.get("func")!="stat":
            return "schema_unrecognized",None
        evt=envelope.get("event")
        if type(evt) is not dict or evt.get("result") not in (1,True):
            return "api_status_failed",None
        rows=envelope.get("data")
    else:
        raise ValueError("unknown quota read variant")
    if type(rows) is not list or len(rows)>16:
        return "schema_unrecognized",None
    data={}
    for key in ("diskusage","mysqldiskusage"):
        matches=[x for x in rows if type(x) is dict and x.get("id")==key]
        data[key]=_safe_stat(matches[0],key) if len(matches)==1 else _safe_stat(None,key)
    if data["diskusage"]["found"] and data["diskusage"]["percent_used"] is not None:
        return "success_numeric_quota",data
    return "success_no_matching_quota",data


def _one(name):
    out={"diagnostic":"binary_missing","account_disk":_safe_stat(None,"diskusage"),
         "mysql_disk":_safe_stat(None,"mysqldiskusage")}
    if name not in CALLS:
        raise ValueError("unknown program")
    binary=CALLS[name][0]
    try:
        st=os.stat(binary,follow_symlinks=False)
        if (not stat.S_ISREG(st.st_mode) or not os.access(binary,os.X_OK)):
            out["diagnostic"]="binary_not_regular_or_executable"
            return out
    except OSError:
        return out
    try:
        cp=subprocess.run(
            CALLS[name],capture_output=True,timeout=TIMEOUT,check=False,
            env={"HOME":"/home/zomorod2","USER":OWNER,
                 "PATH":"/usr/local/cpanel/bin:/usr/bin:/bin"},
        )
    except (OSError,subprocess.TimeoutExpired):
        out["diagnostic"]="timeout_or_os_error"
        return out
    if cp.returncode!=0:
        out["diagnostic"]="process_failed"
        return out
    if not 0<len(cp.stdout)<=MAX_BYTES:
        out["diagnostic"]="response_missing_or_oversize"
        return out
    try:
        obj=json.loads(cp.stdout.decode("utf-8"))
    except (UnicodeError,ValueError):
        out["diagnostic"]="invalid_json"
        return out
    verdict,values=_parse_response(obj,name)
    out["diagnostic"]=verdict
    if values:
        out["account_disk"]=values["diskusage"]
        out["mysql_disk"]=values["mysqldiskusage"]
    return out


def report():
    out={"schema":"mojprop.cpanel.quota_cli_diagnostic.readonly.c156.v1",
         "read_only":True,"owner_identity_verified":False,
         "uapi_statsbar":{"diagnostic":"binary_missing",
                           "account_disk":_safe_stat(None,"diskusage"),
                           "mysql_disk":_safe_stat(None,"mysqldiskusage")},
         "cpapi2_statsbar":{"diagnostic":"binary_missing",
                             "account_disk":_safe_stat(None,"diskusage"),
                             "mysql_disk":_safe_stat(None,"mysqldiskusage")},
         "account_backup_write_authorized":False,
         "offhost_independent_restore_verified":False,
         "full_app_db_media_restore_proven":False,
         "database_content_read":False,"backup_content_read":False,
         "customer_data_accessed":False,"external_network_called":False,
         "production_deployment_authorized":False,"payment_created":False,
         "cost_incurred":False}
    try:
        if pwd.getpwuid(os.geteuid()).pw_name!=OWNER:
            return out
        out["owner_identity_verified"]=True
        for name in CALLS:
            out[name]=_one(name)
    except (OSError,ValueError,KeyError):
        pass
    return out


if __name__=="__main__":
    print("MOJPROP_C156_QUOTA_READONLY_DIAGNOSTIC="+
          json.dumps(report(),separators=(",",":"),sort_keys=True))
