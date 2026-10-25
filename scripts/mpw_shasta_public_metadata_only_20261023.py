#!/usr/bin/env python3
"""Read only PUBLIC Shasta wallet metadata. Never access wallet.key."""
from __future__ import annotations
import json,os
from pathlib import Path

root=Path("/home/githubops/.local/share/moj1-shasta-test-20261021")
p=root/"wallet-public.json"
if root.is_symlink() or p.is_symlink() or not p.is_file():
    raise SystemExit("Public test metadata unavailable")
raw=json.loads(p.read_text("utf8"))
if type(raw) is not dict:
    raise SystemExit("Invalid public test metadata")
names=("network","mode","production_approved","address","addressBase58","wallet","chain_id")
public={
    "public_metadata_only":True,
    "network":str(raw.get("network","absent"))[:48],
    "mode":str(raw.get("mode","absent"))[:48],
    "production_field_type":type(raw.get("production_approved")).__name__,
    "production_false":raw.get("production_approved") is False,
    "address_field_presence":{k:bool(raw.get(k)) for k in ("address","addressBase58","wallet")},
    "available_public_keys":sorted(k for k in raw if k in names),
    "secrets_accessed":False,
}
print("MPW_SHASTA_PUBLIC_METADATA="+json.dumps(public,sort_keys=True))
