"""Identity-bound, read-only API connection diagnostics.

NO POST, PUT, mutation, refresh grant, inbox reads, or publishing. A token's
mere existence is never treated as provider authorization. Never return or
persist API tokens, raw provider responses, chat membership rosters or headers.

Runtime response means ONLY token/identity/channel binding was demonstrated
at the check instant, not guaranteed future publishing rights.
"""
from __future__ import annotations

from dataclasses import dataclass
import re
from urllib.parse import quote, urlsplit

from .adapters import Blocked, Uncertain, _server
from .catalog import BRANDS, RESTRICTED_HANDLES
from .transport import http_transport
from .credential_vault import credential_for

@dataclass(frozen=True)
class Diagnostic:
    status: str             # identity_verified | credential_valid_only
    provider_identity: str  # safe, bounded account identifier; do not disclose publicly
    capability: str         # read_verified | channel_admin | token_only
    note_code: str          # safe enum only; no provider-supplied text

SUPPORTED = frozenset({
    "telegram", "discord", "youtube", "mastodon", "bluesky",
    "x", "facebook_pages", "instagram", "tiktok", "whatsapp_business",
    "linkedin", "reddit", "pinterest", "github_releases",
})

def _valid_identity(value):
    if not isinstance(value, (str, int)) or not 1 <= len(str(value)) <= 160:
        raise Uncertain("Provider identity missing")
    txt = str(value)
    if any(ord(ch) < 33 for ch in txt):
        raise Uncertain("Provider identity unsafe")
    return txt

def _get(transport, url, headers):
    if not url.startswith("https://"):
        raise Blocked("Non-HTTPS provider endpoint refused")
    response = transport("GET", url, None, headers)
    if response.status != 200 or not isinstance(response.payload, dict):
        raise Uncertain("Provider read-only authentication failed")
    return response.payload

def _bearer(token):
    if not isinstance(token, str) or not 6 <= len(token) <= 6000 or "\n" in token or "\r" in token:
        raise Blocked("No safe scoped token configured")
    return {"Authorization": "Bearer " + token, "Accept": "application/json"}

def _match(a,b):
    if _valid_identity(a).casefold() != _valid_identity(b).casefold():
        raise Blocked("Authenticated API identity does not match registered owner account")

def inspect(account: dict, token: str, *, transport=None, allowed_instances=()):
    """Check one explicitly owned account via its provider's official read endpoint.

    The CLI/UI caller must enforce authorization and schedule frequency. The only
    non-static outbound URL is Mastodon and it MUST match a separately configured
    exact HTTPS origin allowlist; no fallback HTTP or redirects.
    """
    if not isinstance(account,dict) or account.get("brand") not in BRANDS:
        raise Blocked("Account not in the three approved brands")
    if account.get("verified") is not True:
        raise Blocked("Public profile ownership attestation is missing")
    platform, destination = account.get("platform"), account.get("destination")
    if platform not in SUPPORTED:
        raise Blocked("Read-only validation not implemented for provider")
    if not isinstance(destination,str) or not 2 <= len(destination) <= 180:
        raise Blocked("Registered destination missing")
    if any(term in destination.casefold() for term in RESTRICTED_HANDLES):
        raise Blocked("Restricted account is excluded")
    if transport is None:
        transport=http_transport
    headers = _bearer(token)

    if platform=="telegram":
        if not re.fullmatch(r"[0-9]{5,15}:[A-Za-z0-9_-]{20,100}", token):
            raise Blocked("Invalid Bot API credential shape")
        if not re.fullmatch(r"(?:-?[0-9]{5,20}|@[A-Za-z][A-Za-z0-9_]{4,31})",destination):
            raise Blocked("Telegram destination identifier invalid")
        base="https://api.telegram.org/bot"+token+"/"
        # Telegram requires the token in URL; never log URLs or provider errors.
        me=_get(transport,base+"getMe",{"Accept":"application/json"})
        if me.get("ok") is not True or not (me.get("result") or {}).get("is_bot"):
            raise Uncertain("Telegram bot authentication not confirmed")
        bot_id=(me["result"]).get("id")
        _valid_identity(bot_id)
        chat=_get(transport,base+"getChat?chat_id="+quote(destination,safe=""),
                  {"Accept":"application/json"})
        if chat.get("ok") is not True:
            raise Uncertain("Telegram destination inaccessible")
        chat_data=chat.get("result") or {}
        if chat_data.get("type") != "channel":
            raise Blocked("Only Telegram channels can pass broadcast-admin check")
        if destination.startswith("@"):
            _match(str(chat_data.get("username","")).lstrip("@"),destination.lstrip("@"))
        else:
            _match(chat_data.get("id"),destination)
        admins=_get(transport,base+"getChatAdministrators?chat_id="+quote(destination,safe=""),
                    {"Accept":"application/json"})
        if admins.get("ok") is not True or not isinstance(admins.get("result"),list):
            raise Uncertain("Telegram administrator read failed")
        owns=False
        for item in admins["result"]:
            if not isinstance(item,dict):
                continue
            user=item.get("user") or {}
            if str(user.get("id")) != str(bot_id):
                continue
            owns = item.get("status")=="creator" or (
                item.get("status")=="administrator" and item.get("can_post_messages") is True)
            break
        if not owns:
            raise Blocked("Telegram bot cannot be verified as channel post administrator")
        return Diagnostic("identity_verified",str(bot_id),"channel_admin","bot_and_channel_admin_checked")

    if platform=="discord":
        if not re.fullmatch(r"[0-9]{15,22}",destination):
            raise Blocked("Discord channel ID invalid")
        # Bot tokens use a Bot authorization scheme; user OAuth bearer is different.
        me=_get(transport,"https://discord.com/api/v10/users/@me",
                {"Authorization":"Bot "+token,"Accept":"application/json"})
        if me.get("bot") is not True:
            raise Blocked("Discord Bot API credential required")
        bot_id=_valid_identity(me.get("id"))
        channel=_get(transport,"https://discord.com/api/v10/channels/"+destination,
                     {"Authorization":"Bot "+token,"Accept":"application/json"})
        _match(channel.get("id"),destination)
        return Diagnostic("credential_valid_only",bot_id,"token_only",
                          "channel_access_not_proof_of_send_permission")

    if platform=="youtube":
        if not re.fullmatch(r"UC[A-Za-z0-9_-]{20,40}",destination):
            raise Blocked("YouTube channel ID must be its immutable UC identifier")
        result=_get(transport,
            "https://www.googleapis.com/youtube/v3/channels?part=id&mine=true",headers)
        ids=[str(item.get("id")) for item in result.get("items",[])
             if isinstance(item,dict) and item.get("id")]
        if destination not in ids:
            raise Blocked("Authorized YouTube identity not among owned channels")
        return Diagnostic("identity_verified",destination,"read_verified",
                          "owned_channel_read_scope_checked_upload_scope_unknown")

    if platform=="mastodon":
        origin=_server(account.get("instance",""))
        if origin not in set(allowed_instances):
            raise Blocked("Mastodon instance not in private exact-origin allowlist")
        result=_get(transport,origin+"/api/v1/accounts/verify_credentials",headers)
        username=_valid_identity(result.get("username"))
        expected=destination.lstrip("@").split("@")[0]
        _match(username,expected)
        if result.get("id") is None:
            raise Uncertain("Mastodon identity proof incomplete")
        return Diagnostic("identity_verified",str(result["id"]),"read_verified",
                          "instance_and_authenticated_username_checked")

    if platform=="bluesky":
        result=_get(transport,
            "https://bsky.social/xrpc/com.atproto.server.getSession",headers)
        did=_valid_identity(result.get("did"))
        handle=_valid_identity(result.get("handle"))
        if destination.casefold() not in (did.casefold(),handle.casefold()):
            raise Blocked("Authenticated Bluesky DID/handle differs from target")
        return Diagnostic("identity_verified",did,"read_verified",
                          "pds_session_checked_write_scope_unknown")

    if platform=="x":
        if not re.fullmatch(r"[0-9]{1,22}",destination):
            raise Blocked("X expected immutable numeric user ID")
        result=_get(transport,"https://api.x.com/2/users/me",headers)
        ident=_valid_identity((result.get("data") or {}).get("id"))
        _match(ident,destination)
        return Diagnostic("identity_verified",ident,"read_verified",
                          "user_oauth_identity_checked_write_scope_unknown")

    if platform=="facebook_pages":
        if not re.fullmatch(r"[0-9]{5,30}",destination):
            raise Blocked("Facebook Page ID invalid")
        result=_get(transport,"https://graph.facebook.com/v24.0/me?fields=id",headers)
        ident=_valid_identity(result.get("id"))
        _match(ident,destination)
        return Diagnostic("identity_verified",ident,"read_verified",
                          "page_access_token_identity_checked_write_scope_unknown")

    if platform=="instagram":
        if not re.fullmatch(r"[0-9]{5,30}",destination):
            raise Blocked("Instagram Professional numeric ID invalid")
        result=_get(transport,
           "https://graph.facebook.com/v24.0/"+destination+"?fields=id,username",headers)
        ident=_valid_identity(result.get("id"))
        _match(ident,destination)
        return Diagnostic("identity_verified",ident,"read_verified",
                          "professional_account_read_checked_publish_scope_unknown")

    if platform=="tiktok":
        # Requires user.info.basic; the Content Posting API has separate scopes.
        result=_get(transport,
           "https://open.tiktokapis.com/v2/user/info/?fields=open_id",headers)
        ident=_valid_identity((result.get("data") or {}).get("user",{}).get("open_id"))
        _match(ident,destination)
        return Diagnostic("identity_verified",ident,"read_verified",
                          "tiktok_creator_read_checked_post_permission_unknown")

    if platform=="whatsapp_business":
        if not re.fullmatch(r"[0-9]{5,30}",destination):
            raise Blocked("WhatsApp phone-number ID invalid")
        result=_get(transport,
            "https://graph.facebook.com/v24.0/"+destination+
            "?fields=id,display_phone_number",headers)
        ident=_valid_identity(result.get("id"))
        _match(ident,destination)
        return Diagnostic("identity_verified",ident,"read_verified",
                          "phone_number_read_checked_message_templates_not_verified")

    if platform=="linkedin":
        # LinkedIn OIDC permits member identity; organization posting is NOT proven.
        data=_get(transport,"https://api.linkedin.com/v2/userinfo",headers)
        ident=_valid_identity(data.get("sub"))
        if destination.startswith("urn:li:person:"):
            _match(destination.rsplit(":",1)[-1],ident)
            return Diagnostic("identity_verified",ident,"read_verified",
                              "member_oidc_only_organization_scope_unknown")
        return Diagnostic("credential_valid_only",ident,"token_only",
                          "member_oidc_does_not_verify_organization_ownership")

    if platform=="reddit":
        data=_get(transport,"https://oauth.reddit.com/api/v1/me",
            {**headers,"User-Agent":"MojtabaSocialHub/1.0 (owner-authenticated-check)"})
        ident=_valid_identity(data.get("name"))
        return Diagnostic("credential_valid_only",ident,"token_only",
                          "reddit_user_auth_does_not_verify_subreddit_permissions")

    if platform=="pinterest":
        data=_get(transport,"https://api.pinterest.com/v5/user_account",headers)
        ident=_valid_identity(data.get("username"))
        return Diagnostic("credential_valid_only",ident,"token_only",
                          "pinterest_user_read_does_not_verify_board_post_access")

    if platform=="github_releases":
        data=_get(transport,"https://api.github.com/user",
             {**headers,"Accept":"application/vnd.github+json",
              "X-GitHub-Api-Version":"2022-11-28"})
        ident=_valid_identity(data.get("login"))
        return Diagnostic("credential_valid_only",ident,"token_only",
                          "authenticated_user_does_not_verify_repository_release_permission")

    raise Blocked("No read-only verifier available")


def record_one(store, account_id, *, env=None, transport=None,
               allowed_instances=None, actor="owner-cli:verify", force=False):
    """Explicit per-account diagnostic with a 10-minute frequency guard.

    Results are auditable, deterministic, private and never stored as OAuth
    credentials. Provider HTTP failures are stored as generic check status.
    """
    from datetime import datetime, timezone, timedelta
    from .store import utc_now
    import os
    env=os.environ if env is None else env
    account=store.account(account_id)
    if not account:
        raise Blocked("Account record not found")
    if not account["verified"]:
        raise Blocked("Owner attestation required first")
    if account["platform"] not in SUPPORTED:
        raise Blocked("Provider does not support read-only identity checks")
    token=credential_for(account,env=env)
    _bearer(token)
    recent=store.api_check(account_id)
    if recent and not force:
        try:
            checked=datetime.fromisoformat(recent["checked_at"].replace("Z","+00:00"))
        except ValueError:
            raise Blocked("Previous diagnostic timestamp invalid; manual review required") from None
        if checked >= datetime.now(timezone.utc)-timedelta(minutes=10):
            raise Blocked("Provider check already completed recently")
    if allowed_instances is None:
        allowed_instances=[v.strip() for v in env.get(
            "MPW_SOCIAL_ALLOWED_MASTODON_ORIGINS","").split(",") if v.strip()]
    try:
        result=inspect({**account,"verified":bool(account["verified"])},token,
                       transport=transport,allowed_instances=allowed_instances)
        status, note, identity=result.status,result.note_code,result.provider_identity
    except (Uncertain,Blocked):
        # Never repeat provider response bodies, token, URL or raw exception text.
        status,note,identity="failed","read_only_provider_verification_failed",""
    store.record_api_check(account_id,status=status,identity=identity,
                           note=note,actor=actor)
    return {"account_id":account_id,"brand":account["brand"],
            "platform":account["platform"],"status":status,
            "provider_identity_verified":status=="identity_verified",
            "publishing_scope_verified":False,"checked_at":utc_now(),
            "note_code":note}
