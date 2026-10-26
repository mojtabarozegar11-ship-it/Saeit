"""Network request planning and strict input validation.

No imported module performs network calls or reads secrets. Most platforms need
app review, OAuth refresh and per-brand approved scopes before connection.
"""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone
import ipaddress
import json
import re
from urllib.parse import urlsplit, urlencode

from .catalog import BRANDS, MEDIA_HOSTS, RESTRICTED_HANDLES, platform

class Blocked(ValueError):
    pass

class Uncertain(RuntimeError):
    pass

def _require(value, pattern, label):
    if not isinstance(value, str) or not re.fullmatch(pattern, value):
        raise Blocked("Invalid " + label)
    return value

def _text(content, *, limit=10000):
    value = content.get("text", "")
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise Blocked("Text is missing or exceeds platform limit")
    if any(x in value.casefold() for x in RESTRICTED_HANDLES):
        raise Blocked("Restricted promotional account")
    return value.strip()

def _media_url(value):
    if not isinstance(value, str) or len(value) > 1600:
        raise Blocked("Media URL missing")
    x = urlsplit(value)
    if (x.scheme != "https" or x.hostname not in MEDIA_HOSTS or x.username
        or x.password or x.port or x.fragment or x.query
        or not x.path.startswith("/") or len(x.path) < 5):
        raise Blocked("Media URL must be on a controlled HTTPS domain")
    if any(x in value.casefold() for x in RESTRICTED_HANDLES):
        raise Blocked("Restricted promotional account")
    return value

def _server(value):
    if not isinstance(value, str):
        raise Blocked("Unverified Mastodon instance")
    x = urlsplit(value)
    if (x.scheme != "https" or not x.hostname or x.username or x.password or x.port
        or x.query or x.fragment or x.path not in ("", "/")):
        raise Blocked("Mastodon instance must be a clean HTTPS origin")
    host = x.hostname
    if host == "localhost" or "." not in host:
        raise Blocked("Untrusted instance")
    try:
        ipaddress.ip_address(host)
        raise Blocked("Literal IP instances are forbidden")
    except ValueError as exc:
        if isinstance(exc, Blocked):
            raise
    if not re.fullmatch(r"[a-z0-9.-]{4,180}", host) or ".." in host:
        raise Blocked("Invalid instance host")
    return "https://" + host

@dataclass(frozen=True)
class Response:
    status: int
    payload: dict
    headers: dict

@dataclass(frozen=True)
class DispatchOutcome:
    state: str                 # published | submitted | draft_created
    remote_id: str
    note: str = ""

def _auth(token):
    if not isinstance(token, str) or len(token) < 6 or "\n" in token or "\r" in token:
        raise Blocked("Token missing or malformed")
    return {"Authorization": "Bearer " + token}

def _json_headers(token):
    return {**_auth(token), "Content-Type": "application/json"}

def _post(transport, url, body, token, extra_headers=None, form=False):
    headers = _json_headers(token) if not form else {**_auth(token), "Content-Type": "application/x-www-form-urlencoded"}
    headers.update(extra_headers or {})
    resp = transport("POST", url, body, headers)
    if not isinstance(resp, Response):
        raise Uncertain("Transport response invalid")
    if not 200 <= resp.status < 300:
        raise Uncertain("Remote API failed with HTTP status " + str(resp.status))
    return resp

def _id(value, label="remote receipt"):
    if not isinstance(value, (str, int)) or not str(value) or len(str(value)) > 500:
        raise Uncertain(label + " missing in remote response")
    return str(value)

def _check_brand(account):
    if account.get("brand") not in BRANDS:
        raise Blocked("Unknown brand")
    p = platform(account.get("platform"))
    if not p.sendable:
        raise Blocked("Official write API unavailable or not implemented for " + p.key)
    if account.get("verified") is not True:
        raise Blocked("Account ownership not verified")
    return p

def send(account: dict, content: dict, token: str, transport) -> DispatchOutcome:
    """Invoke an explicitly authorized official API using an injected HTTP transport.

    The caller MUST independently verify owner authorization, account permissions,
    exact destination, campaign approval, and rate limits before calling send().
    """
    p = _check_brand(account)
    key = p.key
    destination = account.get("destination")
    if not isinstance(destination, str) or not destination or len(destination) > 180:
        raise Blocked("Destination missing")
    text = content.get("text", "")
    if any(x in json.dumps(content, ensure_ascii=False).casefold() for x in RESTRICTED_HANDLES):
        raise Blocked("Restricted account may not be promoted")
    if key == "telegram":
        _require(destination, r"(?:-?[0-9]{5,20}|@[A-Za-z][A-Za-z0-9_]{4,31})", "Telegram chat")
        _require(token, r"[0-9]{5,15}:[A-Za-z0-9_-]{20,100}", "Telegram token")
        body = {"chat_id": destination, "text": _text(content, limit=4096)}
        # Bot API embeds token in URL; no transport/exception should log URLs.
        resp = transport("POST", "https://api.telegram.org/bot" + token + "/sendMessage",
                         body, {"Content-Type": "application/json"})
        if resp.status != 200 or resp.payload.get("ok") is not True:
            raise Uncertain("Telegram did not confirm send")
        return DispatchOutcome("published", _id((resp.payload.get("result") or {}).get("message_id")))
    if key == "discord":
        _require(destination, r"[0-9]{15,22}", "Discord channel")
        resp = _post(transport, "https://discord.com/api/v10/channels/" + destination + "/messages",
                     {"content": _text(content, limit=2000), "allowed_mentions": {"parse": []}}, token)
        return DispatchOutcome("published", _id(resp.payload.get("id")))
    if key == "x":
        _require(destination, r"[0-9]{1,22}", "X account ID")
        resp = _post(transport, "https://api.x.com/2/tweets", {"text": _text(content, limit=280)}, token)
        return DispatchOutcome("published", _id((resp.payload.get("data") or {}).get("id")))
    if key == "linkedin":
        _require(destination, r"urn:li:(?:person|organization):[A-Za-z0-9_-]{2,100}", "LinkedIn author URN")
        body = {"author": destination, "commentary": _text(content, limit=3000),
                "visibility": "PUBLIC", "distribution": {"feedDistribution": "MAIN_FEED",
                "targetEntities": [], "thirdPartyDistributionChannels": []},
                "lifecycleState": "PUBLISHED", "isReshareDisabledByAuthor": False}
        resp = _post(transport, "https://api.linkedin.com/rest/posts", body, token,
                     {"X-Restli-Protocol-Version": "2.0.0", "Linkedin-Version": "202606"})
        return DispatchOutcome("published", _id(resp.headers.get("x-restli-id") or resp.headers.get("X-Restli-Id")))
    if key == "facebook_pages":
        _require(destination, r"[0-9]{5,30}", "Facebook Page ID")
        resp = _post(transport, "https://graph.facebook.com/v24.0/" + destination + "/feed",
                     {"message": _text(content, limit=50000)}, token)
        return DispatchOutcome("published", _id(resp.payload.get("id")))
    if key == "threads":
        _require(destination, r"[0-9]{5,30}", "Threads user ID")
        body = {"media_type": "TEXT", "text": _text(content, limit=500)}
        container = _post(transport, "https://graph.threads.net/v1.0/" + destination + "/threads",
                          body, token)
        creation_id = _id(container.payload.get("id"), "Threads creation ID")
        published = _post(transport, "https://graph.threads.net/v1.0/" + destination + "/threads_publish",
                          {"creation_id": creation_id}, token)
        return DispatchOutcome("published", _id(published.payload.get("id")))
    if key == "bluesky":
        _require(destination, r"(?:did:[a-z0-9]+:[A-Za-z0-9._:-]{3,160}|[A-Za-z0-9.-]{3,160})", "Bluesky repo")
        now = datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")
        body = {"repo": destination, "collection": "app.bsky.feed.post",
                "record": {"$type": "app.bsky.feed.post",
                           "text": _text(content, limit=300), "createdAt": now}}
        resp = _post(transport, "https://bsky.social/xrpc/com.atproto.repo.createRecord", body, token)
        return DispatchOutcome("published", _id(resp.payload.get("uri")))
    if key == "mastodon":
        origin = _server(account.get("instance", ""))
        resp = _post(transport, origin + "/api/v1/statuses",
                     {"status": _text(content, limit=500)}, token,
                     {"Idempotency-Key": str(content.get("idempotency_key", ""))})
        return DispatchOutcome("published", _id(resp.payload.get("id")))
    if key == "reddit":
        _require(destination, r"[A-Za-z0-9_]{2,21}", "subreddit")
        body = urlencode({"sr": destination, "kind": "self",
                          "title": _text({"text":content.get("title")}, limit=300),
                          "text": _text(content, limit=40000),
                          "api_type": "json"})
        resp = _post(transport, "https://oauth.reddit.com/api/submit", body, token,
                     {"User-Agent": "MojtabaSocialHub/1.0 owner-authorized-api"}, form=True)
        data = resp.payload.get("json", {})
        if data.get("errors"):
            raise Uncertain("Reddit rejected submission")
        entry = data.get("data") or {}
        return DispatchOutcome("published", _id(entry.get("name") or entry.get("url")))
    if key == "google_business_profile":
        _require(destination, r"accounts/[0-9]{3,30}/locations/[0-9]{3,30}", "Business Profile location")
        resp = _post(transport, "https://mybusiness.googleapis.com/v4/" + destination + "/localPosts",
                     {"languageCode": "en-US", "summary": _text(content, limit=1500),
                      "topicType": "STANDARD"}, token)
        return DispatchOutcome("published", _id(resp.payload.get("name")))
    if key == "instagram":
        _require(destination, r"[0-9]{5,30}", "Instagram Professional account")
        image = _media_url(content.get("image_url"))
        container = _post(transport, "https://graph.facebook.com/v24.0/" + destination + "/media",
                          {"image_url": image, "caption": _text(content, limit=2200)}, token)
        creation_id = _id(container.payload.get("id"), "Instagram container")
        published = _post(transport, "https://graph.facebook.com/v24.0/" + destination + "/media_publish",
                          {"creation_id": creation_id}, token)
        return DispatchOutcome("published", _id(published.payload.get("id")))
    if key == "pinterest":
        _require(destination, r"[0-9]{5,30}", "Pinterest board ID")
        resp = _post(transport, "https://api.pinterest.com/v5/pins",
                     {"board_id": destination,
                      "title": _text({"text": content.get("title")}, limit=100),
                      "description": _text(content, limit=800),
                      "media_source": {"source_type": "image_url",
                                       "url": _media_url(content.get("image_url"))}}, token)
        return DispatchOutcome("published", _id(resp.payload.get("id")))
    if key == "tiktok":
        _require(destination, r"[A-Za-z0-9._:-]{3,150}", "TikTok authorized creator")
        if content.get("creator_confirmed") is not True or content.get("explicit_consent") is not True:
            raise Blocked("TikTok creator details and post-specific consent required")
        creator = _post(transport, "https://open.tiktokapis.com/v2/post/publish/creator_info/query/",
                        {}, token)
        data = creator.payload.get("data") or {}
        if (creator.payload.get("error") or {}).get("code") != "ok":
            raise Uncertain("Creator-info request not confirmed")
        privacy = content.get("privacy_level")
        if privacy not in (data.get("privacy_level_options") or []):
            raise Blocked("Selected TikTok privacy not allowed for creator")
        if not isinstance(content.get("disable_comment"), bool) or not isinstance(content.get("disable_duet"), bool) or not isinstance(content.get("disable_stitch"), bool):
            raise Blocked("TikTok creator settings must be explicit")
        video_url = _media_url(content.get("video_url"))
        body = {
            "post_info": {"title": _text(content, limit=2200), "privacy_level": privacy,
                          "disable_comment": content["disable_comment"],
                          "disable_duet": content["disable_duet"],
                          "disable_stitch": content["disable_stitch"]},
            "source_info": {"source": "PULL_FROM_URL", "video_url": video_url},
        }
        post = _post(transport, "https://open.tiktokapis.com/v2/post/publish/video/init/", body, token)
        if (post.payload.get("error") or {}).get("code") != "ok":
            raise Uncertain("TikTok did not accept upload")
        return DispatchOutcome("submitted", _id((post.payload.get("data") or {}).get("publish_id")),
                               "TikTok publication status must be polled; never count init as published")
    if key == "whatsapp_business":
        _require(destination, r"[0-9]{5,30}", "WhatsApp phone-number ID")
        recipient = _require(content.get("recipient"), r"[1-9][0-9]{7,14}", "WhatsApp opted-in recipient")
        if content.get("consent_recorded") is not True:
            raise Blocked("Opt-in proof required before business message")
        template_name = _require(content.get("template"), r"[a-z0-9_]{2,128}", "approved template")
        lang = _require(content.get("language", "en_US"), r"[A-Za-z_]{2,12}", "template language")
        body = {"messaging_product": "whatsapp", "to": recipient, "type": "template",
                "template": {"name": template_name, "language": {"code": lang}}}
        resp = _post(transport, "https://graph.facebook.com/v24.0/" + destination + "/messages", body, token)
        return DispatchOutcome("submitted", _id((resp.payload.get("messages") or [{}])[0].get("id")),
                               "Message submission not proof of delivery or marketing consent")
    if key == "zenodo":
        if content.get("publish") is not False:
            raise Blocked("Only draft deposition; never auto-publish a DOI")
        creators = content.get("creators")
        if not isinstance(creators, list) or not creators or any(not isinstance(c, dict) or not c.get("name") for c in creators):
            raise Blocked("Real author/creator metadata required")
        body = {"metadata": {"title": _text({"text":content.get("title")}, limit=250),
                             "description": _text(content, limit=20000),
                             "creators": creators, "upload_type": "publication",
                             "publication_type": "other"}}
        resp = _post(transport, "https://zenodo.org/api/deposit/depositions", body, token)
        return DispatchOutcome("draft_created", _id(resp.payload.get("id")),
                               "Not published or peer reviewed; files and rights must be checked separately")
    if key == "github_releases":
        _require(destination, r"[A-Za-z0-9_.-]{1,80}/[A-Za-z0-9_.-]{1,100}", "GitHub repository")
        tag = _require(content.get("tag"), r"[A-Za-z0-9._-]{1,80}", "release tag")
        body = {"tag_name": tag, "name": _text({"text":content.get("title")}, limit=200),
                "body": _text(content, limit=120000), "draft": True, "prerelease": False}
        resp = _post(transport, "https://api.github.com/repos/" + destination + "/releases", body, token,
                     {"Accept": "application/vnd.github+json",
                      "X-GitHub-Api-Version": "2022-11-28"})
        return DispatchOutcome("draft_created", _id(resp.payload.get("id")),
                               "Draft only; publishing requires separate approval")
    if key == "youtube":
        raise Blocked("YouTube video bytes require the dedicated resumable media uploader")
    raise Blocked("No supported writer for " + key)
