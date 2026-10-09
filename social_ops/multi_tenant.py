"""Multi-tenant social dispatch planner. Standard library only; never posts directly."""
import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

MAX_TENANTS = 50
MAX_CHANNELS_PER_TENANT = 20
SUPPORTED = {"instagram", "facebook", "youtube", "tiktok", "threads", "pinterest", "x", "linkedin", "telegram", "website", "blog"}
@dataclass(frozen=True)
class Destination:
    tenant_id: str
    destination_id: str
    network: str
    account_ref: str
    enabled: bool = False
    authorized: bool = False

def validate(registry):
    tenants = registry.get("tenants", [])
    if len(tenants) > MAX_TENANTS:
        raise ValueError("Tenant limit exceeded")
    ids = set()
    destinations = set()
    for tenant in tenants:
        tid = tenant["id"]
        if not tid or tid in ids:
            raise ValueError("Duplicate/empty tenant")
        ids.add(tid)
        channels = tenant.get("destinations", [])
        if len(channels) > MAX_CHANNELS_PER_TENANT:
            raise ValueError("Destination limit exceeded")
        for channel in channels:
            key = (tid, channel["id"])
            if key in destinations or channel["network"] not in SUPPORTED:
                raise ValueError("Duplicate/unsupported destination")
            destinations.add(key)
    return True

def plan(registry, drafts, now=None):
    """Create pending jobs only for authorized channels. No network I/O."""
    validate(registry)
    now = now or datetime.now(timezone.utc)
    jobs = []
    for tenant in registry["tenants"]:
        tid = tenant["id"]
        draft = drafts.get(tid)
        if not draft or draft.get("brand") != tid or not draft.get("approved") or not draft.get("text"):
            continue
        for dest in tenant.get("destinations", []):
            if not (dest.get("enabled") and dest.get("authorized") and dest.get("account_ref")):
                continue
            if dest["network"] in {"instagram", "pinterest", "tiktok", "youtube"} and not draft.get("media"):
                continue
            payload = f'{tid}|{dest["id"]}|{draft.get("id")}|{draft.get("version",1)}'
            jobs.append({"job_id": hashlib.sha256(payload.encode()).hexdigest()[:24],
                         "tenant_id": tid, "destination_id": dest["id"],
                         "network": dest["network"], "account_ref": dest["account_ref"],
                         "draft_id": draft["id"], "status": "pending_dispatch",
                         "created_at": now.isoformat()})
    return jobs

def main():
    base = Path(__file__).resolve().parent
    registry = json.loads((base / "tenants.json").read_text(encoding="utf-8"))
    drafts = {}
    for tenant in registry["tenants"]:
        path = base / "output" / (tenant["id"] + "_agent_draft.json")
        if path.exists():
            drafts[tenant["id"]] = json.loads(path.read_text(encoding="utf-8"))
    jobs = plan(registry, drafts)
    out = base / "output"
    out.mkdir(exist_ok=True)
    (out / "dispatch_plan.json").write_text(json.dumps(jobs, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Validated {len(registry['tenants'])} tenants; {len(jobs)} eligible jobs; nothing published")

if __name__ == "__main__":
    main()
