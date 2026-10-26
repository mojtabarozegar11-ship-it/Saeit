"""Owner's one-phase API activation checklist, intentionally free of credentials.

Shows exact per-account environment variable *names* and provider
requirements; never token values, private owner proof, emails or provider data.
This checklist is a plan, not evidence of live API approval.
"""
from __future__ import annotations
import os

from .catalog import BRANDS, PLATFORMS
from .diagnostics import SUPPORTED as READ_ONLY_PROBES
from .service import connection_status
from .adapters import Blocked

def build_connection_plan(store, *, brands, env=None):
    env=os.environ if env is None else env
    if not isinstance(brands,(set,list,tuple)) or not set(brands).issubset(BRANDS):
        raise Blocked("Invalid brand scope")
    permitted=set(brands)
    status={r["account_id"]:r for r in connection_status(store,env=env)}
    rows=[]
    for account in store.accounts():
        if account["brand"] not in permitted:
            continue
        p=PLATFORMS[account["platform"]]
        current=status.get(account["id"],{})
        api_needed=p.sendable
        checked=current.get("provider_check_state","not_checked")
        if not account["verified"]:
            action="owner_profile_attestation_required"
        elif not api_needed:
            action="manual_public_profile_only"
        elif not current.get("token_present"):
            action="provider_app_approval_and_private_token_required"
        elif checked in ("failed","stale"):
            action="review_and_repeat_read_only_diagnostic"
        elif checked in ("not_checked","credential_valid_only"):
            action="read_only_identity_or_scope_check_required"
        else:
            action="separate_publish_scope_and_live_receipt_test_required"
        rows.append({
            "account_id":account["id"],
            "brand":account["brand"],
            "provider":p.key,
            "provider_label":p.label,
            "category":p.category,
            "auth_type":p.auth,
            "official_documentation":p.docs,
            "provider_constraint":p.constraint,
            "write_adapter_locally_implemented":p.sendable,
            "read_only_verifier_locally_implemented":p.key in READ_ONLY_PROBES,
            "owner_profile_attested":bool(account["verified"]),
            "credential_env_name":account["token_env"] if api_needed else None,
            "credential_configured_privately":bool(current.get("token_present")) if api_needed else False,
            "last_read_only_check":checked if api_needed else "not_applicable",
            "publishing_permission_verified":False,
            "next_action":action
        })
    rows.sort(key=lambda x:(x["brand"],x["provider"],x["account_id"]))
    return {
        "schema_version":1,"private_staff_only":True,
        "credentials_included":False,"publishing_enabled_by_this_plan":False,
        "brands":sorted(permitted),"account_count":len(rows),
        "api_bearing_account_count":sum(1 for r in rows if r["write_adapter_locally_implemented"]),
        "provider_identity_read_verified":sum(1 for r in rows if
            r["last_read_only_check"]=="identity_verified" and r["credential_configured_privately"]),
        "items":rows,
        "disclaimer":"Provider authorization, quota, write scopes and a real post receipt are independent and not implied by this checklist."
    }
