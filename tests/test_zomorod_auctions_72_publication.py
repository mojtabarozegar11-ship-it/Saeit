"""Concrete immutable 72 public procurement pages 350..421, preserving existing 346..349."""
from pathlib import Path
import json
import re
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
DATA = json.loads((ROOT / "content/auctions-72/procurement-notices.json").read_text(encoding="utf-8"))
PUBLIC = ROOT / "public" / "auctions"


def test_registry_counts_and_ranges():
    notices = DATA["notices"]
    assert len(notices) == 72
    assert [n["proposed_public_number"] for n in notices if n["kind"] == "supply"] == list(range(350, 386))
    assert [n["proposed_public_number"] for n in notices if n["kind"] == "equipment"] == list(range(386, 422))
    assert DATA["proposed_numbering"]["highest_verified_public_number"] == 349


def test_every_public_page_is_distinct_and_has_applicable_content():
    notices = DATA["notices"]
    titles = set()
    for notice in notices:
        n = notice["proposed_public_number"]
        html = (PUBLIC / str(n) / "index.html").read_text(encoding="utf-8")
        assert f"zm-auctions-72-v1 official-{n}" in html
        assert f"/auctions/{n}/" in html
        assert f"شماره رسمی آگهی {n}" in html
        assert notice["title"] in html
        assert "بدون" in html and "ثابت" in html
        assert "zomorodmelal@gmail.com" in html
        assert all(s in html for s in ("canonical", "og:title", "application/ld+json"))
        assert "ماهیت درخواست و وضعیت مالی" in html
        assert "<li>" in html
        assert "<h1>" in html
        assert html.count("<h1>") == 1
        assert notice["title"] not in titles
        titles.add(notice["title"])


def test_index_links_and_both_sitemaps_preserve_all_previous_pages():
    index = (PUBLIC / "index.html").read_text(encoding="utf-8")
    assert "zm-auctions-72-index-v1" in index
    for n in range(346, 422):
        assert f'href="/auctions/{n}/"' in index
    assert 'href="/auctions/supplier-kit/"' in index
    for rel in ("public/auctions/sitemap.xml", "public/sitemap-auctions.xml"):
        doc = ET.parse(ROOT / rel)
        ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
        urls = [u.text for u in doc.findall(".//sm:loc", ns)]
        assert len(urls) == 78
        assert len(set(urls)) == 78
        for n in range(346, 422):
            assert f"https://zomorodmelal.ir/auctions/{n}/" in urls


def test_no_fake_dates_or_commitment_metadata():
    for item in DATA["notices"]:
        assert "deadline" not in item and "published_at" not in item
        assert "price" not in item
        assert "contact_path" in item
    for n in range(350, 422):
        html = (PUBLIC / str(n) / "index.html").read_text(encoding="utf-8")
        assert 'datePublished' not in html and 'dateModified' not in html
        assert 'پرداخت' in html and 'قرارداد' in html
