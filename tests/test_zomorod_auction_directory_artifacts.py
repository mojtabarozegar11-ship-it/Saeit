"""Production regression checks for the published Zomorod auctions index and sitemap.

The site serves these exact UTF-8 artifacts on cPanel through a narrowly
scoped, fingerprint-verified route; none of these tests change live state.
"""
from html.parser import HTMLParser
from pathlib import Path
import json
import re
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[1] / "public" / "auctions"
NOTICES = (346, 347, 348, 349)
ORIGIN = "https://zomorodmelal.ir"


class LinkParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            self.links.append(dict(attrs).get("href", ""))


def test_directory_lists_all_four_published_notices_without_purchase_promises():
    text = (ROOT / "index.html").read_text(encoding="utf-8")
    parsed = LinkParser()
    parsed.feed(text)
    assert '<html lang="fa" dir="rtl">' in text
    assert '<link rel="canonical" href="https://zomorodmelal.ir/auctions/">' in text
    assert 'name="description"' in text
    assert "zomorodmelal@gmail.com" in text
    assert "۵ تا ۱۰ هر ماه" in text
    assert "بدون تعهد خرید یا پیش‌پرداخت" in text
    assert "هیچ پرداخت، وجه ثبت‌نام یا پیش‌پرداختی" in text
    assert "/static/site/company/company-logo.png" in text
    assert len(re.findall(r'class="notice-card"', text)) == 4
    for n in NOTICES:
        assert f"/auctions/{n}/" in parsed.links
    assert "/sitemap-auctions.xml" in parsed.links
    assert "هیچ مزایده‌ای برای نمایش" not in text


def test_directory_collection_schema_matches_public_notices():
    text = (ROOT / "index.html").read_text(encoding="utf-8")
    match = re.search(r'<script type="application/ld\+json">(.*?)</script>', text, re.S)
    assert match is not None
    payload = json.loads(match.group(1))
    assert payload["@type"] == "CollectionPage"
    assert payload["mainEntity"]["numberOfItems"] == 4
    actual = {item["url"] for item in payload["mainEntity"]["itemListElement"]}
    expected = {f"{ORIGIN}/auctions/{n}/" for n in NOTICES}
    assert actual == expected


def test_secondary_sitemap_contains_only_real_auction_urls():
    doc = ET.parse(ROOT / "sitemap.xml")
    ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    urls = [n.text for n in doc.findall(".//sm:loc", ns)]
    expected = {f"{ORIGIN}/auctions/{n}/" for n in NOTICES} | {f"{ORIGIN}/auctions/", f"{ORIGIN}/auctions/supplier-kit/"}
    assert set(urls) == expected
    assert len(urls) == len(expected)


def test_robot_policy_is_identical_except_for_one_sitemap_addition():
    content = (ROOT / "robots.txt").read_text(encoding="utf-8")
    assert content.splitlines() == [
        "User-agent: *",
        "Disallow: /admin/",
        "Disallow: /site-heritage/",
        "Disallow: /__zm_",
        "Disallow: /zm-agriculture-guides/",
        f"Sitemap: {ORIGIN}/sitemap.xml",
        f"Sitemap: {ORIGIN}/topics/sitemap.xml",
        f"Sitemap: {ORIGIN}/sitemap-auctions.xml",
    ]


def test_supplier_kit_links_legal_quotations_and_downloads():
    page = (ROOT / "supplier-kit" / "index.html").read_text(encoding="utf-8")
    assert '<html lang="fa" dir="rtl">' in page
    assert '<link rel="canonical" href="https://zomorodmelal.ir/auctions/supplier-kit/">' in page
    assert "غیرالزام‌آور" in page
    assert "zomorodmelal@gmail.com" in page
    index = (ROOT / "index.html").read_text(encoding="utf-8")
    assert 'href="/auctions/supplier-kit/"' in index
    for number in NOTICES:
        assert f'/auctions/{number}/' in page
        assert f'/auctions/supplier-kit/templates/rfq-{number}.csv' in page
        raw = (ROOT / "templates" / f"rfq-{number}.csv").read_bytes()
        assert raw[:3] == b"\xef\xbb\xbf"  # UTF-8 BOM for Excel Persian compatibility
        decoded = raw[3:].decode("utf-8-sig")
        assert "پاسخ تأمین‌کننده" in decoded
        assert "شماره فراخوان" in decoded
        assert "تعهد" in decoded
        assert decoded.count("\r\n") >= 30
    assert "حداقل حجم عمده" in (ROOT / "templates" / "rfq-349.csv").read_text(encoding="utf-8-sig")
    assert "رفاه جانوری" in (ROOT / "templates" / "rfq-346.csv").read_text(encoding="utf-8-sig")
