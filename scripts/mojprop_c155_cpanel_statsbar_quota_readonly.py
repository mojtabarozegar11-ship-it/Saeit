#!/usr/bin/env python3
"""C155 owner-only account statistics via documented read-only cPanel UAPI.

Exactly one StatsBar::get_stats call, restricted to diskusage/fileusage/
mysqldiskusage. Never print cPanel JSON, usernames, paths, other statistics,
raw errors, file names, email or secrets. Units must be explicit to publish
amounts; zero or "unlimited" quota is unknown, NOT backup authorization.
No backup, database reads, cPanel writes, shell, purchases or HTTP tokens.
"""
from __future__ import annotations
import json
import math
import os
import pwd
import re
import subprocess

OWNER = "zomorod2"
UAPI = "/usr/local/cpanel/bin/uapi"
DISPLAY = "diskusage|fileusage|mysqldiskusage"
ALLOWED_IDS = ("diskusage", "fileusage", "mysqldiskusage")
MAX_JSON = 49152
NUM = re.compile(r"^(?:0|[1-9][0-9]{0,13})(?:\.[0-9]{1,3})?$")
UNITS = frozenset(("B", "KB", "MB", "GB", "TB", "bytes", "files"))


def _number(raw):
    if type(raw) in (int, float) and math.isfinite(raw) and 0 <= raw < 1e14:
        return float(raw)
    if type(raw) is str and NUM.fullmatch(raw):
        return float(raw)
    return None


def stat_row(row: object, expected_id: str) -> dict:
    out = {"available": False, "units": None, "usage": None,
           "maximum": None, "percent_of_limit": None,
           "account_write_headroom_proven": False}
    if type(row) is not dict or row.get("id") != expected_id:
        return out
    if row.get("units") not in UNITS:
        return out
    # The count and max must be in the same provider 'units' row.
    usage = _number(row.get("count", row.get("_count")))
    maximum = _number(row.get("max", row.get("_max")))
    if usage is None:
        return out
    out.update(available=True, units=row["units"], usage=round(usage, 3))
    if maximum is not None and maximum > 0:
        out["maximum"] = round(maximum, 3)
        out["percent_of_limit"] = round(100*usage/maximum, 3)
    # An account-wide quota is not a reversible full backup/restore proof.
    return out


def normalize(payload: object) -> dict:
    result = {
        "api_ok": False, "requested_ids": list(ALLOWED_IDS),
        "response_type": "unavailable",
        "diskusage": stat_row(None,"diskusage"),
        "fileusage": stat_row(None,"fileusage"),
        "mysqldiskusage": stat_row(None,"mysqldiskusage"),
        "account_write_headroom_proven": False,
        "full_database_media_backup_proven": False,
    }
    if type(payload) is not dict or type(payload.get("result")) is not dict:
        return result
    wrapper=payload["result"]
    if wrapper.get("status") not in (1,True):
        return result
    data=wrapper.get("data")
    if type(data) is dict and type(data.get("data")) is list:
        data=data["data"]
    if type(data) is not list or len(data)>12:
        result["response_type"]="unsupported"
        return result
    result["api_ok"]=True
    result["response_type"]="list"
    for name in ALLOWED_IDS:
        rows=[row for row in data if type(row) is dict and row.get("id")==name]
        if len(rows)==1:
            result[name]=stat_row(rows[0],name)
    return result


def query() -> dict:
    try:
        result=subprocess.run(
            [UAPI, "--output=json", "StatsBar", "get_stats",
             "display="+DISPLAY],
            capture_output=True, timeout=15, check=False,
            env={"HOME":"/home/zomorod2","USER":OWNER,
                 "PATH":"/usr/local/cpanel/bin:/usr/bin:/bin"},
        )
        if result.returncode or not 0<len(result.stdout)<=MAX_JSON:
            return normalize(None)
        return normalize(json.loads(result.stdout.decode("utf-8")))
    except (OSError,ValueError,UnicodeError,subprocess.TimeoutExpired):
        return normalize(None)


def report() -> dict:
    out={"schema":"mojprop.cpanel.owner_statsbar_quota.readonly.c155.v1",
         "owner_identity_verified":False,"read_only":True,
         "stats":normalize(None),
         "database_content_accessed":False,"customer_data_accessed":False,
         "file_or_backup_content_read":False,
         "offhost_independent_backup_verified":False,
         "full_app_db_media_restore_verified":False,
         "production_release_authorized":False,
         "payment_created":False,"cost_incurred":False}
    try:
        if pwd.getpwuid(os.geteuid()).pw_name!=OWNER:
            return out
        out["owner_identity_verified"]=True
        out["stats"]=query()
    except (OSError,ValueError,KeyError):
        pass
    return out

if __name__=="__main__":
    print("MOJPROP_C155_ACCOUNT_STATSBAR_READONLY="+
          json.dumps(report(),sort_keys=True,separators=(",",":")))
