#!/usr/bin/env python3
"""Reversible, evidence-safe enrichment of the existing Zomorod Melal /about/ page.

This script edits only the deployed about/index.html file. It does not assert
laboratory accreditation, publish private documents, invent projects or alter
the existing visual system. GitHub Actions is used solely as an SSH bridge.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from pathlib import Path

TAG = "zm-about-research-evidence-20261023"
OWNER_BEFORE = "<p><strong>محقق، پژوهشگر و مدیرعامل شرکت کشت و صنعت زمرد ملل</strong></p>"
OWNER_AFTER = "<p><strong>مجتبی روزگار، محقق، پژوهشگر، مالک و مدیرعامل شرکت کشت و صنعت زمرد ملل</strong></p>"
YEAR_ANCHOR = '<a href="/company/">آشنایی با ساختار و چشم‌انداز شرکت ←</a>'
YEAR_NOTE = "<p>بر اساس اطلاعات اعلام‌شده مجموعه، آغاز فعالیت رسمی شرکت کشت و صنعت زمرد ملل ۲۵ آبان ۱۳۹۸ بوده است.</p>"
DISCLOSURE = '<div class="disclosure"><strong>شفافیت اطلاعات علمی و سازمانی:'
META_DESCRIPTION = "شرکت کشت و صنعت زمرد ملل، با مدیریت مجتبی روزگار، با سهم اعلام‌شده ۹۰ درصدی تحقیقات علمی، ژنتیک و اصلاح نژاد؛ معرفی محورهای پژوهشی و معیار انتشار دستاوردهای مستند."
REPLACEMENTS = (
    (OWNER_BEFORE, OWNER_AFTER),
    ("5.2 ـ تمرکز نزدیک به ۹۰ درصدی بر پژوهش", "5.2 ـ تمرکز ۹۰ درصدی بر پژوهش"),
    ("بر اساس اطلاعات اعلام‌شده شرکت، نزدیک به ۹۰ درصد فعالیت‌ها به تحقیقات علمی، ژنتیک و اصلاح نژاد اختصاص دارد.",
     "بر اساس اطلاعات اعلام‌شده شرکت، ۹۰ درصد فعالیت‌ها به تحقیقات علمی، ژنتیک و اصلاح نژاد اختصاص دارد و ۱۰ درصد باقی‌مانده مربوط به سایر زمینه‌های فعالیت شرکت است."),
    ("حدود ۲۳۰ واحد تخصصی و تمرکز نزدیک به ۹۰ درصدی بر پژوهش نیز اطلاعات اعلام‌شده مجموعه‌اند",
     "حدود ۲۳۰ واحد تخصصی و تمرکز ۹۰ درصدی بر پژوهش نیز اطلاعات اعلام‌شده مجموعه‌اند"),
)

EVIDENCE_BLOCK = """<details id="zm-about-research-evidence-20261023">
<summary>نقشه پژوهش و شفافیت طرح‌های علمی<small>محورهای تحقیق، شواهد لازم و وضعیت امکانات · ۳ موضوع</small></summary>
<div class="cards">
<article><h4>محورهای علمی و ژنتیکی</h4>
<p>بر مبنای مأموریت اعلام‌شده شرکت، محورهای قابل بررسی شامل ژنتیک مولکولی و ژنومیک، اصلاح نژاد گیاهان زراعی و باغی، دام، طیور و آبزیان، حفاظت منابع ژنتیکی، میکروبیولوژی و زیست‌فناوری، بیوانفورماتیک و هوش مصنوعی زیستی، علوم خاک و آب و تحقیقات فناوری مواد غذایی است. این فهرست بیانگر زمینه‌های پژوهش است؛ نه ادعای تکمیل همه طرح‌ها یا برخورداری از آزمایشگاه مستقل در تمام رشته‌ها.</p>
<p><a href="/agriculture/genetics/">مطالعه ژنتیک و اصلاح نژاد ←</a> · <a href="/research/">چارچوب پژوهش ←</a></p></article>
<article><h4>شناسنامه قابل راستی‌آزمایی هر پروژه</h4>
<p>برای معرفی هر پروژه واقعی، عنوان و شناسه، مسئله علمی، مسئول پژوهش، مرحله اجرا، روش و داده قابل انتشار، معیار کنترل کیفیت، محدودیت یافته‌ها و تاریخ آخرین بازبینی ثبت می‌شود. تنها نتایج دارای شواهد و مجوز انتشار مناسب به‌عنوان دستاورد معرفی خواهند شد. تا پیش از آن، موضوع پیشنهادی نباید به‌عنوان پروژه تکمیل‌شده، مقاله داوری‌شده یا محصول آماده عرضه معرفی شود.</p>
<p><a href="/research/">روش‌شناسی و اصول ارزیابی پژوهش ←</a></p></article>
<article><h4>امکانات پژوهشی و ارزیابی توانمندی‌ها</h4>
<p>فعالیت آزمایشگاهی و تحلیل ژنومی به متخصص، زیرساخت، نمونه‌برداری معتبر، کنترل کالیبراسیون، ایمنی، ثبت داده و مجوزهای لازم وابسته است. ظرفیت واقعی هر واحد تنها پس از ثبت شناسنامه تجهیزات، نیروی مسئول، وضعیت دسترسی و مستندات تأییدشده اعلام می‌شود. عنوان یک واحد پژوهشی در ساختار سازمانی به‌تنهایی گواه دارابودن تجهیزات یا تأییدیه تخصصی نیست.</p>
<p><a href="/research/directory/units/molecular-genetics/">معرفی حوزه ژنتیک مولکولی ←</a> · <a href="/contact/">ارتباط برای همکاری علمی ←</a></p></article>
</div></details>
"""
PAGE_SCHEMA = {
    "@context": "https://schema.org",
    "@type": "AboutPage",
    "@id": "https://zomorodmelal.ir/about/#aboutpage",
    "url": "https://zomorodmelal.ir/about/",
    "name": "درباره شرکت کشت و صنعت زمرد ملل | پژوهش علمی و ژنتیک",
    "description": META_DESCRIPTION,
    "inLanguage": "fa-IR",
    "isPartOf": {"@type": "WebSite", "url": "https://zomorodmelal.ir/"},
    "about": {"@id": "https://zomorodmelal.ir/#organization"},
    "breadcrumb": {
        "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "خانه", "item": "https://zomorodmelal.ir/"},
            {"@type": "ListItem", "position": 2, "name": "درباره ما", "item": "https://zomorodmelal.ir/about/"},
        ],
    },
}

def digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()

def rewrite(original: bytes) -> bytes:
    source = original.decode("utf-8")
    if TAG in source:
        raise AssertionError("Patch is already present; do not republish.")
    for required in (
        'id="zm-about-official-20261018"',
        'id="zm-about-comprehensive"',
        'id="restored-earlier-corporate-content"',
        'id="zm-owner-real-photo-style-20261018"',
        '<strong>۹۰٪</strong>',
        '۹۰ درصد فعالیت‌های آن به تحقیقات علمی',
    ):
        assert required in source, "Missing original site baseline: " + required[:50]
    for old, new in REPLACEMENTS:
        assert source.count(old) == 1, "Missing or repeated anchor: " + old[:65]
        source = source.replace(old, new, 1)
    assert source.count(YEAR_ANCHOR) == 1
    source = source.replace(YEAR_ANCHOR, YEAR_NOTE + "\n" + YEAR_ANCHOR, 1)
    assert source.count(DISCLOSURE) == 1
    source = source.replace(DISCLOSURE, EVIDENCE_BLOCK + "\n" + DISCLOSURE, 1)
    found = re.findall(r'<meta name="description" content="[^"]*">', source)
    assert len(found) == 1
    source = source.replace(found[0], '<meta name="description" content="' + META_DESCRIPTION + '">', 1)
    assert source.count("</head>") == 1
    schema = json.dumps(PAGE_SCHEMA, ensure_ascii=False, separators=(",", ":"))
    extras = ('<meta property="og:type" content="website">\n'
              '<meta property="og:locale" content="fa_IR">\n'
              '<meta property="og:title" content="درباره زمرد ملل | مرکز پژوهش علمی و ژنتیک">\n'
              '<meta property="og:description" content="' + META_DESCRIPTION + '">\n'
              '<meta property="og:url" content="https://zomorodmelal.ir/about/">\n'
              '<script type="application/ld+json" id="zm-about-science-schema-20261023">' + schema + '</script>\n')
    for name in ("og:type", "og:locale", "og:title", "og:description", "og:url"):
        assert ('property="' + name + '"') not in source, "Existing metadata should be preserved"
    source = source.replace("</head>", extras + "</head>", 1)
    result = source.encode("utf-8")
    assert result != original
    assert source.count('id="' + TAG + '"') == 1
    for _, new in REPLACEMENTS:
        assert source.count(new) == 1
    assert source.count(META_DESCRIPTION) == 3
    assert '<meta name="viewport" content="width=device-width,initial-scale=1">' in source
    assert 'id="zm-about-official-theme-20261018"' in source
    return result

def location() -> tuple[Path, Path]:
    root = Path.home() / "public_html"
    target = root / "about" / "index.html"
    assert root.is_dir() and not root.is_symlink()
    assert target.is_file() and not target.is_symlink()
    return root, target

def backup_path(raw: str, root: Path) -> Path:
    value = Path(raw)
    assert value.is_absolute() and not value.is_symlink()
    assert value.resolve().is_relative_to(Path.home().resolve())
    assert not value.resolve().is_relative_to(root.resolve())
    return value

def atomic_write(target: Path, content: bytes):
    temporary = target.with_name(".index.about-research-evidence-next")
    assert not temporary.exists() and not temporary.is_symlink()
    with temporary.open("xb") as fd:
        fd.write(content)
        fd.flush()
        os.fsync(fd.fileno())
    os.chmod(temporary, 0o644)
    os.replace(temporary, target)

def verify(raw: str):
    root, target = location()
    location_ = backup_path(raw, root)
    manifest = json.loads((location_ / "manifest.json").read_text(encoding="utf-8"))
    current = target.read_bytes()
    assert digest(current) == manifest["after"]
    assert current.count(('id="' + TAG + '"').encode("utf-8")) == 1
    assert b'<meta property="og:title"' in current
    assert 'تمرکز ۹۰ درصدی بر پژوهش'.encode("utf-8") in current
    print("ABOUT_SCIENCE_VERIFY=success", "SHA256=" + digest(current))

def publish(raw: str):
    root, target = location()
    archive = backup_path(raw, root)
    previous = target.read_bytes()
    updated = rewrite(previous)
    assert not archive.exists()
    archive.mkdir(parents=True, mode=0o700)
    (archive / "before.html").write_bytes(previous)
    manifest = {"before": digest(previous), "after": digest(updated), "path": "about/index.html"}
    (archive / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    try:
        atomic_write(target, updated)
        verify(raw)
    except BaseException:
        if digest(target.read_bytes()) == manifest["after"]:
            atomic_write(target, previous)
        raise
    print("ABOUT_SCIENCE_PATCH=published")

def rollback(raw: str):
    root, target = location()
    archive = backup_path(raw, root)
    manifest = json.loads((archive / "manifest.json").read_text(encoding="utf-8"))
    previous = (archive / "before.html").read_bytes()
    assert digest(previous) == manifest["before"]
    assert digest(target.read_bytes()) == manifest["after"], "Concurrent edit: refusing rollback"
    atomic_write(target, previous)
    assert digest(target.read_bytes()) == manifest["before"]
    print("ABOUT_SCIENCE_ROLLBACK=success")

def selftest():
    fixture = ('<html><head><meta name="viewport" content="width=device-width,initial-scale=1">'
               '<meta name="description" content="old"></head><body>'
               '<section id="zm-about-official-20261018"><style id="zm-owner-real-photo-style-20261018"></style>'
               '<style id="zm-about-official-theme-20261018"></style>'
               + OWNER_BEFORE + YEAR_ANCHOR + '<strong>۹۰٪</strong>'
               + '۹۰ درصد فعالیت‌های آن به تحقیقات علمی'
               + "".join(old for old, _ in REPLACEMENTS if old != OWNER_BEFORE)
               + DISCLOSURE
               + '</section><div id="zm-about-comprehensive"></div><div id="restored-earlier-corporate-content"></div></body></html>')
    revised = rewrite(fixture.encode("utf-8")).decode("utf-8")
    assert PAGE_SCHEMA["url"] in revised
    assert revised.count(TAG) == 1
    assert "۲۵ آبان ۱۳۹۸" in revised
    assert "نزدیک به ۹۰ درصد" not in revised
    print("ABOUT_SCIENCE_SELFTEST=passed")

if __name__ == "__main__":
    args_ = argparse.ArgumentParser()
    args_.add_argument("action", choices=("selftest", "publish", "verify", "rollback"))
    args_.add_argument("--backup", default="")
    args = args_.parse_args()
    if args.action == "selftest":
        selftest()
    else:
        assert args.backup
        {"publish": publish, "verify": verify, "rollback": rollback}[args.action](args.backup)
