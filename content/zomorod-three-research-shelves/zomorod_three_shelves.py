#!/usr/bin/env python3
"""Add three Zomorod Melal research shelves and 60 real, independent pages.

Strictly additive: original rows/cards/routes remain unchanged. Produces a
candidate homepage and a staging directory; NEVER writes to production itself.
"""
import argparse
import base64
import hashlib
import json
import re
from html import escape
from pathlib import Path

MARKER = "zm-research-three-shelves-20261018"
BASE_COUNT = 26
NEW_COUNT = 3
CARD_COUNT = 20
GROUPS = [
    ("ZM-R27", "واحدهای تخصصی", "units", "حوزه‌ها و واحدهای علمی مرتبط با تحقیقات و فناوری", """
ژنتیک مولکولی|molecular-genetics|بررسی ساختار و عملکرد ماده ژنتیکی، نشانگرهای مولکولی و رابطه ژن با صفات زیستی
ژنتیک کمی|quantitative-genetics|مطالعه وراثت‌پذیری، صفات چندژنی و عوامل ژنتیکی و محیطی
ژنومیک|genomics|بررسی داده‌های ژنومی، تنوع ژنتیکی و روابط میان اطلاعات مولکولی
اصلاح نژاد زراعی|crop-breeding|ارزیابی صفات اصلاحی در گیاهان زراعی با توجه به عملکرد و پایداری
اصلاح نژاد باغی|horticultural-breeding|مطالعه صفات گیاهان باغی، سازگاری اقلیمی و کیفیت محصول
اصلاح نژاد دام|animal-breeding|ارزیابی صفات رشد، تولید، سلامت و سازگاری در دام
ژنتیک طیور|poultry-genetics|بررسی داده‌های عملکردی و ژنتیکی جمعیت‌های طیور
ژنتیک آبزیان|aquatic-genetics|مطالعه تنوع ژنتیکی و صفات تولیدی گونه‌های آبزی
میکروبیولوژی|microbiology|مطالعه میکروارگانیسم‌ها و تعاملات زیستی در سامانه‌های مختلف
زیست‌فناوری|biotechnology|بررسی کاربردهای علمی فرایندهای زیستی در پژوهش و توسعه
بیوانفورماتیک|bioinformatics|تحلیل محاسباتی توالی‌ها، داده‌های ژنتیکی و الگوهای زیستی
آمار زیستی|biostatistics|طراحی و تحلیل آماری پژوهش‌های زیستی و ارزیابی عدم قطعیت
هوش مصنوعی پژوهشی|research-ai|کاربرد یادگیری ماشین و مدل‌های داده‌محور در پرسش‌های علمی
فیزیولوژی گیاهی|plant-physiology|مطالعه رشد، فتوسنتز و پاسخ گیاه به عوامل محیطی
علوم خاک|soil-sciences|بررسی ویژگی‌های فیزیکی و شیمیایی خاک و روابط آن با تولید
تغذیه گیاهی|plant-nutrition|مطالعه عناصر غذایی، جذب مواد و مدیریت تغذیه بر پایه داده
گیاه‌پزشکی|plant-pathology|شناخت عوامل بیماری‌زا و فرایندهای حفاظت علمی گیاه
علوم و فناوری غذا|food-science|مطالعه ترکیب، کیفیت، ایمنی و فناوری فرایندهای غذایی
غذاهای فراسودمند|functional-foods|بررسی ترکیبات زیست‌فعال و شواهد علمی ویژگی‌های عملکردی غذا
علوم آب و اقلیم|water-climate|تحلیل داده‌های محیطی، منابع آب و سازگاری سامانه‌های تولید
"""),
    ("ZM-R28", "آزمایشگاه‌ها", "laboratories", "زمینه‌های آزمایشگاهی و روش‌های سنجش و ارزیابی", """
آزمایشگاه ژنتیک مولکولی|molecular-genetics|موضوعات آزمون مولکولی، نشانگرها و کیفیت داده‌های ژنتیکی
آزمایشگاه DNA و RNA|dna-rna|اصول ارزیابی کیفیت اسیدهای نوکلئیک و ردیابی نمونه
آزمایشگاه ژنومیک|genomics|روش‌های ارزیابی داده‌های ژنومی و کنترل کیفیت تحلیل
آزمایشگاه زیست‌شناسی سلولی|cell-biology|روش‌های مطالعه ساختار و رفتار سلول در شرایط پژوهشی
آزمایشگاه میکروبیولوژی|microbiology|کنترل نمونه، اصول شناسایی و تحلیل جمعیت‌های میکروبی
آزمایشگاه میکروبیولوژی غذا|food-microbiology|ارزیابی علمی ایمنی میکروبی و کیفیت مواد غذایی
آزمایشگاه زیست‌فناوری|biotechnology|بررسی فرایندهای زیستی و روش‌های توسعه فناورانه
آزمایشگاه بیوشیمی|biochemistry|تحلیل ترکیبات و فرایندهای شیمیایی مرتبط با سامانه‌های زیستی
آزمایشگاه خاک‌شناسی|soil-analysis|سنجش ویژگی‌های خاک و کنترل کیفیت نمونه‌برداری
آزمایشگاه آب و کیفیت منابع|water-quality|شاخص‌های کیفی آب، روش نمونه‌گیری و تفسیر داده
آزمایشگاه تغذیه گیاه|plant-nutrition|ارزیابی عناصر غذایی و روابط آن‌ها با رشد و تولید
آزمایشگاه فیزیولوژی گیاه|plant-physiology|ثبت پاسخ‌های فیزیولوژیکی و کنترل متغیرهای محیطی
آزمایشگاه گیاه‌پزشکی|plant-health|مطالعات آسیب‌شناسی، تشخیص افتراقی و مستندسازی علائم
آزمایشگاه بذر|seed-quality|مطالعات ویژگی‌های بذر، جوانه‌زنی و کیفیت فیزیولوژیکی
آزمایشگاه کیفیت مواد غذایی|food-quality|شاخص‌های فیزیکی، شیمیایی و حسی کیفیت غذا
آزمایشگاه ترکیبات زیست‌فعال|bioactives|بررسی پایداری و ویژگی‌های ترکیبات زیست‌فعال
آزمایشگاه تخمیر غذایی|fermentation|مطالعه فرایندهای تخمیری و پارامترهای کنترل کیفیت
آزمایشگاه خوراک دام و طیور|feed-analysis|ارزیابی شاخص‌های تغذیه‌ای و کیفیت مواد خوراکی
آزمایشگاه آزمون مواد|materials-testing|روش‌های ارزیابی خواص فیزیکی و کاربردی مواد
آزمایشگاه کنترل کیفیت پژوهش|research-quality|اعتبارسنجی روش، مستندسازی، کالیبراسیون و ردیابی داده
"""),
    ("ZM-R29", "مراکز تحقیقات", "centers", "برنامه‌ها و حوزه‌های راهبردی پژوهش‌های چندرشته‌ای", """
مرکز تحقیقات ژنتیک|genetics|پژوهش‌های بنیادی و کاربردی در وراثت و تنوع ژنتیکی
مرکز تحقیقات ژنومیک|genomics|تفسیر داده‌های ژنومی و روش‌های تحلیل مولکولی
مرکز تحقیقات اصلاح نباتات|plant-breeding|مطالعات به‌نژادی گیاهان زراعی و باغی
مرکز تحقیقات اصلاح نژاد دام|animal-breeding|ارزیابی صفات ژنتیکی و عملکردی در جمعیت‌های دامی
مرکز تحقیقات طیور|poultry|مطالعه تولید، ژنتیک، تغذیه و محیط پرورش طیور
مرکز تحقیقات آبزیان|aquaculture|پژوهش‌های زیستی و ژنتیکی مرتبط با آبزیان
مرکز تحقیقات میکروبیولوژی|microbiology|مطالعات میکروبی، اکولوژی و فرایندهای زیستی
مرکز تحقیقات زیست‌فناوری|biotechnology|مطالعات انتقال دانش زیستی به کاربرد فناورانه
مرکز تحقیقات بیوانفورماتیک|bioinformatics|علوم داده، آمار و الگوریتم‌های تحلیل زیستی
مرکز تحقیقات هوش مصنوعی|artificial-intelligence|اعتبارسنجی مدل‌های هوشمند و کاربرد آن‌ها در پژوهش
مرکز تحقیقات علوم خاک|soil-science|مطالعه خاک، حاصلخیزی و ارتباط آن با تولید پایدار
مرکز تحقیقات منابع آب|water-resources|تحلیل مدیریت آب، کیفیت منابع و کارایی مصرف
مرکز تحقیقات اقلیم|climate|مدل‌سازی تنش‌های اقلیمی و سازگاری سامانه‌های زیستی
مرکز تحقیقات گیاه‌پزشکی|plant-protection|مطالعه آفات، بیماری‌ها و راهبردهای حفاظت گیاهی
مرکز تحقیقات فیزیولوژی|physiology|بررسی سازوکارهای رشد و پاسخ موجودات زنده به محیط
مرکز تحقیقات علوم غذایی|food-science|پژوهش ترکیبات، ایمنی و فناوری فرآوری غذا
مرکز تحقیقات غذاهای فراسودمند|functional-foods|مطالعات شواهد و پایداری ترکیبات عملکردی غذا
مرکز تحقیقات تنوع زیستی|biodiversity|حفاظت از منابع ژنتیکی و ارزیابی تنوع زیستی
مرکز تحقیقات کشاورزی پایدار|sustainable-agriculture|بررسی بهره‌وری منابع و پیامدهای محیط‌زیستی تولید
مرکز تحقیقات توسعه فناوری|technology-development|امکان‌سنجی، توسعه تجربی و انتقال مسئولانه یافته‌های پژوهشی
"""),
]

def items(raw):
    rows = []
    for line in raw.strip().splitlines():
        parts = [part.strip() for part in line.split("|")]
        if len(parts) != 3 or not all(parts):
            raise ValueError("Bad content definition")
        rows.append(tuple(parts))
    if len(rows) != CARD_COUNT or len({r[1] for r in rows}) != CARD_COUNT:
        raise ValueError("Each shelf requires 20 distinct slugs")
    return rows

def graphic(group, slug):
    """Distinct illustrations, explicitly not laboratory photographs."""
    h = int(hashlib.sha256((group + ":" + slug).encode()).hexdigest()[:12], 16)
    hue = (h % 112) + 96
    x = 80 + h % 285
    y = 70 + (h // 17) % 100
    lines = "".join(
        f'<path d="M{40 + j * 61} {190 + (h >> (j*3)) % 40} '
        f'Q{90 + j*59} {65 + (h >> (j*4)) % 55} '
        f'{128 + j*61} {193 + (h >> (j*2)) % 43}" '
        f'stroke="#eac87a" opacity=".44" fill="none" stroke-width="5"/>'
        for j in range(6)
    )
    symbol = {
        "units": '<circle cx="270" cy="165" r="70" fill="none" stroke="#f3e5a9" stroke-width="10"/>'
                 '<path d="M227 169L262 200 320 129" fill="none" stroke="#f3e5a9" stroke-width="12"/>',
        "laboratories": '<path d="M248 87V177L190 266Q187 282 207 283H354Q370 282 362 262L305 177V87" '
                        'stroke="#f3e5a9" stroke-width="12" fill="#6fa59b70"/>'
                        '<circle cx="276" cy="237" r="18" fill="#f5e39f"/>',
        "centers": '<circle cx="279" cy="162" r="65" fill="none" stroke="#f3e5a9" stroke-width="9"/>'
                   '<circle cx="279" cy="162" r="16" fill="#f3e5a9"/>'
                   '<path d="M280 72V34M280 253V291M189 162H151M369 162H407" stroke="#f3e5a9" stroke-width="9"/>',
    }[group]
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 560 320">'
           f'<defs><linearGradient id="g" x2=".8" y2="1"><stop stop-color="hsl({hue} 34% 27%)"/>'
           f'<stop offset="1" stop-color="hsl({hue+28} 41% 10%)"/></linearGradient></defs>'
           f'<rect width="560" height="320" fill="url(#g)"/>'
           f'<circle cx="{x}" cy="{y}" r="{105 + h%60}" fill="#f3d589" opacity=".13"/>'
           + lines + symbol +
           f'<circle cx="{32 + h%470}" cy="{19 + (h//11)%90}" r="{12+h%19}" fill="#f7d77d" opacity=".3"/>'
           '</svg>')
    return 'data:image/svg+xml;base64,' + base64.b64encode(svg.encode()).decode()

def page_html(group, group_title, title, slug, subject):
    path = f"/research/directory/{group}/{slug}/"
    t, s, g = escape(title), escape(subject), escape(group_title)
    canonical = "https://zomorodmelal.ir" + path
    return f'''<!doctype html>
<html lang="fa" dir="rtl"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="index,follow">
<title>{t} | {g} | زمرد ملل</title>
<meta name="description" content="{s}؛ معرفی حوزه علمی و مسیر پژوهش در زمرد ملل.">
<link rel="canonical" href="{canonical}">
<style>
:root{{--green:#102f23;--gold:#eac77a;--text:#f8edcf}}
*{{box-sizing:border-box}}body{{margin:0;background:radial-gradient(circle at 70% 0%,#244b38,var(--green) 45%);
color:var(--text);font-family:Tahoma,Arial,sans-serif;line-height:2}}
a{{color:var(--gold)}}header,main,footer{{width:min(1030px,calc(100% - 38px));margin:auto}}
header{{padding:30px 0;border-bottom:1px solid #a98e5280}}header a{{margin-left:20px;text-decoration:none}}
main{{padding:38px 0 60px}}.eyebrow{{font-size:13px;color:var(--gold);letter-spacing:.04em}}
h1{{font-size:clamp(28px,4vw,49px);color:var(--gold);line-height:1.5}}h2{{color:var(--gold)}}
p{{max-width:83ch}}.panel{{border:1px solid #b7a36b77;border-radius:21px;padding:26px;
margin:22px 0;background:#0b291eb8;box-shadow:0 12px 35px #0002}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(250px,1fr));gap:20px}}
footer{{border-top:1px solid #a98e5280;padding:22px 0 40px;color:#e2d1ac}}
</style></head><body>
<header><a href="/">زمرد ملل</a><a href="/research/">مرکز تحقیقات</a>
<a href="/company/">معرفی شرکت</a></header>
<main><div class="eyebrow">مرکز تحقیقات علمی · {g}</div>
<h1>{t}</h1>
<p>{s}.</p>
<section class="panel"><h2>موضوع پژوهش و دامنه علمی</h2>
<p>این صفحه به معرفی تخصصی {t} در چارچوب پژوهش‌های علمی، روش‌های ارزیابی و ارتباط آن
با دیگر حوزه‌های تحقیقاتی شرکت کشت و صنعت زمرد ملل اختصاص دارد. موضوع محوری این حوزه،
{s} است. دامنه هر طرح باید با مسئله پژوهشی، منابع معتبر و امکانات واقعی تعیین شود.</p></section>
<div class="grid">
<section class="panel"><h2>روش‌شناسی و کیفیت</h2><p>طراحی پرسش تحقیق، مرور منابع، انتخاب نمونه مناسب،
ثبت روش، کنترل خطا، اعتبارسنجی داده‌ها و گزارش محدودیت‌ها برای این حوزه ضروری است.
تفسیر نتایج تنها در محدوده شواهد و روش‌های آزمون‌شده معتبر خواهد بود.</p></section>
<section class="panel"><h2>پیوند میان‌رشته‌ای</h2><p>بررسی ارتباط یافته‌های {t} با ژنتیک، زیست‌فناوری،
علوم داده، کشاورزی و علوم غذایی می‌تواند زمینه تعریف طرح‌های مشترک و ارزیابی کاربرد فناوری را فراهم کند.</p></section>
</div>
<section class="panel"><h2>وضعیت فعالیت و صلاحیت</h2>
<p>این صفحه شناسنامه موضوعی یک حوزه علمی است و به‌تنهایی به معنای وجود آزمایشگاه مستقل،
تجهیزات مشخص، ارائه خدمت عمومی، مجوز تخصصی یا اعتباربخشی آزمایشگاهی نیست.
اطلاعات مربوط به امکانات و طرح‌های عملیاتی صرفاً پس از مستندسازی جداگانه اعلام می‌شود.</p>
<p><a href="/research/">بازگشت به مرکز تحقیقات ←</a></p></section>
</main><footer>شرکت کشت و صنعت زمرد ملل · پژوهش علمی، ژنتیک و توسعه فناوری</footer>
<!-- {MARKER}:page -->
</body></html>'''

def build(source, out_file, pages_root):
    if MARKER in source:
        raise ValueError("Already applied; refusing duplicate insertion")
    if "zm-v9-real-pages-unique-links-20261018" not in source:
        raise ValueError("Expected verified V9 baseline")
    found = list(re.finditer(r'(window\.ZOMOROD_ORBIT_DATA=)(\{.*?\})(;</script>)', source, re.S))
    if len(found) != 1:
        raise ValueError("Expected exactly one homepage data manifest")
    m = found[0]
    manifest = json.loads(m.group(2))
    old = manifest["rows"]
    if len(old) != BASE_COUNT or len({r["id"] for r in old}) != BASE_COUNT:
        raise ValueError("Unexpected existing row count/IDs; refuse to change")
    if [r["index"] for r in old if r["index"] <= 17] != list(range(1, 18)):
        raise ValueError("Original 17 orbital rows are not intact")
    if any(len(r["cards"]) < CARD_COUNT for r in old):
        raise ValueError("An existing row has fewer than 20 cards")
    if len(old[-2:]) != 2 or [r["title"] for r in old[-2:]] != ["شرکت، رسانه و ارتباطات", "اخبار شرکت"]:
        raise ValueError("Unexpected footer shelf order")
    if "topic.canonicalUrl||dest" not in source:
        raise ValueError("Current renderer does not support canonical card links")
    new_rows = []
    linkset = {c.get("canonicalUrl") for r in old for c in r["cards"] if c.get("canonicalUrl")}
    for rid, title, kind, description, raw in GROUPS:
        cards = []
        for i, (name, slug, summary) in enumerate(items(raw), 1):
            path = f"/research/directory/{kind}/{slug}/"
            if path in linkset:
                raise ValueError("Duplicate card URL: " + path)
            linkset.add(path)
            cards.append(dict(
                id=f"{rid}-C{i:02}", title=name, slug=slug,
                image=graphic(kind, slug), imageStatus="unique_vector_illustration",
                canonicalUrl=path, livePage=True
            ))
            dest = pages_root / kind / slug / "index.html"
            dest.parent.mkdir(parents=True, exist_ok=False)
            dest.write_text(page_html(kind, title, name, slug, summary), encoding="utf-8")
        num = int(rid[-2:])
        new_rows.append(dict(id=rid, index=num, title=title, slug=kind, icon="layers",
            target=f"orbit-{num:02}", description=description, sectorPath="/research/",
            orbital=False, cards=cards))
    insert_at = next((i + 1 for i, r in enumerate(old) if r["id"] == "ZM-R12"), None)
    if insert_at is None:
        raise ValueError("Research shelf ZM-R12 missing")
    manifest["rows"] = old[:insert_at] + new_rows + old[insert_at:]
    manifest["version"] = "homepage-three-research-shelves-20261018"
    manifest["researchDirectoryRows"] = len(new_rows)
    manifest["researchDirectoryCards"] = NEW_COUNT * CARD_COUNT
    edited = source[:m.start(2)] + json.dumps(manifest, ensure_ascii=False, separators=(",", ":")) + source[m.end(2):]
    guard = "config.rows?.length!==26 || config.rows.some(r=>r.cards?.length<20)"
    if edited.count(guard) != 1:
        raise ValueError("Unexpected JS row-count validation")
    edited = edited.replace(guard, "config.rows?.length!==29 || config.rows.some(r=>r.cards?.length<20)", 1)
    edited = edited.replace("</body>", f"<!-- {MARKER} -->\n</body>", 1)
    current = json.loads(re.search(r'window\.ZOMOROD_ORBIT_DATA=(\{.*?\});</script>', edited, re.S).group(1))["rows"]
    assert len(current) == 29
    assert [r for r in current if r["index"] <= 26] == old
    assert len([r for r in current if r["index"] > 26]) == 3
    assert sum(len(r["cards"]) for r in current) == sum(len(r["cards"]) for r in old) + 60
    assert len({c["image"] for r in new_rows for c in r["cards"]}) == 60
    assert len(list(pages_root.rglob("index.html"))) == 60
    assert edited.count(MARKER) == 1
    if out_file.exists() or not edited.strip().endswith("</html>"):
        raise ValueError("Output exists or output HTML is incomplete")
    out_file.write_text(edited, encoding="utf-8")
    print("THREE_RESEARCH_SHELVES_VALIDATED=29 rows, 60 linked cards, 60 independent pages")
    print("OLD_ROWS_AND_ALL_EXISTING_CARDS_PRESERVED=yes")

def main():
    p = argparse.ArgumentParser()
    p.add_argument("source", type=Path)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--pages-root", type=Path, required=True)
    a = p.parse_args()
    if a.pages_root.exists() or a.output.exists():
        raise ValueError("Refuse existing output/staging directory")
    a.pages_root.mkdir(parents=True)
    try:
        build(a.source.read_text(encoding="utf-8"), a.output, a.pages_root)
    except BaseException:
        # Staging only; never remove or edit production files.
        import shutil
        shutil.rmtree(a.pages_root)
        raise

if __name__ == "__main__":
    main()
