#!/usr/bin/env python3
"""C157 diagnose StatsBar UAPI response *shape* with no values or identifiers.

Run through the already pinned owner-only factory→cPanel SSH relay. Query a
single documented read-only StatsBar.get_stats endpoint. NEVER log provider
payload, arbitrary field keys, field values, domain/user/host/email, SQL,
credentials, customer data, backups or errors. Validated fixed whitelist only.
No backup, payment, state modification or production deployment.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import pwd
import stat
import subprocess

OWNER="zomorod2"
BIN="/usr/local/cpanel/bin/uapi"
ARGS=(BIN,"--output=json","StatsBar","get_stats",
      "display=diskusage|mysqldiskusage|fileusage")
MAX_BYTES=65536
MAX_ITEMS=128
KNOWN=("diskusage","mysqldiskusage","fileusage")
FIELD_TYPES=("id","name","count","_count","max","_max","units","normalized",
             "percent","value","used","limit","diskusage","mysqldiskusage")
DATA_CONTAINERS=("data","stats","result")
SHAPES=("none","list","dict","other","oversized")
STATES=("not_run","missing","unsafe_binary","process_error","invalid_json",
        "bad_envelope","status_failure","ok")


def trusted_binary():
    """Verify any symlink target stays in root-owned cPanel tree."""
    try:
        link=os.lstat(BIN)
        if stat.S_ISLNK(link.st_mode):
            target=os.path.realpath(BIN)
            if not target.startswith("/usr/local/cpanel/") or link.st_uid!=0:
                return False
            st=os.stat(target)
            if st.st_uid!=0 or st.st_mode & 0o022:
                return False
        else:
            st=link
        return stat.S_ISREG(st.st_mode) and os.access(BIN,os.X_OK)
    except OSError:
        return False


def type_class(x):
    if type(x) is dict: return "dict"
    if type(x) is list: return "list"
    if x is None: return "none"
    return "other"


def _rows(value):
    """A small read-only collection, allowing only fixed known wrapper keys."""
    if type(value) is list:
        return value if len(value)<=MAX_ITEMS else None
    if type(value) is dict:
        for k in DATA_CONTAINERS:
            child=value.get(k)
            if type(child) is list and len(child)<=MAX_ITEMS:
                return child
        # A mapping of stats keyed by fixed, known identifiers is also possible.
        selected=[v for k,v in value.items() if k in KNOWN and type(v) is dict]
        return selected[:MAX_ITEMS] if selected else []
    return []


def shape(value):
    out={"status":"bad_envelope","top_result_shape":"none",
         "data_shape":"none","data_nested_shape":"none",
         "rows_bounded":False,"row_count":0,"dict_rows":0,
         "known_id_matches":{n:0 for n in KNOWN},
         "known_name_matches":{n:0 for n in KNOWN},
         "field_presence":{k:0 for k in FIELD_TYPES},
         "unit_declared_rows":0,"unknown_id_rows":0,
         "has_raw_reason_or_errors":False,
         "actual_account_quota_proven":False}
    if type(value) is not dict or type(value.get("result")) is not dict:
        return out
    r=value["result"]
    out["top_result_shape"]="dict"
    if r.get("status") not in (1,True):
        out["status"]="status_failure"
        return out
    out["status"]="ok"
    out["has_raw_reason_or_errors"]=("errors" in r or "reason" in r)
    data=r.get("data")
    out["data_shape"]=type_class(data)
    if type(data) is dict:
        out["data_nested_shape"]=type_class(data.get("data"))
    rows=_rows(data)
    if rows is None:
        out["data_shape"]="oversized"
        return out
    out["rows_bounded"]=True
    out["row_count"]=len(rows)
    for row in rows:
        if type(row) is not dict:
            continue
        out["dict_rows"]+=1
        for key in FIELD_TYPES:
            if key in row:
                out["field_presence"][key]+=1
        if type(row.get("units")) is str:
            out["unit_declared_rows"]+=1
        identity=row.get("id")
        alias=row.get("name")
        if identity not in KNOWN:
            out["unknown_id_rows"]+=1
        for name in KNOWN:
            if identity==name: out["known_id_matches"][name]+=1
            if alias==name: out["known_name_matches"][name]+=1
    return out


def report():
    out={"schema":"mojprop.cpanel.statsbar_uapi_shape.c157.v1",
         "read_only":True,"owner_identity_verified":False,
         "cli":"not_run","payload_shape":shape(None),
         "db_or_customer_content_accessed":False,
         "provider_payload_logged":False,"backup_created":False,
         "offhost_backup_verified":False,"independent_restore_verified":False,
         "production_deploy_authorized":False,"cost_incurred":False}
    try:
        if pwd.getpwuid(os.geteuid()).pw_name!=OWNER:
            return out
        out["owner_identity_verified"]=True
        if not trusted_binary():
            out["cli"]="unsafe_binary"
            return out
        proc=subprocess.run(ARGS,capture_output=True,timeout=16,check=False,
                            env={"HOME":"/home/zomorod2","USER":OWNER,
                                 "PATH":"/usr/local/cpanel/bin:/usr/bin:/bin"})
        if proc.returncode or not 0<len(proc.stdout)<=MAX_BYTES:
            out["cli"]="process_error"
            return out
        try:
            payload=json.loads(proc.stdout.decode("utf-8"))
        except (ValueError,UnicodeError):
            out["cli"]="invalid_json"
            return out
        out["payload_shape"]=shape(payload)
        out["cli"]=out["payload_shape"]["status"]
    except (OSError,subprocess.TimeoutExpired):
        out["cli"]="process_error"
    return out

if __name__=="__main__":
    print("MOJPROP_C157_UAPI_SHAPE_READONLY="+
          json.dumps(report(),sort_keys=True,separators=(",",":")))
