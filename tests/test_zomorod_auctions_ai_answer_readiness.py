"""Human-visible, verifiable answer snippets for RFQs; no fake AI ranking claims."""
import html
import json
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parents[1]
PAGE_ROOT=ROOT/"public/auctions"
RECORDS=json.loads((ROOT/"content/auctions-72/procurement-notices.json").read_text(encoding="utf-8"))
BASELINE=json.loads((ROOT/"content/auctions-aeo-20261117/baseline.json").read_text(encoding="utf-8"))
GROUPS=json.loads((ROOT/"content/auctions-aeo-20261117/bilingual-groups.json").read_text(encoding="utf-8"))
CANON="https://zomorodmelal.ir"

def fact_section(source, number):
    pattern=rf'<!-- zm-auctions-aeo-20261117-{number} -->\s*(<section[\s\S]*?</section>)'
    found=re.findall(pattern,source)
    assert len(found)==1, (number,len(found))
    return found[0]

def test_all_72_machine_and_human_readable_answers_are_true_and_citable():
    ids=set()
    translations={}
    assert len(GROUPS["pairs"])==36
    for group in GROUPS["pairs"]:
        translations[group["product_serial"]]=group["english_group"]
        translations[group["equipment_serial"]]=group["english_group"]
    assert len(translations)==72
    for record in RECORDS["notices"]:
        n=record["proposed_public_number"]
        assert n not in ids
        ids.add(n)
        markup=(PAGE_ROOT/str(n)/"index.html").read_text(encoding="utf-8")
        answers=fact_section(markup,n)
        visible=html.unescape(re.sub(r"<[^>]+>"," ",answers))
        assert f'id="official-facts-{n}"' in answers
        assert f'id="official-facts-heading-{n}"' in answers
        assert answers.count("<dt>")==6 and answers.count("</dd>")==6
        assert record["group"] in visible, n
        assert record["special_checks"] in visible, n
        assert all(x in visible for x in record["scope"][:3]), n
        assert "شرکت کشت و صنعت زمرد ملل" in visible
        assert "مهلت پایان ثابت تعیین نشده است" in visible
        assert "تضمین بازبودن دائمی" in visible
        assert "هیچ ارسال یا ثبت خودکاری" in visible
        assert "این سند دعوت به ارائه پیشنهاد" in visible
        assert f"/auctions/{n}/" in answers
        assert 'lang="en" dir="ltr"' in answers
        assert f"Official Zomorod Melal procurement inquiry No. {n}" in answers
        assert "non-binding" in answers and "No fixed closing deadline" in answers
        english_topic=translations[n]
        assert english_topic in answers, (n, english_topic)
        assert len(english_topic)>=9
        assert answers.count(english_topic)==1
        assert f"zm-auctions-72-v1 official-{n}" in markup
        assert "zm-auctions-seo-20261117-v1" in markup
        assert f'id="rfq-offer-form-{n}"' in markup
        assert f'link rel="canonical" href="{CANON}/auctions/{n}/"' in markup
        assert '"@type":"BreadcrumbList"' in markup
        assert '"@type":"FAQPage"' not in markup
        assert "datePublished" not in markup
        assert 'noindex' not in markup
    assert ids==set(range(350,422))

def test_directory_has_citable_human_qa_without_legacy_notice_damage():
    text=(PAGE_ROOT/"index.html").read_text(encoding="utf-8")
    assert text.count("zm-auctions-aeo-20261117-index-v1")==1
    assert "راهنمای روشن و قابل‌استناد فراخوان‌های زمرد ملل" in text
    assert 'id="official-procurement-answers"' in text
    assert "روزهای ۵ تا ۱۰ هر ماه فقط در صورت اعلام رسمی قبلی" in text
    assert 'lang="en" dir="ltr"' in text
    assert "No fixed closing date is stated" in text
    assert "بدون مهلت پایان ثابت" in text
    assert "عدم" not in "محدوده"
    for n in range(346,422):
        assert f'href="/auctions/{n}/"' in text, n
    assert 'href="/auctions/supplier-kit/"' in text
    assert "zm-auctions-seo-20261117-index-v1" in text
    assert "zm-auctions-72-index-v1" in text
    assert f'{CANON}/auctions/' in text

def test_existing_search_crawler_access_policy_and_sitemap_unchanged_in_scope():
    robots=(PAGE_ROOT/"robots.txt").read_text(encoding="utf-8")
    assert "User-agent: *" in robots
    from urllib.robotparser import RobotFileParser
    rp=RobotFileParser()
    rp.parse(robots.splitlines())
    for bot in ("OAI-SearchBot","Googlebot","Claude-SearchBot","PerplexityBot","Bingbot"):
        assert rp.can_fetch(bot, "/auctions/350/"), bot
        assert rp.can_fetch(bot, "/auctions/421/"), bot
        assert not rp.can_fetch(bot, "/admin/"), bot
    for p in ("/admin/","/site-heritage/","/__zm_","/zm-agriculture-guides/"):
        assert "Disallow: "+p in robots
    assert "Disallow: /auctions/" not in robots
    assert "Sitemap: https://zomorodmelal.ir/sitemap-auctions.xml" in robots
    sitemap=(ROOT/"public/sitemap-auctions.xml").read_text(encoding="utf-8")
    for n in range(346,422):
        assert f"/auctions/{n}/" in sitemap
    assert sitemap.count("<lastmod>2026-11-17</lastmod>")==73

def test_immutable_preimage_for_only_73_reviewed_pages():
    expected={"public/auctions/index.html"}|{f"public/auctions/{n}/index.html" for n in range(350,422)}
    assert set(BASELINE["baseline_git_blob_sha1"])==expected
    assert len(expected)==73
    assert all(re.fullmatch(r"[0-9a-f]{40}",s) for s in BASELINE["baseline_git_blob_sha1"].values())
    assert BASELINE["source_main_sha"]=="a5a450e821b2698d02c3d80cb2d4de454cf159ea"
