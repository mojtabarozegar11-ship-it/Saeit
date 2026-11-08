"""Bounded, attribution-first reader for an official agricultural news feed.

This module deliberately has no Django dependency. It never publishes content.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import urlsplit, urlunsplit
from urllib.request import Request, urlopen
from xml.etree import ElementTree


FEED_URL = "https://www.nass.usda.gov/rss/news.xml"
FEED_PUBLISHER = "USDA National Agricultural Statistics Service"
ALLOWED_HOSTS = frozenset({"nass.usda.gov", "www.nass.usda.gov", "data.nass.usda.gov"})
MAX_FEED_BYTES = 1_500_000
USER_AGENT = "ZomorodMelalNews/1.0 (+https://zomorodmelal.ir/contact/)"


@dataclass(frozen=True)
class OfficialNewsItem:
    title: str
    url: str
    published_at: datetime


def _canonical_official_url(candidate: str) -> str | None:
    """Keep only source links under the exact official USDA NASS hosts."""
    try:
        parts = urlsplit((candidate or "").strip())
        port = parts.port
    except ValueError:
        return None
    if parts.scheme.lower() not in {"https", "http"}:
        return None
    if parts.hostname not in ALLOWED_HOSTS or parts.username or parts.password or port:
        return None
    if not parts.path:
        return None
    return urlunsplit(("https", parts.hostname, parts.path, parts.query, ""))


def parse_official_rss(payload: bytes, *, now: datetime | None = None,
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
        link = _canonical_official_url(item.findtext("link") or "")
        raw_date = (item.findtext("pubDate") or "").strip()
        if not title or not link or not raw_date or link in seen:
            continue
        try:
            published = parsedate_to_datetime(raw_date)
            if published.tzinfo is None:
                published = published.replace(tzinfo=timezone.utc)
            published = published.astimezone(timezone.utc)
        except (TypeError, ValueError, IndexError):
            continue
        if not now - timedelta(days=lookback_days) <= published <= now + timedelta(hours=2):
            continue
        seen.add(link)
        results.append(OfficialNewsItem(title=title[:500], url=link, published_at=published))
    return sorted(results, key=lambda row: row.published_at, reverse=True)[:max_items]


def fetch_official_news(*, lookback_days: int = 21,
                        max_items: int = 15) -> list[OfficialNewsItem]:
    request = Request(FEED_URL, headers={"User-Agent": USER_AGENT, "Accept": "application/rss+xml, application/xml, text/xml"})
    with urlopen(request, timeout=18) as response:
        if urlsplit(response.url).hostname not in ALLOWED_HOSTS:
            raise ValueError("RSS redirected outside the official domain")
        payload = response.read(MAX_FEED_BYTES + 1)
    return parse_official_rss(payload, lookback_days=lookback_days, max_items=max_items)
