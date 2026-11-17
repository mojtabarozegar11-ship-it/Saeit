"""Strict SEO regression gate for 72 real published non-binding procurement RFQs."""
import html
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "public" / "auctions"
CANON = "https://zomorodmelal.ir"
DATA = json.loads((ROOT / "content/auctions-72/procurement-notices.json").read_text(encoding="utf-8"))
BASELINE = json.loads((ROOT / "content/auctions-seo-20261117/baseline.json").read_text(encoding="utf-8"))


class MetaParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.meta = {}
        self.links = []
        self.headings = []
        self.refs = []
        self._h1 = False

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "meta":
            name = a.get("name") or a.get("property")
            if name:
                self.meta[name] = a.get("content")
        if tag == "link":
            self.links.append(a)
        if tag == "a":
            self.refs.append(a.get("href", ""))
        if tag == "h1":
            self._h1 = True

    def handle_endtag(self, tag):
        if tag == "h1":
            self._h1 = False

    def handle_data(self, data):
        if self._h1:
            self.headings.append(data)


def schema_blocks(markup):
    return [json.loads(x) for x in re.findall(
        r'<script type="application/ld\+json">([\s\S]*?)</script>',
        markup,
    )]


def test_seo_title_description_and_legal_notice_uniqueness_72():
    titles, descriptions = set(), set()
    seen = []
    for notice in DATA["notices"]:
        n = notice["proposed_public_number"]
        seen.append(n)
        page = (PUBLIC / str(n) / "index.html").read_text(encoding="utf-8")
        p = MetaParser()
        p.feed(page)
        title = html.unescape(re.search(r"<title>(.*?)</title>", page, re.S).group(1))
        description = p.meta.get("description")
        assert "zm-auctions-72-v1 official-" + str(n) in page
        assert "zm-auctions-seo-20261117-v1" in page
        assert notice["title"] in page and notice["special_checks"] in page
        assert all(part in html.unescape(page) for part in notice["scope"])
        assert "zomorodmelal@gmail.com" in page
        assert "مهلت پایان ثابت تعیین نشده است" in page
        assert "قرارداد" in page and "تعهد خرید" in page
        assert len(title) >= 30 and title.count(str(n)) == 1
        assert notice["group"] in title
        assert len(description or "") >= 80
        assert notice["group"] in description and str(n) in description
        assert p.meta["robots"] == "index,follow,max-image-preview:large"
        assert p.meta["og:title"] == title
        assert p.meta["og:description"] == description
        assert p.meta["og:locale"] == "fa_IR"
        assert p.meta["twitter:card"] == "summary"
        assert p.meta["og:site_name"] == "زمرد ملل"
        assert p.meta["og:image"].startswith(CANON + "/static/site/company/")
        assert p.meta["og:url"] == CANON + f"/auctions/{n}/"
        assert '<html lang="fa" dir="rtl">' in page
        assert len(p.headings) == 1
        assert [x.get("href") for x in p.links if x.get("rel") == "canonical"] == [CANON + f"/auctions/{n}/"]
        assert title not in titles and description not in descriptions
        titles.add(title)
        descriptions.add(description)
        assert "datePublished" not in page
        assert '"@type":"Product"' not in page
        assert '"@type":"FAQPage"' not in page
        assert "noindex" not in page
    assert sorted(seen) == list(range(350, 422))
    assert len(titles) == len(descriptions) == 72


def test_every_breadcrumb_graph_and_related_links_match_true_route():
    for notice in DATA["notices"]:
        n = notice["proposed_public_number"]
        s = (PUBLIC / str(n) / "index.html").read_text(encoding="utf-8")
        graphs = schema_blocks(s)
        assert len(graphs) == 1, n
        graph = graphs[0]
        assert graph["@context"] == "https://schema.org"
        items = graph["@graph"]
        by_type = {item["@type"]: item for item in items}
        assert set(by_type) == {"Organization", "WebPage", "BreadcrumbList"}
        page = by_type["WebPage"]
        crumb = by_type["BreadcrumbList"]
        assert page["url"] == CANON + f"/auctions/{n}/"
        assert page["inLanguage"] == "fa-IR"
        assert page["breadcrumb"]["@id"] == crumb["@id"]
        nodes = crumb["itemListElement"]
        assert [item["position"] for item in nodes] == [1, 2, 3]
        assert [item["item"] for item in nodes] == [
            CANON + "/", CANON + "/auctions/", CANON + f"/auctions/{n}/"
        ]
        p = MetaParser()
        p.feed(s)
        partner = n + (36 if notice["kind"] == "supply" else -36)
        assert f"/auctions/{partner}/" in p.refs
        assert "/auctions/" in p.refs
        for href in p.refs:
            if re.fullmatch(r"/auctions/[0-9]+/", href):
                num = int(href.strip("/").split("/")[1])
                assert 350 <= num <= 421, (n, num)
        assert "فراخوان‌های مرتبط" in s


def test_directory_seo_schema_navigation_and_canonical():
    source = (PUBLIC / "index.html").read_text(encoding="utf-8")
    p = MetaParser()
    p.feed(source)
    title = re.search(r"<title>(.*?)</title>", source).group(1)
    assert "۷۶ فراخوان" in title
    assert p.meta["og:title"] == title
    assert "۳۶ گروه" in p.meta["description"]
    assert "زمرد ملل" in p.meta["og:site_name"]
    assert p.meta["twitter:card"] == "summary"
    assert '#supplier-calls' in p.refs and '#equipment-calls' in p.refs
    assert 'id="supplier-calls"' in source and 'id="equipment-calls"' in source
    assert [x.get("href") for x in p.links if x.get("rel") == "canonical"] == [CANON + "/auctions/"]
    graph = schema_blocks(source)
    assert len(graph) == 2
    assert graph[0]["@type"] == "CollectionPage"
    assert graph[0]["mainEntity"]["numberOfItems"] == 76
    assert graph[1]["@type"] == "BreadcrumbList"
    for n in range(346, 422):
        assert f'href="/auctions/{n}/"' in source
    assert "/auctions/supplier-kit/" in source
    assert "۵ تا ۱۰ هر ماه" in source


def test_accurate_only_changed_sitemap_dates_and_robots_discovery():
    ns = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    expected_changed = {CANON + "/auctions/"} | {
        CANON + f"/auctions/{n}/" for n in range(350, 422)
    }
    for path in (ROOT / "public/sitemap-auctions.xml", PUBLIC / "sitemap.xml"):
        doc = ET.parse(path)
        urls = doc.findall(".//s:url", ns)
        assert len(urls) == 78
        seen = {}
        for url in urls:
            loc = url.findtext("s:loc", namespaces=ns)
            lm = url.findtext("s:lastmod", namespaces=ns)
            assert loc not in seen
            seen[loc] = lm
        assert len(seen) == 78
        assert {x for x, lastmod in seen.items() if lastmod} == expected_changed
        assert all(seen[x] == "2026-11-17" for x in expected_changed)
        assert seen[CANON + "/auctions/346/"] is None
        assert seen[CANON + "/auctions/supplier-kit/"] is None
    robots = (PUBLIC / "robots.txt").read_text(encoding="utf-8")
    assert "Sitemap: https://zomorodmelal.ir/sitemap-auctions.xml" in robots
    assert "Disallow: /auctions/" not in robots


def test_fingerprint_manifest_preserves_production_preimage_for_each_asset():
    baseline = BASELINE["baseline_git_blob_sha1"]
    expected = {f"public/auctions/{n}/index.html" for n in range(350, 422)}
    expected |= {"public/auctions/index.html", "public/sitemap-auctions.xml",
                 "public/auctions/sitemap.xml"}
    assert set(baseline) == expected
    assert all(re.fullmatch(r"[0-9a-f]{40}", sha) for sha in baseline.values())
    assert BASELINE["source_commit"] == "a7a7eaa0192a322db6ec009d56fa8c2bea549a4a"
