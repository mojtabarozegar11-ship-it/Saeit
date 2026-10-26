"""Explicit platform capability matrix. 'manual' NEVER means API publishable."""
from __future__ import annotations
from dataclasses import asdict, dataclass

BRANDS = ("personal", "zomorod", "mojplaywin")
RESTRICTED_HANDLES = ("dr.mojtaba.rozegar",)
MEDIA_HOSTS = frozenset({"mojplaywin.com", "www.mojplaywin.com",
                         "zomorodmelal.ir", "www.zomorodmelal.ir"})

@dataclass(frozen=True)
class Platform:
    key: str
    label: str
    category: str
    capability: str
    auth: str
    docs: str
    constraint: str = ""
    """capability: text, image, video, template, research_draft, read_only, manual, dev_release."""
    @property
    def sendable(self):
        return self.capability in {"text", "image", "video", "template", "research_draft", "dev_release"}

_LIST = [
    Platform("telegram", "Telegram", "social", "text", "bot", "https://core.telegram.org/bots/api#sendmessage", "Bot must administer the channel."),
    Platform("discord", "Discord", "social", "text", "bot", "https://discord.com/developers/docs/resources/message#create-message", "Bot needs message permissions."),
    Platform("bluesky", "Bluesky", "social", "text", "oauth", "https://docs.bsky.app/docs/api/com-atproto-repo-create-record", "OAuth session and repo DID required."),
    Platform("mastodon", "Mastodon", "social", "text", "oauth", "https://docs.joinmastodon.org/methods/statuses/", "Server hostname must be separately approved."),
    Platform("x", "X", "social", "text", "oauth", "https://docs.x.com/x-api/posts/create-post", "Write-capable user OAuth; API plan may be paid."),
    Platform("linkedin", "LinkedIn", "professional", "text", "oauth", "https://learn.microsoft.com/en-us/linkedin/marketing/community-management/shares/posts-api", "Person/organization scopes and application review."),
    Platform("facebook_pages", "Facebook Pages", "social", "text", "oauth", "https://developers.facebook.com/docs/pages-api/posts/", "Page token and pages_manage_posts scope."),
    Platform("threads", "Threads", "social", "text", "oauth", "https://developers.facebook.com/docs/threads/posts/", "Two-stage publish, approved permissions."),
    Platform("reddit", "Reddit", "community", "text", "oauth", "https://www.reddit.com/dev/api/#POST_api_submit", "Subreddit rules and OAuth API access."),
    Platform("google_business_profile", "Google Business Profile", "business", "text", "oauth", "https://developers.google.com/my-business/reference/rest/v4/accounts.locations.localPosts/create", "Verified eligible business location; API approval."),
    Platform("instagram", "Instagram Professional", "social", "image", "oauth", "https://developers.facebook.com/docs/instagram-platform/content-publishing/", "Professional account; image container then publish."),
    Platform("pinterest", "Pinterest", "social", "image", "oauth", "https://developers.pinterest.com/docs/api/v5/pins-create/", "Approved pins:write and board."),
    Platform("youtube", "YouTube", "video", "video", "oauth", "https://developers.google.com/youtube/v3/docs/videos/insert", "Channel authorization; resumable local video upload."),
    Platform("tiktok", "TikTok", "video", "video", "oauth", "https://developers.tiktok.com/docs/en/content-posting-api-reference-direct-post", "Creator-info, explicit post consent, verified domain and app audit."),
    Platform("whatsapp_business", "WhatsApp Business", "messaging", "template", "oauth", "https://developers.facebook.com/docs/whatsapp/cloud-api/", "Only opted-in recipients; approved templates; no bulk spam."),
    Platform("zenodo", "Zenodo", "research", "research_draft", "token", "https://developers.zenodo.org/", "Create a draft only; DOI publication requires separate manual approval."),
    Platform("github_releases", "GitHub Releases", "developer", "dev_release", "oauth", "https://docs.github.com/en/rest/releases/releases#create-a-release", "Draft release only; owner-approved repositories."),
    Platform("orcid", "ORCID", "research", "read_only", "oauth", "https://info.orcid.org/documentation/api-tutorials/", "Public reads; writes require member integration."),
    Platform("google_scholar", "Google Scholar", "research", "manual", "website", "https://scholar.google.com/", "No supported public post publishing API."),
    Platform("researchgate", "ResearchGate", "research", "manual", "website", "https://www.researchgate.net/", "Do not automate posting without authorized API."),
    Platform("academia", "Academia.edu", "research", "manual", "website", "https://www.academia.edu/"),
    Platform("ssrn", "SSRN", "research", "manual", "website", "https://www.ssrn.com/"),
    Platform("huggingface", "Hugging Face", "developer", "manual", "website", "https://huggingface.co/docs/hub/"),
    Platform("medium", "Medium", "publishing", "manual", "website", "https://help.medium.com/", "New integration tokens generally unavailable."),
    Platform("substack", "Substack", "publishing", "manual", "website", "https://substack.com/", "No assumed general public write API."),
    Platform("quora", "Quora", "professional", "manual", "website", "https://www.quora.com/"),
    Platform("devto", "DEV Community", "developer", "manual", "website", "https://developers.forem.com/api/"),
    Platform("alibaba", "Alibaba.com", "business", "manual", "website", "https://www.alibaba.com/"),
    Platform("globalsources", "Global Sources", "business", "manual", "website", "https://www.globalsources.com/"),
    Platform("madeinchina", "Made-in-China", "business", "manual", "website", "https://www.made-in-china.com/"),
    Platform("europages", "Europages", "business", "manual", "website", "https://www.europages.com/"),
    Platform("kompass", "Kompass", "business", "manual", "website", "https://www.kompass.com/"),
    Platform("crunchbase", "Crunchbase", "business", "manual", "website", "https://www.crunchbase.com/"),
    Platform("trustpilot", "Trustpilot", "business", "manual", "website", "https://developers.trustpilot.com/", "API access differs by plan and product."),
    Platform("steam", "Steamworks", "commerce", "manual", "website", "https://partner.steamgames.com/doc/home"),
    Platform("itchio", "itch.io", "commerce", "manual", "website", "https://itch.io/docs/butler/", "Use native butler release pipeline, not a generic social-post API."),
    Platform("googleplay", "Google Play", "commerce", "manual", "website", "https://developers.google.com/android-publisher"),
    Platform("appstore", "Apple App Store", "commerce", "manual", "website", "https://developer.apple.com/documentation/appstoreconnectapi"),
    Platform("kdp", "Amazon KDP", "commerce", "manual", "website", "https://kdp.amazon.com/"),
    Platform("gumroad", "Gumroad", "commerce", "manual", "website", "https://gumroad.com/"),
    Platform("payhip", "Payhip", "commerce", "manual", "website", "https://payhip.com/"),
    Platform("udemy", "Udemy", "commerce", "manual", "website", "https://www.udemy.com/"),
    Platform("patreon", "Patreon", "commerce", "manual", "website", "https://docs.patreon.com/"),
    Platform("kofi", "Ko-fi", "commerce", "manual", "website", "https://ko-fi.com/"),
    Platform("producthunt", "Product Hunt", "marketing", "manual", "website", "https://www.producthunt.com/"),
    Platform("snapchat", "Snapchat", "social", "manual", "website", "https://developers.snap.com/"),
]
PLATFORMS = {x.key: x for x in _LIST}

def catalogue():
    return [asdict(p) | {"sendable": p.sendable} for p in _LIST]

def platform(key: str) -> Platform:
    try:
        return PLATFORMS[key]
    except (KeyError, TypeError):
        raise ValueError("platform not registered") from None
