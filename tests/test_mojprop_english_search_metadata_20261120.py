"""Validate search and sharing metadata without accessing customer data."""
import json
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "templates" / "moj-prop"
PAGES = ("", "rules/", "signals/", "payment/", "contact/")


class HeadParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.meta = {}
        self.canonical = []
        self.schemas = []
        self.titles = []
        self.mode = None
        self.buffer = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "meta":
            key = attrs.get("name") or attrs.get("property")
            if key:
                self.meta.setdefault(key, []).append(attrs.get("content", ""))
        if tag == "link" and attrs.get("rel") == "canonical":
            self.canonical.append(attrs.get("href"))
        if tag == "title" or (tag == "script" and attrs.get("type") == "application/ld+json"):
            self.mode = tag
            self.buffer = []

    def handle_data(self, data):
        if self.mode:
            self.buffer.append(data)

    def handle_endtag(self, tag):
        if self.mode == tag:
            value = "".join(self.buffer).strip()
            if tag == "title":
                self.titles.append(value)
            else:
                self.schemas.append(json.loads(value))
            self.mode = None


def test_public_search_and_share_metadata():
    titles, descriptions = set(), set()
    for slug in PAGES:
        parser = HeadParser()
        page = (ROOT / slug / "index.html").read_text(encoding="utf-8")
        parser.feed(page.split("</head>", 1)[0])
        url = "https://mojplaywin.com/moj-prop/" + slug
        assert parser.canonical == [url]
        assert len(parser.titles) == 1
        title = parser.titles[0]
        assert 20 <= len(title) <= 75
        assert len(parser.meta["description"]) == 1
        desc = parser.meta["description"][0]
        assert 80 <= len(desc) <= 200
        assert title not in titles and desc not in descriptions
        titles.add(title)
        descriptions.add(desc)
        for key in ("og:title", "twitter:title"):
            assert parser.meta[key] == [title]
        for key in ("og:description", "twitter:description"):
            assert parser.meta[key] == [desc]
        assert parser.meta["og:url"] == [url]
        assert parser.meta["robots"] == ["index,follow,max-image-preview:large"]
        assert parser.meta["twitter:card"] == ["summary"]
        schemas = [s for s in parser.schemas if s.get("@type") in ("WebPage", "ContactPage")]
        assert len(schemas) == 1
        assert schemas[0]["url"] == url
        assert schemas[0]["name"] == title
        assert schemas[0]["description"] == desc
        assert schemas[0]["inLanguage"] == "en"
        assert all(s.get("@type") not in ("Product", "Offer", "AggregateRating") for s in parser.schemas)
