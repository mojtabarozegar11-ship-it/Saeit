#!/usr/bin/env python3
"""Conservative and reversible public trust pages for the live Zomorod static site.

Only /contact/index.html and four previously absent directories are in scope.
Financial records, databases, credentials, and the 2.3 MB homepage are never read.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
import re
import shutil
from pathlib import Path

CONTACT_SHA_PREFIX = "62631e0ccd54"
LINK_ANCHOR = '<a href="/api/health/">وضعیت سامانه ←</a></div>'
PAGE_LINKS = (
    '<a href="/legal/">هویت حقوقی ←</a>'
    '<a href="/financial-transparency/">شفافیت مالی ←</a>'
    '<a href="/privacy/">حریم خصوصی ←</a>'
    '<a href="/terms/">شرایط استفاده ←</a>'
)
NAVIGATION = (
    '<div class="zm-v7-info-links">'
    '<a href="/contact/">تماس ←</a>'
    '<a href="/legal/">هویت حقوقی ←</a>'
    '<a href="/financial-transparency/">شفافیت مالی ←</a>'
    '<a href="/privacy/">حریم خصوصی ←</a>'
    '<a href="/terms/">شرایط استفاده ←</a></div>'
)
PAGES = {
    "legal": {
        "title": "هویت و اطلاعات حقوقی | زمرد ملل",
        "description": "اطلاعات معرفی و مسیرهای استعلام مستقل هویت ثبتی شرکت کشت و صنعت زمرد ملل.",
        "heading": "هویت و اطلاعات حقوقی شرکت",
        "lead": "هدف این صفحه امکان بررسی مستقل هویت طرف قرارداد است؛ انتشار اطلاعات به‌معنای گواهی رسمی وضعیت روز شرکت نیست.",
        "sections": [
            ("اطلاعات ثبتی اعلام‌شده", "نام: شرکت کشت و صنعت زمرد ملل؛ قالب حقوقی اعلامی: با مسئولیت محدود؛ شناسه ملی اعلام‌شده: 14008746024؛ شماره ثبت اعلامی: 3110. این اطلاعات از منابع عمومی گردآوری شده و وضعیت فعلی، آخرین تغییرات و صاحبان امضای مجاز هنوز با سند رسمی روز تأیید نشده‌اند."),
            ("راه استعلام رسمی", 'طرف قرارداد می‌تواند وضعیت جاری شرکت و آخرین تغییرات را از <a href="https://ilenc.ssaa.ir/" rel="noopener noreferrer">سامانه شناسه ملی اشخاص حقوقی</a> و <a href="https://www.rrk.ir/" rel="noopener noreferrer">روزنامه رسمی</a> مستقلاً بررسی کند. در صورت اختلال سامانه‌های رسمی، استعلام نهایی باید به زمان دسترسی موکول شود.'),
            ("اختیارات و قرارداد", "هیچ‌گونه حق امضا، مجوز تخصصی، گواهی استاندارد، نمایندگی انحصاری یا اعتبار بانکی صرفاً بر اساس محتوای این وب‌سایت تأیید نمی‌شود. قراردادهای تجاری پس از احراز اصالت مدارک، صاحبان امضای مجاز و شرایط معامله تنظیم خواهند شد."),
        ],
        "notice": "این صفحه، گواهی اعتبار حقوقی یا استعلام رسمی دولت نیست. برای معامله با مبلغ قابل‌توجه، آخرین آگهی رسمی و هویت امضاکنندگان جداگانه بررسی شود.",
    },
    "financial-transparency": {
        "title": "چارچوب شفافیت و اعتبار مالی | زمرد ملل",
        "description": "مرزبندی شفاف ادعاهای مالی، مستندات محرمانه و شرایط ارزیابی اعتبار تجاری زمرد ملل.",
        "heading": "شفافیت و ارزیابی اعتبار مالی",
        "lead": "شفافیت یعنی وضعیت قابل‌اثبات از ادعای بدون سند جدا شود؛ این صفحه رتبه اعتباری، ضمانت بانکی یا توان بازپرداخت را تأیید نمی‌کند.",
        "sections": [
            ("وضعیت انتشار عمومی", "صورت‌های مالی حسابرسی‌شده، گواهی تمکن بانکی، رتبه اعتباری مستقل و ضمانت‌نامه معتبر در این صفحه منتشر نشده‌اند. نبود انتشار عمومی به‌خودی‌خود اثبات داشتن یا نداشتن اعتبار نیست."),
            ("حفاظت از اطلاعات محرمانه", "مانده حساب‌ها، تراکنش‌ها، گردش مالی، جزئیات بدهی و مطالبات، شماره حساب‌ها و قراردادهای خصوصی در سایت عمومی منتشر نمی‌شوند. هرگونه ارائه سند به طرف قرارداد منوط به احراز هویت، ضرورت تجاری، توافق محرمانگی و تصویب مدیریت خواهد بود."),
            ("اعتبار خرید و همکاری", "درخواست خرید اعتباری، از جمله بازپرداخت مدت‌دار، صرفاً پیشنهاد قابل‌مذاکره است و به‌منزله تصویب تأمین اعتبار، تعهد پرداخت، تضمین بانکی یا وجود خط اعتباری فعال نیست. مهلت، تضامین و اعتبارسنجی در قرارداد مستقل تعیین می‌شود."),
            ("مراحل ارزیابی طرف مقابل", "برای قراردادهای مهم: استعلام هویت حقوقی روز، بررسی اختیارات امضا، ارزیابی مالی با رضایت طرفین، اخذ مستندات متناسب با ریسک، تعیین تضامین و ثبت مسئول پاسخگویی انجام می‌شود."),
        ],
        "notice": "این صفحه گزارش حسابرسی، رتبه اعتباری رسمی یا توصیه برای اعطای اعتبار نیست.",
    },
    "privacy": {
        "title": "حریم خصوصی و حفاظت اطلاعات | زمرد ملل",
        "description": "اطلاع‌رسانی عمومی درباره حفظ اطلاعات ارتباطی و مرزبندی داده‌های محرمانه در وب‌سایت زمرد ملل.",
        "heading": "حریم خصوصی و حفاظت اطلاعات",
        "lead": "برای برقراری ارتباط و ارائه خدمات، تنها اطلاعات ضروری باید درخواست و متناسب با هدف همکاری استفاده شود.",
        "sections": [
            ("اطلاعات ارتباطی", "هنگام تماس مستقیم، اطلاعاتی که خودتان برای پاسخگویی یا بررسی درخواست ارائه می‌کنید ممکن است در گردش کار اداری رسیدگی شود. از ارسال کد ملی شخصی، اطلاعات کارت بانکی، رمز عبور و اسناد مالی در پیام‌های عمومی خودداری کنید."),
            ("داده‌های فنی بازدید", "سامانه میزبانی ممکن است برای امنیت و عیب‌یابی، گزارش‌های فنی مانند زمان درخواست، نشانی IP و اطلاعات مرورگر را پردازش کند. این متن ادعای نبود همه ابزارهای تحلیل یا تعیین مدت نگهداری مشخص نیست؛ این موارد نیازمند ممیزی زیرساخت هستند."),
            ("اشتراک‌گذاری و حقوق اشخاص", "جزئیات محرمانه صرفاً برای هدف قانونی و قراردادی مربوط بررسی می‌شوند. برای طرح سؤال درباره داده‌های ارسالی، تصحیح اطلاعات یا درخواست رسیدگی به حذف داده، از راه تماس رسمی شرکت استفاده کنید؛ رسیدگی تابع مقررات و الزامات نگهداری قانونی است."),
            ("پرداخت و امنیت", "هیچ درخواست عمومی برای دریافت رمز بانکی، کلید خصوصی کیف پول یا رمز یکبارمصرف از جانب این صفحه معتبر نیست. فعال بودن واقعی هر خدمت مالی باید مستقل از ظاهر سایت آزموده شود."),
        ],
        "notice": "این متن اطلاع‌رسانی عمومی است و جایگزین بررسی حقوقی یا ممیزی تخصصی حریم خصوصی نمی‌شود.",
    },
    "terms": {
        "title": "شرایط استفاده و همکاری | زمرد ملل",
        "description": "شرایط عمومی استفاده از محتوا و چارچوب ثبت سفارش و همکاری تجاری سایت زمرد ملل.",
        "heading": "شرایط استفاده و همکاری",
        "lead": "اطلاعات علمی و معرفی خدمات برای آشنایی با فعالیت‌ها هستند و به‌تنهایی پیشنهاد الزام‌آور فروش یا قرارداد محسوب نمی‌شوند.",
        "sections": [
            ("محتوا و مسئولیت حرفه‌ای", "مطالب پژوهشی، آموزشی، کشاورزی و اقتصادی ممکن است به بازبینی علمی، شرایط اقلیمی و نظر متخصص نیاز داشته باشند. هیچ بازده، عملکرد محصول، سود تجاری یا نتیجه حقوقی بدون قرارداد مشخص تضمین نشده است."),
            ("معامله و پرداخت", "نمایش کالا یا خدمت در سایت به‌معنای امکان پرداخت، ثبت سفارش قطعی یا تحویل فوری نیست. قبل از هر خرید، فعال بودن مسیر پرداخت، مبلغ نهایی، نحوه تحویل، رسید، شرایط انصراف و پشتیبانی باید روشن و آزموده شود."),
            ("فعالیت‌های دارای مجوز", "فروش یا واردات بذر، سم، کود، دارو و مکمل دامپزشکی و سایر کالاهای دارای مقررات خاص، حسب مورد مستلزم مجوزها، ثبت و تأیید مراجع ذی‌صلاح است. نمایش حوزه فعالیت در سایت به معنی داشتن همه مجوزهای مربوط نیست."),
            ("حقوق و اختلافات", "نقل مطالب و استفاده تجاری تابع حقوق صاحبان اثر و توافق کتبی است. قرارداد اختصاصی، شرایط پرداخت، مسئولیت‌ها و سازوکار حل اختلاف را جداگانه تعیین می‌کند."),
        ],
        "notice": "تا زمانی که مسیر ثبت سفارش و تسویه واقعی آزموده نشده باشد، تأیید خرید یا پرداخت موفق نباید به مشتری اعلام شود.",
    },
}


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def render(template: str, key: str) -> str:
    page = PAGES[key]
    assert template.count('<main id="main">') == 1
    assert template.count("</main>") == 1
    assert template.count('<title>') == 1
    assert template.count('rel="canonical"') == 1
    head, after = template.split('<main id="main">', 1)
    _, tail = after.split("</main>", 1)
    body = '<main id="main"><section class="zm-v7-information">'
    body += '<p>زمرد ملل · اطلاعات عمومی و همکاری</p>'
    body += '<h1>' + html.escape(page["heading"]) + '</h1>'
    body += '<p class="lead">' + html.escape(page["lead"]) + '</p>'
    body += '<div class="zm-v7-content-grid">'
    for heading, detail in page["sections"]:
        body += '<article class="zm-v7-content-card"><h2>' + html.escape(heading) + '</h2><p>' + detail + '</p></article>'
    body += '</div><p class="summary">' + html.escape(page["notice"]) + '</p>'
    body += '<h2>پیوندهای حقوقی و ارتباطی</h2>' + NAVIGATION
    body += '</section></main>'
    head, n = re.subn(r'<title>[^<]*</title>', '<title>' + html.escape(page["title"]) + '</title>', head, count=1)
    assert n == 1
    head, n = re.subn(r'(<link rel="canonical" href=")[^"]+(")', lambda m: m[1]+'https://zomorodmelal.ir/'+key+'/'+m[2], head, count=1)
    assert n == 1
    head, n = re.subn(r'(<meta name="description" content=")[^"]*(")', lambda m: m[1]+html.escape(page["description"], quote=True)+m[2], head, count=1)
    assert n == 1
    result = head + body + tail
    assert result.count('class="zm-v7-header"') == template.count('class="zm-v7-header"')
    assert result.count('class="zm-v7-footer"') == template.count('class="zm-v7-footer"')
    assert '<form' not in result
    return result


def new_contact(raw: str) -> str:
    assert raw.count(LINK_ANCHOR) == 1, "The contact page has changed; preserve original."
    result = raw.replace(LINK_ANCHOR, LINK_ANCHOR[:-6] + PAGE_LINKS + "</div>", 1)
    assert result.count('class="zm-v7-header"') == raw.count('class="zm-v7-header"')
    assert result.count('class="zm-v7-footer"') == raw.count('class="zm-v7-footer"')
    return result


def safe_path(root: Path, rel: str, require_absent=False) -> Path:
    p = root / rel
    assert root.is_dir() and not root.is_symlink()
    assert p.resolve().is_relative_to(root.resolve())
    assert not p.is_symlink()
    if require_absent:
        assert not p.exists(), f"Protected path exists: {rel}"
    return p


def stage(site: Path, backup: Path):
    contact=safe_path(site,"contact/index.html")
    original=contact.read_bytes()
    assert digest(original).startswith(CONTACT_SHA_PREFIX), "Live contact fingerprint changed; abort."
    text=original.decode("utf-8")
    assert '<!-- zm-unified-v7-20261018 -->' in text
    assert '<meta name="viewport"' in text
    assert 'zm-official-contact-details-20261018' in text
    assert not any((site/key).exists() or (site/key).is_symlink() for key in PAGES)
    assert not backup.exists(), "Backup already exists; abort."
    for key in PAGES:
        safe_path(site,key,require_absent=True)
    rendered={key:render(text,key).encode('utf-8') for key in PAGES}
    rendered["contact"]=new_contact(text).encode('utf-8')
    backup.mkdir(mode=0o700,parents=True)
    (backup/"original-contact.html").write_bytes(original)
    (backup/"manifest.json").write_text(json.dumps({
        "original_sha256":digest(original),
        "new_sha256":{key:digest(raw) for key,raw in rendered.items()},
        "created_pages":list(PAGES),
    },sort_keys=True,indent=2),encoding='utf-8')
    (backup/"staged").mkdir(mode=0o700)
    for key,raw in rendered.items():
        (backup/"staged"/(key+".html")).write_bytes(raw)
    return rendered


def atomic_publish(path: Path, raw: bytes, work: Path):
    temp=path.with_name("."+path.name+".zm-trust-next")
    assert not temp.exists() and not temp.is_symlink()
    with temp.open("xb") as handle:
        handle.write(raw)
        handle.flush()
        os.fsync(handle.fileno())
    os.chmod(temp,0o644)
    os.replace(temp,path)


def apply(site: Path, backup: Path):
    rendered=stage(site,backup)
    created=[]
    changed_contact=False
    try:
        for key in PAGES:
            dest=site/key
            dest.mkdir(mode=0o755)
            created.append(dest)
            atomic_publish(dest/"index.html",rendered[key],backup)
        atomic_publish(site/"contact/index.html",rendered["contact"],backup)
        changed_contact=True
        verify(site,backup)
        print("TRUST_PUBLICATION=verified")
        print("CHANGED_EXISTING_FILE=contact/index.html")
        print("HOMEPAGE_TOUCHED=no")
        print("FINANCIAL_PRIVATE_FILES_TOUCHED=no")
        print("BACKUP_STORED=private")
    except Exception:
        if changed_contact:
            original=(backup/"original-contact.html").read_bytes()
            atomic_publish(site/"contact/index.html",original,backup)
        for directory in reversed(created):
            f=directory/"index.html"
            if f.exists() and f.is_file() and not f.is_symlink():
                f.unlink()
            directory.rmdir()
        raise


def verify(site: Path, backup: Path):
    manifest=json.loads((backup/"manifest.json").read_text(encoding="utf-8"))
    for key,expected in manifest["new_sha256"].items():
        rel="contact/index.html" if key=="contact" else key+"/index.html"
        raw=safe_path(site,rel).read_bytes()
        assert digest(raw)==expected,rel
        assert b'class="zm-v7-footer"' in raw
        assert b'class="zm-v7-header"' in raw
        print("TRUST_FILE_VALID",rel,len(raw))


def rollback(site: Path, backup: Path):
    manifest=json.loads((backup/"manifest.json").read_text(encoding="utf-8"))
    contact=safe_path(site,"contact/index.html")
    original=(backup/"original-contact.html").read_bytes()
    assert digest(original)==manifest["original_sha256"]
    assert digest(contact.read_bytes())==manifest["new_sha256"]["contact"],"Contact modified since deployment; manual review."
    for key in PAGES:
        p=safe_path(site,key+"/index.html")
        assert digest(p.read_bytes())==manifest["new_sha256"][key],f"Page modified since deployment: {key}"
    atomic_publish(contact,original,backup)
    for key in PAGES:
        p=site/key/"index.html"
        p.unlink()
        (site/key).rmdir()
    print("TRUST_ROLLBACK=verified")


def selftest():
    fixture=('<html><head><title>تماس</title><meta name="description" content="old">'
             '<link rel="canonical" href="https://zomorodmelal.ir/contact/"></head>'
             '<body><!-- zm-unified-v7-20261018 --><header class="zm-v7-header"></header>'
             '<main id="main"><section class="zm-v7-information"><div class="zm-v7-info-links">'
             + LINK_ANCHOR + '</section></main>'
             '<section id="zm-official-contact-details-20261018"></section>'
             '<footer class="zm-v7-footer"></footer></body></html>')
    assert len(PAGES)==4
    assert new_contact(fixture).count('href="/legal/"')==1
    for key in PAGES:
        out=render(fixture,key)
        assert f'href="https://zomorodmelal.ir/{key}/"' in out
        assert 'class="zm-v7-footer"' in out
        assert PAGES[key]["heading"] in out
    print("TRUST_SELFTEST=passed")


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("mode",choices=["selftest","apply","verify","rollback"])
    parser.add_argument("--site",default=str(Path.home()/"public_html"))
    parser.add_argument("--backup",default="")
    args=parser.parse_args()
    if args.mode=="selftest":
        selftest()
        return
    assert args.backup and Path(args.backup).is_absolute(),"Explicit private backup required."
    site=Path(args.site)
    backup=Path(args.backup)
    assert backup.resolve().is_relative_to(Path.home().resolve())
    assert not backup.resolve().is_relative_to(site.resolve())
    {"apply":apply,"verify":verify,"rollback":rollback}[args.mode](site,backup)


if __name__=="__main__":
    main()
