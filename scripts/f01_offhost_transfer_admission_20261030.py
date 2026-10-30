#!/usr/bin/env python3
"""Fail-closed OFFHOST transfer admission gate. No SSH, writes, or secrets.

Outputs ONLY machine-readable reasons. Read-only evidence does not itself
authorize any live transfer/reboot; this gate is one *necessary* check.
"""
import argparse
import datetime as dt
import json
import math
import sys

MIN_QUOTA_MARGIN = 2.0
MAX_LOAD_PER_CPU = 2.0
MAX_SNAPSHOT_AGE_HOURS = 24
MAX_SOURCE_EVIDENCE_AGE_MINUTES = 20

def decide(e, now):
    reasons=[]
    def require(flag, name):
        if not flag:
            reasons.append(name)
    observed=e.get("observed_utc")
    try:
        t=dt.datetime.fromisoformat(observed.replace("Z","+00:00"))
        require(t.tzinfo is not None and 0 <= (now-t).total_seconds() <= 60*MAX_SOURCE_EVIDENCE_AGE_MINUTES,
                "FRESH_SOURCE_EVIDENCE_REQUIRED")
    except (TypeError,ValueError,AttributeError):
        reasons.append("FRESH_SOURCE_EVIDENCE_REQUIRED")
    cpus=e.get("cpu_count")
    load=e.get("load1")
    require(type(cpus)==int and cpus>=1 and type(load) in (float,int)
            and math.isfinite(load) and load<=cpus*MAX_LOAD_PER_CPU,
            "SOURCE_LOAD_NOT_SAFE")
    free=e.get("source_unprivileged_free_bytes")
    require(type(free)==int and free>=1024**3,"SOURCE_HEADROOM_NOT_SAFE")
    snapshot=e.get("snapshot",{})
    sz=snapshot.get("bytes")
    require(type(sz)==int and 4096<=sz<=3*1024**3,"BOUNDED_SNAPSHOT_REQUIRED")
    try:
        stamp=dt.datetime.fromisoformat(snapshot.get("mtime_utc","").replace("Z","+00:00"))
        require(stamp.tzinfo is not None and 0<=(now-stamp).total_seconds()<=3600*MAX_SNAPSHOT_AGE_HOURS,
                "CURRENT_SNAPSHOT_REQUIRED")
    except (TypeError,ValueError,AttributeError):
        reasons.append("CURRENT_SNAPSHOT_REQUIRED")
    require(snapshot.get("sqlite_consistency_verified") is True,"SQLITE_CONSISTENCY_NOT_PROVEN")
    require(e.get("recipient_public_key_matches_offline_recovery_key") is True,
            "RECOVERY_PAIR_NOT_VERIFIED")
    require(e.get("owner_recovery_key_custody_outside_chat") is True,
            "OFFLINE_RECOVERY_CUSTODY_NOT_CONFIRMED")
    require(e.get("transfer_path_encrypted_only") is True,
            "ENCRYPTED_ONLY_TRANSPORT_NOT_VERIFIED")
    q=e.get("destination",{})
    avail=q.get("available_bytes")
    require(type(avail)==int and type(sz)==int and avail>=int(sz*MIN_QUOTA_MARGIN)
            and q.get("source") not in (None,"","SHARED_FILESYSTEM_ONLY"),
            "OFFHOST_AVAILABLE_QUOTA_NOT_VERIFIED")
    require(e.get("authorized_maintenance_and_io_window") is True,
            "MAINTENANCE_IO_WINDOW_NOT_AUTHORIZED")
    return {
        "schema":"f01-offhost-transfer-admission.v1",
        "status":"ALLOW_FOR_MANUAL_REVIEW_ONLY" if not reasons else "NO_GO",
        "reasons":sorted(set(reasons)),
        "transfer_performed":False,
        "reboot_authorized":False,
        "source_mutated":False
    }

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--evidence-json",required=True)
    a=p.parse_args()
    with open(a.evidence_json,encoding="utf8") as f:
        evidence=json.load(f)
    result=decide(evidence,dt.datetime.now(dt.timezone.utc))
    print(json.dumps(result,sort_keys=True))
    return 0 if result["status"]=="ALLOW_FOR_MANUAL_REVIEW_ONLY" else 2

if __name__=="__main__":
    sys.exit(main())
