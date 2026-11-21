#!/usr/bin/env python3
"""Safely align Zomorod Melal company and research pages with owner-reported R&D focus.

Edits ONLY existing public_html/company/index.html and research/index.html.
Preserves imagery, navigation, site styles, and all existing sections.
No lab accreditation, independent certification or completed study is asserted.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from pathlib import Path

MARKERS = {
    "company": "zm-company-rd-focus-20261023",
    "research": "zm-research-rd-focus-20261023",
}
DESCRIPTIONS = {
    "company": "معرفی شرکت کشت و صنعت زمرد ملل با تمرکز ۹۰ درصدی اعلام‌شده بر تحقیقات علمی، ژنتیک و اصلاح نژاد، و ۱۰ درصد سایر حوزه‌های فعالیت؛ اطلاعات پژوهشی با معیار شواهد معتبر.",
    "research": "پژوهش و توسعه در زمرد ملل؛ سهم اعلام‌شده ۹۰ درصدی پژوهش‌های علمی و ژنتیکی از فعالیت شرکت، محورهای ژنتیک، اصلاح نژاد و علوم داده و اصول اعتبارسنجی مستقل.",
}
BLOCKS = {
    "company": """<section class="zm-page-section" id="zm-company-rd-focus-20261023" aria-labelledby="zm-company-rd-focus-title">
<div class="zm-container">
<div class="zm-section-head">
<div><span class="zm-eyebrow">SCIENTIFIC RESEARCH · COMPANY PRIORITY</span>
<h2 id="zm-company-rd-focus-title">پژوهش علمی و ژنتیکی؛ محور اصلی فعالیت شرکت</h2></div>
<p>بر پایه اطلاعات اعلام‌شده مدیرعامل، <strong>۹۰٪ فعالیت‌های شرکت کشت و صنعت زمرد ملل</strong> به تحقیقات و پژوهش‌های علمی و ژنتیکی اختصاص دارد و ۱۰٪ دیگر به سایر زمینه‌های فعالیت شرکت مربوط است. این نسبت بیانگر تعریف و اولویت فعالیت‌های مجموعه است، نه نتیجه یک حسابرسی مستقل.</p>
</div>
<div class="zm-card-grid">
<article class="zm-card"><span>01 / محور راهبردی</span><h3>ژنتیک و اصلاح نژاد</h3><p>موضوعات مطالعاتی می‌توانند ژنتیک گیاهی، دام و طیور، منابع ژنتیکی و کاربرد داده‌های ژنومی در تصمیم‌های اصلاح نژاد را دربر بگیرند. معرفی این حوزه‌ها به‌تنهایی اثبات‌کننده اجرای همه طرح‌ها یا وجود آزمایشگاه اختصاصی نیست.</p><a href="/agriculture/genetics/">آشنایی با حوزه ژنتیک ←</a></article>
<article class="zm-card"><span>02 / معیار پژوهش</span><h3>شواهد، روش و بازتولیدپذیری</h3><p>انتشار هر نتیجه واقعی باید همراه شناسه طرح، روش، مسئول متخصص، داده قابل انتشار، محدودیت‌ها و وضعیت کنترل کیفیت باشد. طرح‌های بدون شاهد معتبر، صرفاً در حد پیشنهاد یا موضوع تحقیق معرفی می‌شوند.</p><a href="/research/">روش‌شناسی پژوهش ←</a></article>
<article class="zm-card"><span>03 / شفافیت سازمانی</span><h3>۱۰٪ سایر فعالیت‌های شرکت</h3><p>در کنار مأموریت پژوهشی، شرکت در زمینه‌های مکمل کشاورزی، صنعت و زنجیره ارزش نیز فعالیت‌های تعریف‌شده دارد. وضعیت اجرایی و مجوز هر فعالیت باید مستقلاً و با مستندات معتبر احراز شود.</p><a href="/about/">معرفی و شفافیت فعالیت‌ها ←</a></article>
</div></div></section>
""",
    "research": """<section class="zm-page-section" id="zm-research-rd-focus-20261023" aria-labelledby="zm-research-rd-focus-title">
<div class="zm-container">
<div class="zm-section-head">
<div><span class="zm-eyebrow">RESEARCH IDENTITY · OWNER-REPORTED</span>
<h2 id="zm-research-rd-focus-title">تمرکز ۹۰٪ بر تحقیقات علمی و ژنتیکی</h2></div>
<p>طبق اعلام مدیرعامل شرکت کشت و صنعت زمرد ملل، <strong>۹۰٪ فعالیت‌های شرکت</strong> بر تحقیقات و پژوهش‌های علمی و ژنتیکی متمرکز است. ۱۰٪ دیگر به سایر حوزه‌های فعالیت اختصاص دارد. این تقسیم‌بندی، نسبت اعلام‌شده شرکت است و تأییدیه بیرونی یا آمار ممیزی‌شده محسوب نمی‌شود.</p>
</div>
<div class="zm-card-grid">
<article class="zm-card"><span>01 / زمینه پژوهش</span><h3>ژنتیک، ژنومیک و اصلاح نژاد</h3><p>موضوعات پژوهشی شامل بررسی تنوع ژنتیکی، روش‌های اصلاح نژاد گیاهان و جانوران و تفسیر داده‌های ژنومی است؛ هر پروژه برای ادعای نتیجه به روش، داده و بررسی تخصصی نیاز دارد.</p><a href="/agriculture/genetics/">مطالعه حوزه ژنتیک ←</a></article>
<article class="zm-card"><span>02 / پژوهش میان‌رشته‌ای</span><h3>بیوانفورماتیک و داده‌های زیستی</h3><p>تحلیل داده، مدل‌سازی و ابزارهای هوش مصنوعی زیستی می‌توانند از پژوهش پشتیبانی کنند؛ خروجی آنها باید با داده مناسب، روش معتبر و آزمون مستقل سنجیده شود.</p><a href="/research/directory/units/molecular-genetics/">واحد پژوهشی ژنتیک مولکولی ←</a></article>
<article class="zm-card"><span>03 / معیار انتشار</span><h3>گزارش پژوهش با شواهد قابل بررسی</h3><p>هر دستاورد قابل انتشار باید هدف، محدوده مطالعه، وضعیت اجرا، مسئولیت علمی، نتایج مجاز به انتشار و محدودیت‌ها را روشن کند. این صفحه ادعای تجهیزات یا نتایج تکمیل‌شده بدون سند ندارد.</p><a href="/about/">شفافیت معرفی شرکت ←</a></article>
</div></div></section>
""",
}
HEADING_ANCHORS = {
    "company": "دانش و تولید، در یک",
    "research": "دانش معتبر، با",
}
META = re.compile(r'<meta name="description" content="[^"]*">')
FIRST_SECTION = '<section class="zm-page-section">'

def digest(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()

def rewrite(kind: str, data: bytes) -> bytes:
    text = data.decode("utf-8")
    assert text.count('<main id="main">') == 1, f"main baseline missing: {kind}"
    assert HEADING_ANCHORS[kind] in text, f"heading baseline missing: {kind}"
    assert text.count(FIRST_SECTION) >= 2, f"section baseline missing: {kind}"
    assert MARKERS[kind] not in text, f"already installed: {kind}"
    assert '<meta name="viewport"' in text, f"viewport missing: {kind}"
    assert text.count('</main>') == 1, f"unexpected main: {kind}"
    assert len(META.findall(text)) == 1, f"meta baseline missing: {kind}"
    text = text.replace(FIRST_SECTION, BLOCKS[kind] + "\n" + FIRST_SECTION, 1)
    text = META.sub('<meta name="description" content="' + DESCRIPTIONS[kind] + '">', text, count=1)
    assert text.count('id="' + MARKERS[kind] + '"') == 1
    assert text.count('<main id="main">') == 1
    assert all(anchor in text for anchor in ('<section class="zm-hero">', '<section class="zm-narrative">', '<section class="zm-next">'))
    result = text.encode("utf-8")
    assert result != data
    return result

def targets() -> tuple[Path, dict[str, Path]]:
    root = Path.home() / "public_html"
    assert root.is_dir() and not root.is_symlink()
    result = {kind: root / kind / "index.html" for kind in MARKERS}
    for kind, path in result.items():
        assert path.is_file() and not path.is_symlink(), f"missing target: {kind}"
        assert path.stat().st_size > 3500, f"unexpected short page: {kind}"
    return root, result

def backup_dir(raw: str, root: Path) -> Path:
    path = Path(raw)
    assert path.is_absolute() and not path.is_symlink()
    assert path.resolve().is_relative_to(Path.home().resolve())
    assert not path.resolve().is_relative_to(root.resolve())
    return path

def atomic_write(target: Path, data: bytes):
    path = target.with_name(".index.rd-focus-20261023.next")
    assert not path.exists() and not path.is_symlink(), f"temporary path collision: {target}"
    with path.open("xb") as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())
    os.chmod(path, 0o644)
    os.replace(path, target)

def manifest_at(folder: Path) -> dict:
    return json.loads((folder / "manifest.json").read_text(encoding="utf-8"))

def verify(raw: str):
    root, files = targets()
    archive = backup_dir(raw, root)
    manifest = manifest_at(archive)
    for kind, target in files.items():
        current = target.read_bytes()
        assert digest(current) == manifest[kind]["after"], f"concurrent modification: {kind}"
        assert current.count(('id="' + MARKERS[kind] + '"').encode()) == 1
        assert DESCRIPTIONS[kind].encode() in current
    print("RD_FOCUS_VERIFY=success")
    for kind, target in files.items():
        print(f"RD_FOCUS_SHA256_{kind}={digest(target.read_bytes())}")

def publish(raw: str):
    root, files = targets()
    archive = backup_dir(raw, root)
    assert not archive.exists(), "backup path collision"
    before = {kind: target.read_bytes() for kind, target in files.items()}
    after = {kind: rewrite(kind, original) for kind, original in before.items()}
    archive.mkdir(parents=True, mode=0o700)
    manifest = {}
    for kind in files:
        (archive / f"before-{kind}.html").write_bytes(before[kind])
        manifest[kind] = {"before": digest(before[kind]), "after": digest(after[kind])}
    (archive / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    written = []
    try:
        for kind, path in files.items():
            assert digest(path.read_bytes()) == manifest[kind]["before"], f"concurrent modification: {kind}"
            atomic_write(path, after[kind])
            written.append(kind)
        verify(raw)
    except BaseException:
        for kind in reversed(written):
            if digest(files[kind].read_bytes()) == manifest[kind]["after"]:
                atomic_write(files[kind], before[kind])
        raise
    print("RD_FOCUS_PATCH=published")

def rollback(raw: str):
    root, files = targets()
    archive = backup_dir(raw, root)
    manifest = manifest_at(archive)
    originals = {kind: (archive / f"before-{kind}.html").read_bytes() for kind in files}
    for kind, target in files.items():
        assert digest(originals[kind]) == manifest[kind]["before"]
        assert digest(target.read_bytes()) == manifest[kind]["after"], f"concurrent edit; refusing rollback: {kind}"
    for kind, target in files.items():
        atomic_write(target, originals[kind])
    for kind, target in files.items():
        assert digest(target.read_bytes()) == manifest[kind]["before"]
    print("RD_FOCUS_ROLLBACK=success")

def selftest():
    for kind in MARKERS:
        fixture = ('<html lang="fa" dir="rtl"><head><meta name="viewport" content="width=device-width,initial-scale=1">'
                   '<meta name="description" content="old"></head><body><main id="main">'
                   '<section class="zm-hero"><h1>' + HEADING_ANCHORS[kind] + '</h1></section>'
                   '<section class="zm-page-section">cards</section>'
                   '<section class="zm-narrative">narrative</section>'
                   '<section class="zm-page-section">guides</section>'
                   '<section class="zm-next">end</section></main></body></html>')
        changed = rewrite(kind, fixture.encode()).decode()
        assert 'id="' + MARKERS[kind] + '"' in changed
        assert len(changed) > len(fixture)
        assert '<section class="zm-page-section">cards</section>' in changed
        assert '<section class="zm-narrative">narrative</section>' in changed
        assert '<section class="zm-next">end</section>' in changed
        assert changed.count('<meta name="description"') == 1
        try:
            rewrite(kind, changed.encode())
            raise AssertionError("expected idempotence protection")
        except AssertionError as exc:
            assert "already installed" in str(exc)
    print("RD_FOCUS_SELFTEST=passed")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("selftest", "publish", "verify", "rollback"))
    parser.add_argument("--backup", default="")
    args = parser.parse_args()
    if args.action == "selftest":
        selftest()
    else:
        assert args.backup
        {"publish": publish, "verify": verify, "rollback": rollback}[args.action](args.backup)
