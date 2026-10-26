"""One-phase, token-free registry onboarding for 45 supported platform types.

Only imports actual owner-provided account identifiers. Never manufactures social
identities, accepts OAuth tokens, or changes account verification/publication state.
Manifest import is atomic so one invalid record cannot partially create accounts.
"""
from __future__ import annotations
from datetime import datetime
import json
import re
from urllib.parse import urlsplit
import uuid

from .adapters import Blocked
from .catalog import BRANDS, RESTRICTED_HANDLES, platform, PLATFORMS
from .store import utc_now

HOSTS = {
    "telegram": {"t.me"},
    "discord": {"discord.com","www.discord.com"},
    "instagram": {"instagram.com","www.instagram.com"},
    "facebook_pages": {"facebook.com","www.facebook.com"},
    "threads": {"threads.net","www.threads.net"},
    "youtube": {"youtube.com","www.youtube.com","m.youtube.com"},
    "linkedin": {"linkedin.com","www.linkedin.com"},
    "tiktok": {"tiktok.com","www.tiktok.com"},
    "x": {"x.com","www.x.com"},
    "pinterest": {"pinterest.com","www.pinterest.com"},
    "reddit": {"reddit.com","www.reddit.com"},
    "bluesky": {"bsky.app"},
    "whatsapp_business": {"wa.me"},
    "google_business_profile": {"google.com","www.google.com","maps.google.com"},
    "zenodo": {"zenodo.org"},
    "github_releases": {"github.com"},
    "orcid": {"orcid.org"},
    "google_scholar": {"scholar.google.com"},
    "researchgate": {"researchgate.net","www.researchgate.net"},
    "academia": {"academia.edu","www.academia.edu"},
    "ssrn": {"ssrn.com","www.ssrn.com"},
    "huggingface": {"huggingface.co"},
    "medium": {"medium.com","www.medium.com"},
    "substack": {"substack.com","www.substack.com"},
    "quora": {"quora.com","www.quora.com"},
    "devto": {"dev.to"},
    "alibaba": {"alibaba.com","www.alibaba.com"},
    "globalsources": {"globalsources.com","www.globalsources.com"},
    "madeinchina": {"made-in-china.com","www.made-in-china.com"},
    "europages": {"europages.com","www.europages.com"},
    "kompass": {"kompass.com","www.kompass.com"},
    "crunchbase": {"crunchbase.com","www.crunchbase.com"},
    "trustpilot": {"trustpilot.com","www.trustpilot.com"},
    "steam": {"store.steampowered.com","steamcommunity.com"},
    "itchio": {"itch.io"},
    "googleplay": {"play.google.com"},
    "appstore": {"apps.apple.com"},
    "kdp": {"amazon.com","www.amazon.com","kdp.amazon.com"},
    "gumroad": {"gumroad.com"},
    "payhip": {"payhip.com"},
    "udemy": {"udemy.com","www.udemy.com"},
    "patreon": {"patreon.com","www.patreon.com"},
    "kofi": {"ko-fi.com"},
    "producthunt": {"producthunt.com","www.producthunt.com"},
    "snapchat": {"snapchat.com","www.snapchat.com"},
}
# Host exceptions for verified service subdomains: Substack creator pages.
SUBDOMAIN_BASES = {"substack":"substack.com","medium":"medium.com",
                   "itchio":"itch.io","payhip":"payhip.com",
                   "gumroad":"gumroad.com","mastodon":None}
MAX_ROWS = 120

def _valid_url(value,network,instance):
    if not value:
        return ""
    if not isinstance(value,str) or len(value)>600:
        raise Blocked("Invalid public profile URL")
    u=urlsplit(value)
    if (u.scheme!="https" or not u.hostname or u.username or u.password
        or u.port or u.fragment or u.query or not u.path.startswith("/")
        or len(u.path)<2 or "\\" in value or any(ord(c)<32 for c in value)):
        raise Blocked("Profile URL must be a clean official HTTPS URL")
    host=u.hostname.lower()
    known=HOSTS.get(network,set())
    base=SUBDOMAIN_BASES.get(network)
    if network=="mastodon":
        if not instance:
            raise Blocked("Mastodon profile needs a verified instance")
        k=urlsplit(instance)
        if (k.scheme!="https" or not k.hostname or k.port or k.username or k.password
            or k.query or k.fragment or k.path not in ("","/")):
            raise Blocked("Mastodon instance must be a safe HTTPS origin")
        if host != k.hostname.lower():
            raise Blocked("Mastodon profile and declared instance differ")
    elif host not in known and not (base and host.endswith("."+base) and host!=base):
        raise Blocked("Profile URL does not belong to the declared network")
    if any(term in value.casefold() for term in RESTRICTED_HANDLES):
        raise Blocked("Restricted promotional profile")
    return value

def validate_manifest(value):
    if isinstance(value,str):
        if len(value)>130_000:
            raise Blocked("Manifest too large")
        try:
            value=json.loads(value)
        except ValueError:
            raise Blocked("Malformed account onboarding JSON") from None
    if not isinstance(value,dict) or set(value)!={"schema_version","owner_confirmed","accounts"}:
        raise Blocked("Expected schema_version, owner_confirmed and accounts only")
    if value["schema_version"]!=1 or value["owner_confirmed"] is not True:
        raise Blocked("Owner confirmation of genuine accounts required")
    entries=value["accounts"]
    if not isinstance(entries,list) or not 0<=len(entries)<=MAX_ROWS:
        raise Blocked("Manifest must contain at most 120 actual accounts")
    result=[]
    seen=set()
    for index,row in enumerate(entries):
        if not isinstance(row,dict) or set(row)-{"brand","platform","destination","public_url","instance"}:
            raise Blocked("Unexpected fields in row "+str(index+1)+"; credentials forbidden")
        if not {"brand","platform","destination"}<=set(row):
            raise Blocked("Missing brand, platform or destination in row "+str(index+1))
        brand,name,dest=row["brand"],row["platform"],row["destination"]
        if brand not in BRANDS:
            raise Blocked("Unsupported brand")
        meta=platform(name)
        if not isinstance(dest,str) or not 2<=len(dest)<=180 or any(ord(c)<32 for c in dest):
            raise Blocked("Invalid account identifier")
        if any(term in dest.casefold() for term in RESTRICTED_HANDLES):
            raise Blocked("Restricted promotional account")
        instance=row.get("instance","")
        if not isinstance(instance,str) or len(instance)>200:
            raise Blocked("Invalid instance value")
        if name=="mastodon" and instance:
            from .adapters import _server
            instance=_server(instance)
        elif instance:
            raise Blocked("Only Mastodon records may include an instance")
        url=_valid_url(row.get("public_url",""),name,instance)
        key=(brand,name,dest)
        if key in seen:
            raise Blocked("Duplicate account in manifest")
        seen.add(key)
        result.append({"brand":brand,"platform":name,"destination":dest,
                       "public_url":url,"instance":instance,
                       "write_api_implemented":meta.sendable})
    return result

def preview(store,manifest):
    records=validate_manifest(manifest)
    existing={(r["brand"],r["platform"],r["destination"]):r for r in store.accounts()}
    add, unchanged = [], []
    for r in records:
        key=(r["brand"],r["platform"],r["destination"])
        old=existing.get(key)
        if old:
            if old["public_url"]!=r["public_url"] or old["instance"]!=r["instance"]:
                raise Blocked("Account already registered with different URL/instance")
            unchanged.append({**r,"account_id":old["id"]})
        else:
            add.append(r)
    return {"to_register":add,"already_registered":unchanged,
            "would_send_posts":False,"would_connect_apis":False,
            "credentials_needed_afterwards":len(add)}

def register(store,manifest,*,actor):
    if not isinstance(actor,str) or not actor.startswith("django:") and not actor.startswith("owner-cli:"):
        raise Blocked("Authenticated administrative actor is required")
    planned=preview(store,manifest)
    added=[]
    with store.transaction():
        for r in planned["to_register"]:
            # Re-check under lock: concurrent imports remain atomic.
            old=store.db.execute(
                "SELECT id FROM accounts WHERE brand=? AND platform=? AND destination=?",
                (r["brand"],r["platform"],r["destination"])).fetchone()
            if old:
                raise Blocked("Concurrent account import; retry preview")
            aid=uuid.uuid4().hex
            alias="MPW_SOCIAL_"+r["brand"].upper()+"_"+r["platform"].upper()+"_"+aid.upper()+"_TOKEN"
            store.db.execute(
                "INSERT INTO accounts(id,brand,platform,destination,public_url,instance,token_env,created_at) "
                "VALUES (?,?,?,?,?,?,?,?)",
                (aid,r["brand"],r["platform"],r["destination"],r["public_url"],
                 r["instance"],alias,utc_now()))
            store.event(aid,r["brand"],actor,"bulk_account_registered",
                        "unverified;no_token;no_external_publication")
            added.append({"account_id":aid,"brand":r["brand"],"platform":r["platform"]})
    return {"registered":added,"previously_registered":len(planned["already_registered"]),
            "connected":0,"published":0}
