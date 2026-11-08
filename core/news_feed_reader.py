"""Bounded, attribution-first reader for official agricultural news feeds.

This module deliberately has no Django dependency. It never publishes content.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
import hashlib
from urllib.parse import urljoin, urlsplit, urlunsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener
from xml.etree import ElementTree


MAX_FEED_BYTES = 1_500_000
USER_AGENT = "ZomorodMelalNews/1.0 (+https://zomorodmelal.ir/contact/)"


@dataclass(frozen=True)
class OfficialFeed:
    url: str
    publisher: str
    allowed_hosts: frozenset[str]


OFFICIAL_FEEDS = (
    OfficialFeed(
        url="https://www.nass.usda.gov/rss/news.xml",
        publisher="USDA National Agricultural Statistics Service",
        allowed_hosts=frozenset({"nass.usda.gov", "www.nass.usda.gov", "data.nass.usda.gov"}),
    ),
    OfficialFeed(
        url="https://www.fao.org/feeds/fao-newsroom-rss",
        publisher="FAO — Food and Agriculture Organization of the United Nations",
        allowed_hosts=frozenset({"fao.org", "www.fao.org"}),
    ),
)


@dataclass(frozen=True)
class OfficialNewsItem:
    title: str
    url: str
    published_at: datetime
    publisher: str
    feed_url: str


@dataclass(frozen=True)
class NewsFetchResult:
    items: list[OfficialNewsItem]
    feeds_ok: int
    feed_errors: tuple[str, ...]


class _OfficialRedirectsOnly(HTTPRedirectHandler):
    """Reject unapproved feed redirects *before* sending a network request."""

    def __init__(self, allowed_hosts: frozenset[str]):
        self.allowed_hosts = allowed_hosts

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        target = urlsplit(urljoin(req.full_url, newurl))
        if (target.scheme != "https" or target.hostname not in self.allowed_hosts
                or target.username or target.password or target.port is not None):
            raise ValueError("Official RSS redirect left the approved HTTPS publisher hosts")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def editorial_identity(item: OfficialNewsItem) -> tuple[str, str]:
    """Stable per-publisher draft keys, preserving existing USDA draft IDs."""
    digest = hashlib.sha256(item.url.encode("utf-8")).hexdigest()
    if item.feed_url == OFFICIAL_FEEDS[0].url:
        # Previous versions used this exact key; retain it for idempotency.
        return f"official-usda-news:{digest}", f"usda-news-{digest[:24]}"
    if item.feed_url == OFFICIAL_FEEDS[1].url:
        return f"official-fao-news:{digest}", f"fao-news-{digest[:24]}"
    raise ValueError("News item has no approved official feed identity")


def _canonical_official_url(candidate: str, allowed_hosts: frozenset[str]) -> str | None:
    """Keep source links only under the exact publisher-approved hosts."""
    try:
        parts = urlsplit((candidate or "").strip())
        port = parts.port
    except ValueError:
        return None
    if parts.scheme.lower() not in {"https", "http"}:
        return None
    if parts.hostname not in allowed_hosts or parts.username or parts.password or port is not None:
        return None
    if not parts.path:
        return None
    return urlunsplit(("https", parts.hostname, parts.path, parts.query, ""))


def parse_official_rss(payload: bytes, *, feed: OfficialFeed = OFFICIAL_FEEDS[0],
                       now: datetime | None = None,
                       lookback_days: int = 21, max_items: int = 15) -> list[OfficialNewsItem]:
    """Parse official RSS 2.0, rejecting stale, duplicate or untrusted items."""
    if len(payload) > MAX_FEED_BYTES:
        raise ValueError("RSS payload exceeds safe size")
    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    if not 1 <= lookback_days <= 90 or not 1 <= max_items <= 50:
        raise ValueError("Invalid RSS bounds")
    root = ElementTree.fromstring(payload)
    if root.tag.lower() != "rss":
        raise ValueError("Expected RSS 2.0 root")
    channel = root.find("channel")
    if channel is None:
        raise ValueError("Missing RSS channel")
    results: list[OfficialNewsItem] = []
    seen: set[str] = set()
    for item in channel.findall("item"):
        title = " ".join((item.findtext("title") or "").split())
        link = _canonical_official_url(item.findtext("link") or "", feed.allowed_hosts)
        raw_date = (item.findtext("pubDate") or item.findtext(
            "{http://purl.org/dc/elements/1.1/}date") or "").strip()
        if not title or not link or not raw_date or link in seen:
            continue
        try:
            try:
                published = parsedate_to_datetime(raw_date)
            except (TypeError, ValueError, IndexError):
                published = datetime.fromisoformat(raw_date.replace("Z", "+00:00"))
            if published.tzinfo is None:
                published = published.replace(tzinfo=timezone.utc)
            published = published.astimezone(timezone.utc)
        except (TypeError, ValueError, IndexError):
            continue
        if not now - timedelta(days=lookback_days) <= published <= now + timedelta(hours=2):
            continue
        seen.add(link)
        results.append(OfficialNewsItem(
            title=title[:500], url=link, published_at=published,
            publisher=feed.publisher, feed_url=feed.url,
        ))
    return sorted(results, key=lambda row: row.published_at, reverse=True)[:max_items]


def fetch_official_news(*, lookback_days: int = 21,
                        max_items: int = 15) -> NewsFetchResult:
    """Use all verified sources; a single failed feed does not erase the other."""
    if not 1 <= lookback_days <= 90 or not 1 <= max_items <= 50:
        raise ValueError("Invalid RSS bounds")
    items: list[OfficialNewsItem] = []
    errors: list[str] = []
    feeds_ok = 0
    for feed in OFFICIAL_FEEDS:
        try:
            request = Request(feed.url, headers={
                "User-Agent": USER_AGENT,
                "Accept": "application/rss+xml, application/xml, text/xml",
            })
            with build_opener(_OfficialRedirectsOnly(feed.allowed_hosts)).open(request, timeout=18) as response:
                if urlsplit(response.url).hostname not in feed.allowed_hosts:
                    raise ValueError("RSS redirected outside the official domain")
                payload = response.read(MAX_FEED_BYTES + 1)
            items.extend(parse_official_rss(payload, feed=feed,
                                            lookback_days=lookback_days,
                                            max_items=max_items))
            feeds_ok += 1
        except Exception as exc:
            errors.append(f"{feed.publisher}: {type(exc).__name__}")
    if not feeds_ok:
        raise RuntimeError("All official news feeds unavailable: " + "; ".join(errors))
    items.sort(key=lambda item: item.published_at, reverse=True)
    return NewsFetchResult(items=items[:max_items], feeds_ok=feeds_ok,
                           feed_errors=tuple(errors))
