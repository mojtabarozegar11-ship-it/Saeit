#!/usr/bin/env python3
"""C154: actual owner cPanel quota UAPI, safely read-only and bounded.

Call exactly documented UAPI Quota::get_quota_info (whole account) and
Quota::get_local_quota_info (local node) without root access or HTTP tokens.
Do not print raw provider JSON, usernames, domains, paths, passwords, errors
or arbitrary provider fields. No backup, migration, delete, payment or deploy.
A failed/stale/unparseable quota is UNKNOWN, never "unlimited" or "safe".
"""
from __future__ import annotations
import json
import os
import pwd
import re
import subprocess

OWNER = "zomorod2"
UAPI = "/usr/local/cpanel/bin/uapi"
FUNCTIONS = ("get_quota_info", "get_local_quota_info")
MAX_BYTES = 65536
NUM_FIELDS = ("used", "limit", "quota", "quota_used", "quota_limit",
              "disk_used", "disk_limit", "bytes_used", "bytes_limit",
              "megabytes_used", "megabytes_limit",
              "diskused", "diskquota", "quotaused", "quotalimit",
              "spaceused", "spacelimit")
FIELD_RE = re.compile(r"^[0-9]{1,15}(?:\.[0-9]{1,3})?$")


def quota_shape(raw: object) -> dict:
    out = {"api_ok": False, "data_kind": "unknown", "matched_numeric_fields": {},
           "same_unit_used_to_limit_ratio_percent": None,
           "account_write_headroom_proven": False}
    if type(raw) is not dict:
        return out
    payload = raw.get("result")
    if type(payload) is not dict:
        return out
    status = payload.get("status")
    if status is not True and status != 1:
        return out
    data = payload.get("data")
    if type(data) is list and len(data) == 1 and type(data[0]) is dict:
        data = data[0]
    if type(data) is not dict:
        out["data_kind"] = "unsupported"
        return out
    out["api_ok"] = True
    out["data_kind"] = "object"
    fields = {}
    for field in NUM_FIELDS:
        candidate = data.get(field)
        if type(candidate) in (int, float) and 0 <= candidate <= 10**15:
            value = float(candidate)
        elif type(candidate) is str and FIELD_RE.fullmatch(candidate):
            value = float(candidate)
        else:
            continue
        if value != value or value in (float("inf"), float("-inf")):
            continue
        fields[field] = value
    out["matched_numeric_fields"] = fields
    # Only ratio, never assert a source backup can be written from quota alone.
    for used, limit in (("bytes_used","bytes_limit"),
                        ("megabytes_used","megabytes_limit"),
                        ("disk_used","disk_limit"), ("quota_used","quota_limit"),
                        ("diskused","diskquota"), ("quotaused","quotalimit"),
                        ("spaceused","spacelimit"), ("used","limit")):
        if used in fields and limit in fields and fields[limit] > 0:
            out["same_unit_used_to_limit_ratio_percent"] = round(
                fields[used]/fields[limit]*100, 3)
            break
    return out


def read_quota(function: str) -> dict:
    if function not in FUNCTIONS:
        raise ValueError("only UAPI Quota read functions allowed")
    base = {"api_ok": False, "data_kind": "unavailable",
            "matched_numeric_fields": {},
            "same_unit_used_to_limit_ratio_percent": None,
            "account_write_headroom_proven": False}
    try:
        cp = subprocess.run(
            [UAPI, "--output=json", "Quota", function],
            capture_output=True, timeout=12, check=False,
            env={"HOME": "/home/zomorod2", "USER": OWNER,
                 "PATH": "/usr/local/cpanel/bin:/usr/bin:/bin"},
        )
        if cp.returncode != 0 or len(cp.stdout) > MAX_BYTES:
            return base
        return quota_shape(json.loads(cp.stdout.decode("utf-8")))
    except (OSError, ValueError, UnicodeError, subprocess.TimeoutExpired):
        return base


def report() -> dict:
    out = {"schema": "mojprop.cpanel.owner_quota.uapi.readonly.c154.v1",
           "read_only": True, "owner_identity_verified": False,
           "whole_account": {"api_ok": False, "data_kind": "unavailable",
                             "matched_numeric_fields": {},
                             "same_unit_used_to_limit_ratio_percent": None,
                             "account_write_headroom_proven": False},
           "local_node": {"api_ok": False, "data_kind": "unavailable",
                          "matched_numeric_fields": {},
                          "same_unit_used_to_limit_ratio_percent": None,
                          "account_write_headroom_proven": False},
           "independent_restore_capacity_proven": False,
           "full_app_db_media_restore_verified": False,
           "backup_created_or_read": False, "customer_data_accessed": False,
           "database_accessed": False, "external_network_called": False,
           "production_deployment_authorized": False,
           "payment_created": False, "cost_incurred": False}
    try:
        if pwd.getpwuid(os.geteuid()).pw_name != OWNER:
            return out
        out["owner_identity_verified"] = True
        out["whole_account"] = read_quota("get_quota_info")
        out["local_node"] = read_quota("get_local_quota_info")
    except (OSError, ValueError, KeyError):
        pass
    return out


if __name__ == "__main__":
    print("MOJPROP_C154_CPIN_ACCOUNT_QUOTA_READONLY=" +
          json.dumps(report(), sort_keys=True, separators=(",", ":")))
