#!/usr/bin/env python3
"""Astra independent research radar: public headlines -> private research hypotheses.

Research only. This is NOT a buyer-interview, price, product-quality, build,
publication, payment, or market-demand verification service. No factory imports.
Only fixed USDA NASS HTTPS RSS feeds and its newsroom are read; tests use offline bytes.
No API keys, database connections, production writes, or site changes.
"""
import argparse
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
import hashlib
import json
import os
from pathlib import Path
import re
import ssl
from urllib.parse import urljoin, urlsplit
from urllib.request import (
    HTTPSHandler, HTTPRedirectHandler, ProxyHandler, Request, build_opener
)
import xml.etree.ElementTree as ET

FEEDS = {
    "nass_news": "https://www.nass.usda.gov/rss/news.xml",
    "nass_reports": "https://www.nass.usda.gov/rss/reports.xml",
}
HTML_SOURCES = {"nass_newsroom": "https://www.nass.usda.gov/Newsroom/"}
ARTICLE_HOSTS = frozenset((
    "www.nass.usda.gov", "nass.usda.gov", "data.nass.usda.gov"
))
TOPICS = {
    "water_land": ("irrigation", "drought", "water", "aquifer", "moisture"),
    "agri_procurement": ("fertilizer", "seed", "input costs", "machinery", "supply"),
    "agri_markets": ("price", "inventory", "stock", "acreage", "exports", "production"),
    "agri_data_education": ("statistics", "survey", "research", "report", "data"),
}
MAX_FEED_BYTES = 512_000
MAX_ITEMS_PER_FEED = 100
MAX_AGE_DAYS = 120
MAX_ARTICLES_PER_TOPIC = 5


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, message, headers, newurl):
        raise ValueError("redirect forbidden for fixed-source research feed")


def fetch_feed(name):
    """Read exact vetted public sources; block redirects and environment proxies."""
    if name not in FEEDS and name not in HTML_SOURCES:
        raise ValueError("unregistered feed")
    opener = build_opener(ProxyHandler({}), HTTPSHandler(context=ssl.create_default_context()), NoRedirect())
    request = Request((FEEDS | HTML_SOURCES)[name], headers={"User-Agent": "AstraResearchRadar/1.0 (public metadata research)",
                                            "Accept": "text/html" if name in HTML_SOURCES else "application/rss+xml, application/xml, text/xml"})
    with opener.open(request, timeout=12) as response:
        if response.status != 200:
            raise ValueError("feed not available")
        content_type = response.headers.get("Content-Type", "").split(";")[0].strip().lower()
        allowed_media = ("text/html",) if name in HTML_SOURCES else ("application/rss+xml", "application/xml", "text/xml", "application/atom+xml")
        if content_type not in allowed_media:
            raise ValueError("source returned unexpected media")
        data = response.read(MAX_FEED_BYTES + 1)
    if len(data) > MAX_FEED_BYTES:
        raise ValueError("feed too large")
    return data


def _article_url(value):
    if not isinstance(value, str) or len(value) > 1500:
        return False
    try:
        url = urlsplit(value)
        return (url.scheme == "https" and url.hostname in ARTICLE_HOSTS and
                url.username is None and url.password is None and
                url.port in (None, 443) and not url.fragment)
    except ValueError:
        return False


def _date(value):
    if not value:
        return None
    try:
        if re.fullmatch(r"[0-9]{2}/[0-9]{2}/[0-9]{2}", value):
            result = datetime.strptime(value, "%m/%d/%y").replace(tzinfo=timezone.utc)
        elif re.match(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}[Tt ]", value):
            result = datetime.fromisoformat(value.replace("Z", "+00:00"))
        else:
            result = parsedate_to_datetime(value)
        return result.astimezone(timezone.utc) if result.tzinfo else None
    except (TypeError, ValueError, OverflowError):
        return None


class NewsroomHTMLParser(HTMLParser):
    """Associate date and link only when adjacent in a fixed first-party page."""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.before = ""
        self.active = None
        self.records = []

    def handle_starttag(self, tag, attrs):
        if tag.lower() == "a" and self.active is None:
            attr = dict(attrs)
            self.active = (attr.get("href"), self.before[-120:], [])

    def handle_data(self, text):
        if self.active is None:
            self.before = (self.before + " " + text)[-240:]
        else:
            self.active[2].append(text)

    def handle_endtag(self, tag):
        if tag.lower() != "a" or self.active is None:
            return
        href, preceding, chunks = self.active
        self.active = None
        title = " ".join(" ".join(chunks).split())
        matches = list(re.finditer(r"(?<![0-9])[0-9]{2}/[0-9]{2}/[0-9]{2}(?![0-9])", preceding))
        # Unambiguous date directly before the headline link, not one from a
        # distant sidebar or previous news entry.
        if not matches or len(preceding) - matches[-1].end() > 70:
            return
        if not isinstance(href, str) or href.startswith("//"):
            return
        self.records.append((title, urljoin(HTML_SOURCES["nass_newsroom"], href),
                             matches[-1].group()))


def parse_newsroom_html(source, raw, now):
    if source not in HTML_SOURCES or not isinstance(raw, bytes) or len(raw) > MAX_FEED_BYTES:
        raise ValueError("untrusted fixed HTML input")
    parser = NewsroomHTMLParser()
    parser.feed(raw.decode("utf-8", errors="replace"))
    parser.close()
    results = []
    for title, url, published in parser.records[:MAX_ITEMS_PER_FEED]:
        when = _date(published)
        if (not 8 <= len(title) <= 250 or "<" in title or ">" in title
                or not _article_url(url) or when is None
                or not now - timedelta(days=MAX_AGE_DAYS) <= when <= now):
            continue
        results.append({
            "title": title,
            "url": url,
            "published_at": when.isoformat(),
            "source": source,
            "reference_sha256": hashlib.sha256((url + "\n" + title).encode("utf-8")).hexdigest(),
        })
    return results


def parse_feed(source, raw, now):
    """Parse RSS/Atom metadata only; never copy full stories or assume truth."""
    if source in HTML_SOURCES:
        return parse_newsroom_html(source, raw, now)
    if source not in FEEDS or not isinstance(raw, bytes) or len(raw) > MAX_FEED_BYTES:
        raise ValueError("untrusted feed input")
    if b"<!DOCTYPE" in raw.upper() or b"<!ENTITY" in raw.upper():
        raise ValueError("XML entity declarations forbidden")
    try:
        root = ET.fromstring(raw)
    except ET.ParseError as exc:
        raise ValueError("invalid RSS/Atom XML") from exc
    if root.tag not in ("rss", "{http://www.w3.org/2005/Atom}feed"):
        raise ValueError("unsupported feed format")
    if root.tag == "rss":
        entries = root.findall("./channel/item")
        def get(entry):
            return (entry.findtext("title"), entry.findtext("link"),
                    entry.findtext("pubDate"))
    else:
        atom = "{http://www.w3.org/2005/Atom}"
        entries = root.findall(atom + "entry")
        def get(entry):
            links = [x.get("href") for x in entry.findall(atom + "link")
                     if x.get("rel", "alternate") == "alternate"]
            return (entry.findtext(atom + "title"),
                    links[0] if links else None,
                    entry.findtext(atom + "updated") or entry.findtext(atom + "published"))
    records = []
    for entry in entries[:MAX_ITEMS_PER_FEED]:
        title, url, published = get(entry)
        when = _date(published)
        if not (isinstance(title, str) and isinstance(url, str) and
                8 <= len(title.strip()) <= 250 and _article_url(url) and when):
            continue
        if not now - timedelta(days=MAX_AGE_DAYS) <= when <= now:
            continue
        # Remove control chars and compact whitespace; no HTML content reuse.
        title = " ".join(re.sub(r"[\x00-\x1f\x7f]", " ", title).split())
        if "<" in title or ">" in title:
            continue
        records.append({
            "title": title,
            "url": url,
            "published_at": when.isoformat(),
            "source": source,
            "reference_sha256": hashlib.sha256((url + "\n" + title).encode("utf-8")).hexdigest(),
        })
    return records


def research_report(fetched, now):
    if not isinstance(now, datetime) or now.tzinfo is None:
        raise ValueError("timezone-aware clock required")
    now = now.astimezone(timezone.utc)
    if not isinstance(fetched, dict) or any(name not in FEEDS and name not in HTML_SOURCES for name in fetched):
        raise ValueError("unknown feed source")
    references = {}
    failures = {}
    for name, raw in sorted(fetched.items()):
        try:
            for item in parse_feed(name, raw, now):
                references.setdefault(item["reference_sha256"], item)
        except (ValueError, TypeError) as exc:
            failures[name] = str(exc)
    topics = []
    for key, phrases in sorted(TOPICS.items()):
        matched = [item for item in references.values()
                   if any(re.search(r"(?<![a-z])" + re.escape(phrase) + r"(?![a-z])",
                                    item["title"].lower()) for phrase in phrases)]
        matched.sort(key=lambda x: (x["published_at"], x["reference_sha256"]), reverse=True)
        if not matched:
            continue
        selected = matched[:MAX_ARTICLES_PER_TOPIC]
        age = (now - datetime.fromisoformat(selected[0]["published_at"])).days
        # Trend/research triage only. NEVER a quality, conversion or margin score.
        priority = min(70, 20 + 8 * len(selected) + max(0, 25 - age))
        topics.append({
            "opportunity_key": key,
            "research_question": {
                "water_land": "Could a transparent water-and-land scenario workbench help farm planning?",
                "agri_procurement": "Could audited input-quote comparisons reduce procurement errors?",
                "agri_markets": "Could a source-linked farm-market data explainer improve decisions?",
                "agri_data_education": "Could interactive agriculture statistics lessons improve data literacy?",
            }[key],
            "topic_priority_only": priority,
            "preliminary_references": selected,
            "independent_publishers_confirmed": 1,  # All fixed feeds share one USDA agency.
            "status": "RESEARCH_REQUIRED",
            "buyer_willingness_to_pay_verified": False,
            "competitor_advantage_verified": False,
            "financial_margin_verified": False,
            "commercial_quality_score": None,
            "product_build_authorized": False,
            "store_publication_authorized": False,
            "payment_authorized": False,
            "blockers": [
                "DIRECT_BUYER_RESEARCH_MISSING",
                "INDEPENDENT_COMPETITOR_REVIEW_MISSING",
                "DOMAIN_AND_RIGHTS_REVIEW_MISSING",
                "NOT_A_THREE_PUBLISHER_EVIDENCE_DOSSIER",
            ],
        })
    topics.sort(key=lambda x: (-x["topic_priority_only"], x["opportunity_key"]))
    return {
        "schema_version": 1,
        "mode": "private_public_signal_research_only",
        "as_of_utc": now.isoformat(),
        "feed_names": sorted(fetched),
        "feed_failures": failures,
        "distinct_headline_references": len(references),
        "candidate_hypotheses": topics,
        "commercial_products_built": 0,
        "real_customers_contacted": 0,
        "factory_mutations": 0,
        "publications": 0,
        "payments": 0,
    }


def write_private_new(path, report):
    output = Path(path).expanduser()
    if output.is_symlink() or not output.parent.is_dir() or output.parent.is_symlink():
        raise ValueError("unsafe output destination")
    encoded = (json.dumps(report, sort_keys=True, indent=2, ensure_ascii=False) + "\n").encode()
    if len(encoded) > 2_000_000:
        raise ValueError("report too large")
    fd = os.open(str(output), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
    except BaseException:
        output.unlink(missing_ok=True)
        raise


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--fetch", action="store_true", help="Fetch fixed USDA official public RSS")
    mode.add_argument("--fixture", help="Offline RSS XML fixture, no network")
    parser.add_argument("--source", choices=sorted(FEEDS | HTML_SOURCES), default="nass_reports",
                        help="Feed identity for offline fixture")
    parser.add_argument("--output", required=True, help="New local private JSON report (no overwrite)")
    parser.add_argument("--now-utc", help="ISO8601 clock override for reproducible offline test")
    args = parser.parse_args(argv)
    if args.fetch and args.now_utc:
        parser.error("--now-utc may only be used with offline fixtures")
    now = (_date(args.now_utc) if args.now_utc else datetime.now(timezone.utc))
    if now is None:
        raise ValueError("invalid now-utc")
    if args.fetch:
        feeds, errors = {}, {}
        for name in sorted(FEEDS | HTML_SOURCES):
            try:
                feeds[name] = fetch_feed(name)
            except (OSError, ValueError) as exc:
                errors[name] = type(exc).__name__
        report = research_report(feeds, now)
        report["feed_failures"].update(errors)
    else:
        fixture = Path(args.fixture)
        if fixture.is_symlink() or not fixture.is_file() or fixture.stat().st_size > MAX_FEED_BYTES:
            raise ValueError("unsafe fixture")
        report = research_report({args.source: fixture.read_bytes()}, now)
    write_private_new(args.output, report)
    print("ASTRA_RADAR_STATUS=RESEARCH_ONLY")
    print("ASTRA_RADAR_TOPIC_COUNT=" + str(len(report["candidate_hypotheses"])))
    print("ASTRA_RADAR_FEED_FAILURES=" + str(len(report["feed_failures"])))
    print("ASTRA_RADAR_FACTORY_MUTATIONS=0")


if __name__ == "__main__":
    main()
