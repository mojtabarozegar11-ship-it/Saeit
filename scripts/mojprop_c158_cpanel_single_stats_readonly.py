#!/usr/bin/env python3
"""C158 one-call owner-only cPanel UAPI diskusage parser, no writes.

cPanel StatsBar may return "78.71 GB" in count and "unlimited" in max
without a separate units field, so earlier numeric-only collectors missed
its disk usage. This script accepts *only* numeric display units, never
prints provider strings, names, account details, errors, paths, or secrets.
Read-only single command using owner identity; no customer/DB/media reads,
backups, migrations, payments, changes or implicit backup authorization.
"""
from __future__ import annotations
import json
import os
import pwd
import re
import stat
import subprocess
from decimal import Decimal, InvalidOperation

OWNER="zomorod2"
BIN="/usr/local/cpanel/bin/uapi"
ARGS=(BIN,"--output=json","StatsBar","get_stats",
      "display=diskusage|mysqldiskusage")
MAX_BYTES=65536
UNITS={"B":1,"KB":1024,"MB":1024**2,"GB":1024**3,"TB":1024**4}
NUMBER=re.compile(r"^(?:0|[1-9][0-9]{0,11})(?:\.[0-9]{1,3})?$")
COMBINED=re.compile(r"^((?:0|[1-9][0-9]{0,11})(?:\.[0-9]{1,3})?) (B|KB|MB|GB|TB)$")


def parsed_bytes(value, hint=None):
    """Canonical bytes from explicit, bounded human-readable cPanel units."""
    if type(value) in (int,float):
        if type(value) is float and not value.is_integer():
            value=str(value)
        else:
            value=str(int(value))
    if type(value) is not str:
        return None
    found=COMBINED.fullmatch(value)
    if found:
        raw,unit=found.groups()
    elif type(hint) is str and hint in UNITS and NUMBER.fullmatch(value):
        raw,unit=value,hint
    else:
        return None
    try:
        bytes_num=Decimal(raw)*UNITS[unit]
    except (InvalidOperation,OverflowError):
        return None
    if bytes_num<0 or bytes_num>10**17:
        return None
    return int(bytes_num)


def item_stats(row, ident):
    out={"present":False,"usage_mb_approx":None,"limit_mb_approx":None,
         "quota_percent_approx":None,"limit_kind":"unknown"}
    if type(row) is not dict or row.get("id")!=ident:
        return out
    out["present"]=True
    hint=row.get("units")
    if hint not in UNITS:
        hint=None
    used=parsed_bytes(row.get("count",row.get("_count")),hint)
    maximum=parsed_bytes(row.get("max",row.get("_max")),hint)
    if used is not None:
        out["usage_mb_approx"]=round(used/1_000_000,3)
    if maximum is not None and maximum>0:
        out["limit_mb_approx"]=round(maximum/1_000_000,3)
        out["limit_kind"]="explicit_finite"
        if used is not None:
            out["quota_percent_approx"]=round(used/maximum*100,2)
    elif type(row.get("max")) is str and row["max"].lower()=="unlimited":
        out["limit_kind"]="provider_unlimited_display_not_account_contract"
    return out


def stats(payload):
    out={"api_success":False,"valid_list":False,"items_count":0,
         "diskusage":item_stats(None,"diskusage"),
         "mysqldiskusage":item_stats(None,"mysqldiskusage"),
         "quota_verified_for_backup_writes":False}
    if type(payload) is not dict or type(payload.get("result")) is not dict:
        return out
    r=payload["result"]
    if r.get("status") not in (1,True):
        return out
    out["api_success"]=True
    data=r.get("data")
    if type(data) is not list or len(data)>12:
        return out
    out["valid_list"]=True
    out["items_count"]=len(data)
    for name in ("diskusage","mysqldiskusage"):
        rows=[x for x in data if type(x) is dict and x.get("id")==name]
        if len(rows)==1:
            out[name]=item_stats(rows[0],name)
    return out


def trusted_binary():
    try:
        link=os.lstat(BIN)
        if stat.S_ISLNK(link.st_mode):
            target=os.path.realpath(BIN)
            if not target.startswith("/usr/local/cpanel/") or link.st_uid!=0:
                return False
            real=os.stat(target)
            if real.st_uid!=0 or real.st_mode & 0o022:
                return False
        else:
            real=link
        return stat.S_ISREG(real.st_mode) and os.access(BIN,os.X_OK)
    except OSError:
        return False


def report():
    out={"schema":"mojprop.cpanel.single_stats_uapi.readonly.c158.v1",
         "read_only":True,"owner_identity_verified":False,
         "api_diagnostic":"not_run",
         "usage":stats(None),
         "account_quota_confirmed_current":False,
         "offhost_independent_app_db_media_restore_verified":False,
         "database_or_customer_data_read":False,
         "source_or_backup_written":False,
         "public_form_deployed":False,
         "production_deployment_authorized":False,
         "cost_incurred":False}
    try:
        if pwd.getpwuid(os.geteuid()).pw_name!=OWNER:
            return out
        out["owner_identity_verified"]=True
        if not trusted_binary():
            out["api_diagnostic"]="binary_untrusted"
            return out
        try:
            cp=subprocess.run(ARGS,capture_output=True,check=False,timeout=14,
                    env={"HOME":"/home/zomorod2","USER":OWNER,
                         "PATH":"/usr/local/cpanel/bin:/usr/bin:/bin"})
        except (OSError,subprocess.TimeoutExpired):
            out["api_diagnostic"]="process_error"
            return out
        if cp.returncode!=0:
            out["api_diagnostic"]="nonzero_return"
            return out
        if not 0<len(cp.stdout)<=MAX_BYTES:
            out["api_diagnostic"]="empty_or_oversized_output"
            return out
        try:
            payload=json.loads(cp.stdout.decode("utf-8"))
        except (ValueError,UnicodeError):
            out["api_diagnostic"]="invalid_json"
            return out
        out["usage"]=stats(payload)
        out["api_diagnostic"]="ok" if out["usage"]["api_success"] else "api_failed"
    except (OSError,ValueError,KeyError):
        out["api_diagnostic"]="unavailable"
    return out

if __name__=="__main__":
    print("MOJPROP_C158_SINGLE_STATS_READONLY="+
          json.dumps(report(),sort_keys=True,separators=(",",":")))
