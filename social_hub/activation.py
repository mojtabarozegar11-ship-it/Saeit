"""Owner-only, token-free, evidence-bound onboarding matrix for all provider types.

The catalogue represents supported metadata, NOT provider OAuth, live accounts,
or publishing permissions. Never auto-register accounts, infer account ownership,
or enter API tokens through an HTML form.
"""
from __future__ import annotations

from collections import Counter

from .adapters import Blocked
from .catalog import BRANDS, PLATFORMS, RESTRICTED_HANDLES
from .connection_plan import build_connection_plan
from .diagnostics import SUPPORTED as READ_ONLY_PROVIDERS

# Editorial priorities tailored to each independent brand. Not claims of owning
# accounts and not mandatory accounts. All other catalogued platforms stay visible.
PRIORITIES = {
    "personal": ("linkedin","youtube","x","bluesky","telegram","orcid",
                 "researchgate","github_releases"),
    "zomorod": ("linkedin","facebook_pages","youtube","telegram",
                "google_business_profile","instagram","whatsapp_business"),
    "mojplaywin": ("youtube","tiktok","instagram","discord","telegram","x",
                   "bluesky","reddit","pinterest","facebook_pages","threads"),
}

STEP_LABELS = {
    "register_real_account":"ثبت نشانی و شناسه حساب واقعی",
    "record_owner_proof":"ثبت مدرک مستقل مالکیت",
    "manual_profile_ready":"پروفایل دستی تأییدشده؛ API انتشار عمومی ندارد",
    "provider_app_approval_and_private_token":"اخذ مجوز ارائه‌دهنده و ثبت خصوصی کلید",
    "review_failed_or_expired_read_check":"بازبینی مجوز و اجرای مجدد آزمون خواندنی",
    "read_only_identity_check":"آزمون خواندنی هویت حساب و مقصد",
    "write_scope_and_delivery_confirmation":"تأیید مستقل مجوز ارسال و رسید واقعی",
}

def _allowed_brands(brands):
    if not isinstance(brands,(set,list,tuple)) or not brands or any(b not in BRANDS for b in brands):
        raise Blocked("Authorized brand scope required")
    return sorted(set(brands))

def build_activation_matrix(store, *, brands, env=None):
    """A GET-only enrollment inventory for every known provider x allowed brand.

    Read from the existing private registry, never from public profile guesses.
    The command center may have multiple accounts of the same provider/brand;
    each appears as a distinct private record with a separate next step.
    """
    allowed=_allowed_brands(brands)
    # Reuse the audited private, token-free per-account status constructor.
    state=build_connection_plan(store,brands=allowed,env=env)
    by_key={}
    for a in store.accounts():
        if a["brand"] not in allowed: continue
        if any(handle in (a["destination"]+" "+a["public_url"]).casefold()
               for handle in RESTRICTED_HANDLES):
            # An unexpected legacy/restricted DB row is never offered for activation.
            continue
        by_key.setdefault((a["brand"],a["platform"]),[]).append(a)

    status={a["account_id"]:a for a in state["items"]}
    matrix=[]
    for brand in allowed:
        for name,p in PLATFORMS.items():
            all_accounts=by_key.get((brand,name),())
            account_rows=[]
            for a in all_accounts:
                private=status.get(a["id"],{})
                confirmed=bool(a["verified"])
                authorized=bool(private.get("credential_configured_privately"))
                checked=private.get("last_read_only_check","not_checked")
                if not confirmed:
                    step="record_owner_proof"
                elif not p.sendable:
                    step="manual_profile_ready"
                elif not authorized:
                    step="provider_app_approval_and_private_token"
                elif checked in ("failed","stale"):
                    step="review_failed_or_expired_read_check"
                elif checked in ("not_checked","credential_valid_only"):
                    step="read_only_identity_check"
                else:
                    step="write_scope_and_delivery_confirmation"
                account_rows.append({
                    "account_id":a["id"],  # private staff only
                    "destination":a["destination"],
                    "public_url":a["public_url"],
                    "owner_attested":confirmed,
                    "credential_present":authorized,
                    "read_only_status":checked,
                    "next_action_code":step,
                    "next_action_label":STEP_LABELS[step],
                    "remote_post_permission_verified":False,
                })
            if not account_rows:
                step="register_real_account"
            elif len(account_rows)==1:
                step=account_rows[0]["next_action_code"]
            else:
                step="multiple_account_actions"
            matrix.append({
                "brand":brand,
                "platform":name,
                "label":p.label,
                "category":p.category,
                "auth_type":p.auth,
                "capability_code":p.capability,
                "documentation_url":p.docs,
                "constraint":p.constraint,
                "write_adapter_implemented_locally":p.sendable,
                "read_only_probe_implemented_locally":name in READ_ONLY_PROVIDERS,
                "priority":name in PRIORITIES[brand],
                "registered_accounts":len(account_rows),
                "attested_accounts":sum(int(x["owner_attested"]) for x in account_rows),
                "credential_configured_accounts":sum(int(x["credential_present"]) for x in account_rows),
                "next_action_code":step,
                "next_action_label":STEP_LABELS.get(step,"چند حساب ثبت‌شده؛ بررسی جداگانه هر حساب"),
                "accounts":account_rows,
            })
    matrix.sort(key=lambda row:(allowed.index(row["brand"]),not row["priority"],
                                 list(PRIORITIES[row["brand"]]).index(row["platform"])
                                 if row["priority"] else 999,row["label"].casefold()))
    registered=sum(x["registered_accounts"] for x in matrix)
    attested=sum(x["attested_accounts"] for x in matrix)
    with_keys=sum(x["credential_configured_accounts"] for x in matrix)
    return {
        "schema_version":1,
        "staff_only":True,
        "tokens_included":False,
        "external_publish_enabled_by_plan":False,
        "brands":allowed,
        "catalogue_platform_count":len(PLATFORMS),
        "suggested_priority_platform_pairs":sum(int(r["priority"]) for r in matrix),
        "registered_account_count":registered,
        "owner_attested_account_count":attested,
        "accounts_with_privately_configured_keys":with_keys,
        "provider_posting_permissions_confirmed":0,
        "registered_brand_platform_pairs":sum(int(r["registered_accounts"]>0) for r in matrix),
        "missing_priority_brand_platform_pairs":sum(
            int(r["priority"] and not r["registered_accounts"]) for r in matrix),
        "entries":matrix,
        "notice":"A catalogue entry or locally implemented adapter is not an active social profile, an OAuth grant, or a verified remote publishing permission.",
    }
