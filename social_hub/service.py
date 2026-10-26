"""Single-job authenticated worker; no automatic resends or background activity."""
from __future__ import annotations
import os

from .adapters import Blocked, Uncertain, send
from .transport import http_transport
from .youtube import upload_video

def connection_status(store, env=None):
    env = os.environ if env is None else env
    out = []
    for account in store.accounts():
        token_alias = account["token_env"]
        out.append({
            "account_id": account["id"], "brand": account["brand"],
            "platform": account["platform"], "destination": account["destination"],
            "credential_env_name": token_alias,
            "owner_verified": bool(account["verified"]),
            "token_present": bool(env.get(token_alias, "")),
            "outbound_enabled": env.get("MPW_SOCIAL_OUTBOUND_ENABLED") == "1",
            # Configuration is not evidence that the provider accepted the OAuth
            # scope, recognizes account ownership, or permits publishing.
            "configuration_ready": bool(account["verified"]) and bool(env.get(token_alias, "")),
            "connected": False,
            "provider_verified": False,
        })
    return out

def run_one(store, post_id, *, env=None, transport=None, execute=False, actor="private-worker"):
    """Publish just one approved due item. CLI/worker MUST use owner-approved path.

    A missing capability, token or execution flag never writes a dispatch receipt.
    Once a network attempt starts, any ambiguous failure is quarantined for manual
    review; no retry may occur under the same ID.
    """
    env = os.environ if env is None else env
    if execute is not True or env.get("MPW_SOCIAL_OUTBOUND_ENABLED") != "1":
        raise Blocked("Outbound mode disabled")
    item = store.post(post_id)
    if not item or item["state"] != "approved":
        raise Blocked("Only an approved publication may be dispatched")
    account = store.account(item["account_id"])
    if not account or not account["verified"] or account["brand"] != item["brand"]:
        raise Blocked("Official account ownership not verified")
    token = env.get(account["token_env"], "").strip()
    if len(token) < 6:
        raise Blocked("No private token configured for exact account")
    if not item["approved_by"] or not item["approved_at"]:
        raise Blocked("Server-side approval record missing")
    import json
    content = json.loads(item["payload"])
    import hashlib
    digest = hashlib.sha256(json.dumps(content,sort_keys=True,
                                ensure_ascii=False,separators=(",",":")).encode("utf-8")).hexdigest()
    if digest != item["payload_hash"]:
        raise Blocked("Content integrity changed after approval")
    if account["platform"] == "mastodon":
        from .adapters import _server
        approved = {v.strip() for v in env.get("MPW_SOCIAL_ALLOWED_MASTODON_ORIGINS","").split(",") if v.strip()}
        if _server(account.get("instance", "")) not in approved:
            raise Blocked("Mastodon instance is not in explicit private allowlist")
    if account["platform"] == "youtube" and not env.get("MPW_SOCIAL_MEDIA_ROOT"):
        raise Blocked("Private YouTube media root must be configured")
    from datetime import datetime, timedelta, timezone
    recent_hour = (datetime.now(timezone.utc)-timedelta(hours=1)).isoformat(timespec="seconds").replace("+00:00","Z")
    recent_minute = (datetime.now(timezone.utc)-timedelta(minutes=1)).isoformat(timespec="seconds").replace("+00:00","Z")
    recent = store.db.execute(
        "SELECT e.at FROM events e JOIN posts p ON p.id=e.subject "
        "WHERE p.account_id=? AND e.event='dispatch_claimed' AND e.at>=? ORDER BY e.at DESC LIMIT 20",
        (account["id"], recent_hour)).fetchall()
    if len(recent) >= 10 or sum(1 for row in recent if row["at"]>=recent_minute)>=2:
        raise Blocked("Per-account rate budget exceeded; manual scheduling required")
    post, account = store.claim(post_id, actor=actor)
    transport = http_transport if transport is None else transport
    try:
        a = {**account, "verified": bool(account["verified"])}
        if a["platform"] == "youtube":
            result = upload_video(a, content, token, transport,
                                  media_root=env["MPW_SOCIAL_MEDIA_ROOT"])
        else:
            result = send(a, content, token, transport)
        if result.state not in ("published","submitted","draft_created"):
            raise Uncertain("Unsupported external finality")
    except Exception:
        # A prior remote POST may have succeeded despite a timeout/error.
        store.settle(post_id,"needs_review", actor=actor)
        raise Uncertain("Publication outcome uncertain; manual reconciliation required") from None
    store.settle(post_id,result.state,result.remote_id,result.note,actor=actor)
    return {"post_id":post_id, "brand":post["brand"],
            "platform":account["platform"], "state":result.state,
            "remote_id":result.remote_id, "note":result.note}

def run_due(store, *, limit=5, env=None, transport=None, execute=False):
    """Bounded private scheduler: never auto-retries an ambiguous outcome."""
    if execute is not True:
        raise Blocked("Explicit scheduler execution required")
    if not 1 <= int(limit) <= 5:
        raise Blocked("Maximum 5 publications per invocation")
    from .store import utc_now
    due = store.db.execute(
        "SELECT id FROM posts WHERE state='approved' AND scheduled_at<=? "
        "ORDER BY scheduled_at,id LIMIT ?", (utc_now(),int(limit))).fetchall()
    outcomes = []
    for row in due:
        try:
            outcomes.append(run_one(store,row["id"],env=env,transport=transport,execute=True))
        except (Blocked,Uncertain):
            outcomes.append({"post_id":row["id"],"state":"blocked_or_needs_review"})
    return outcomes
