#!/usr/bin/env python3
"""Read-only MojPlayWin live source-lineage inventory.

Reports only file presence, size and SHA-256 for a fixed allowlist.
Never reads .env, mailbox data, database values, credentials or customer data.
"""
from __future__ import annotations
import hashlib
import json
from pathlib import Path

ROOT=Path("/home/zomorod2/Saeit-staging").resolve()
FILES=(
    "config/settings.py",
    "config/urls.py",
    "services/mpw_walletless_commercial_intent.py",
    "services/mpw_trx_commercial_web.py",
    "services/mpw_trx_public_pages.py",
    "services/mpw_trx_email_recovery.py",
    "services/mpw_trx_guest_commerce.py",
    "core/guest_recovery_models.py",
    "core/migrations/0047_mpw_guest_email_recovery.py",
    "core/migrations/0049_mpw_guest_email_recovery.py",
    "mpw_commerce/urls.py",
    "mpw_commerce/views.py",
)
def item(rel):
    p=(ROOT/rel)
    out={"path":rel,"present":False,"symlink":False,"size":None,"sha256":None}
    try:
        out["symlink"]=p.is_symlink()
        if out["symlink"] or not p.is_file():
            return out
        size=p.stat().st_size
        if size>2_000_000:
            out["present"]=True; out["size"]=size; return out
        out["present"]=True; out["size"]=size
        out["sha256"]=hashlib.sha256(p.read_bytes()).hexdigest()
    except (OSError,ValueError):
        return out
    return out
if not ROOT.is_dir() or ROOT.is_symlink():
    raise SystemExit("LIVE_ROOT_MISMATCH")
print("MPW_LIVE_SOURCE_LINEAGE_READONLY="+json.dumps({
    "root":str(ROOT),
    "files":[item(x) for x in FILES],
    "no_host_changes":True,
    "no_customer_data_read":True,
},sort_keys=True))
