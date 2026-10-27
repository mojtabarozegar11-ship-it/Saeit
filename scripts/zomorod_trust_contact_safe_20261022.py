#!/usr/bin/env python3
"""Atomic trust disclosures in existing /contact/; never touch finance, DB, homepage or rewrites."""
from __future__ import annotations
import argparse,hashlib,html,json,os
from pathlib import Path
CONTACT_SHA="62631e0ccd54"
REFINE_SHA="63375f7a39fc"
OLD_LAYOUT='<div class="zm-v7-content-grid"><details id="zm-trust-legal"'
NEW_LAYOUT='<div class="zm-v7-content-grid" style="grid-template-columns:repeat(auto-fit,minmax(min(100%,420px),1fr));align-items:start"><details id="zm-trust-legal"'
MARKER="zm-public-trust-sections-20261022"
CLOSE="</section></main>"
NAV='<a href="/api/health/">وضعیت سامانه ←</a></div>'
ANCHORS={"legal":"zm-trust-legal","financial-transparency":"zm-trust-financial","privacy":"zm-trust-privacy","terms":"zm-trust-terms"}
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


def sha(b): return hashlib.sha256(b).hexdigest()

def enrich(src):
    assert src.count(CLOSE)==1 and src.count(NAV)==1 and MARKER not in src
    links=''.join('<a href="#'+ANCHORS[k]+'">'+html.escape(v["heading"])+' ←</a>' for k,v in PAGES.items())
    out=src.replace(NAV,NAV[:-6]+links+'</div>',1)
    section='<section id="'+MARKER+'" aria-label="اطلاعات حقوقی مالی و حریم خصوصی"><h2>اعتبارسنجی و شفافیت شرکت</h2>'
    section+='<p class="summary">اطلاعات این بخش تنها برای بررسی آگاهانه است؛ هیچ رتبه مالی، ضمانت بانکی یا مجوز تخصصی بدون مدرک ادعا نمی‌شود.</p>'
    section+='<div class="zm-v7-content-grid" style="grid-template-columns:repeat(auto-fit,minmax(min(100%,420px),1fr));align-items:start">'
    for key,v in PAGES.items():
        section+='<details id="'+ANCHORS[key]+'" class="zm-v7-content-card">'
        section+='<summary style="cursor:pointer;color:#f1d58e;font-size:20px;font-weight:bold">'+html.escape(v["heading"])+'</summary>'
        section+='<p>'+html.escape(v["lead"])+'</p>'
        for h,detail in v["sections"]:
            section+='<h3>'+html.escape(h)+'</h3><p>'+detail+'</p>'
        section+='<p class="summary">'+html.escape(v["notice"])+'</p></details>'
    section+='</div></section>'
    out=out.replace(CLOSE,section+CLOSE,1)
    assert out.count(MARKER)==1 and '<form' not in out
    assert out.split('</head>',1)[0]==src.split('</head>',1)[0]
    assert out.split('</main>',1)[1]==src.split('</main>',1)[1]
    assert out.count('class="zm-v7-header"')==src.count('class="zm-v7-header"')==1
    assert out.count('class="zm-v7-footer"')==src.count('class="zm-v7-footer"')==1
    return out

def refine(site,backup):
    target=validated(site,backup)
    prior=target.read_bytes()
    assert sha(prior).startswith(REFINE_SHA),"Live contact has changed; stop to protect other edits."
    src=prior.decode('utf-8')
    assert src.count(OLD_LAYOUT)==1 and src.count(NEW_LAYOUT)==0
    after=src.replace(OLD_LAYOUT,NEW_LAYOUT,1).encode('utf-8')
    assert not backup.exists()
    backup.mkdir(mode=0o700,parents=True)
    (backup/'before.html').write_bytes(prior)
    (backup/'manifest.json').write_text(json.dumps({'before':sha(prior),'after':sha(after)}),encoding='utf8')
    try:
        atomic(target,after)
        verify(site,backup)
    except Exception:
        if sha(target.read_bytes())==sha(after):atomic(target,prior)
        raise
    print('TRUST_LAYOUT_REFINEMENT=applied')
    print('HEADER_FOOTER_HOME_HTACCESS_DB_TOUCHED=no')

def atomic(path,data):
    tmp=path.with_name('.'+path.name+'.trust-next')
    assert not tmp.exists() and not tmp.is_symlink()
    with tmp.open('xb') as f: f.write(data);f.flush();os.fsync(f.fileno())
    os.chmod(tmp,0o644)
    os.replace(tmp,path)

def validated(site,backup):
    assert site.is_dir() and not site.is_symlink()
    target=site/'contact/index.html'
    assert target.is_file() and not target.is_symlink()
    assert backup.is_absolute() and backup.resolve().is_relative_to(Path.home().resolve())
    assert not backup.resolve().is_relative_to(site.resolve())
    return target

def apply(site,backup):
    target=validated(site,backup)
    prior=target.read_bytes()
    assert sha(prior).startswith(CONTACT_SHA),"Contact changed since previous audit"
    changed=enrich(prior.decode('utf-8')).encode('utf-8')
    assert not backup.exists()
    backup.mkdir(mode=0o700,parents=True)
    (backup/'before.html').write_bytes(prior)
    (backup/'manifest.json').write_text(json.dumps({'before':sha(prior),'after':sha(changed)}),encoding='utf8')
    try:
        atomic(target,changed)
        verify(site,backup)
    except Exception:
        if sha(target.read_bytes())==sha(changed):atomic(target,prior)
        raise
    print('TRUST_CONTACT_PUBLICATION=applied')
    print('HOMEPAGE_HTACCESS_STORE_DB_PRIVATE_FINANCE_TOUCHED=no')

def verify(site,backup):
    target=validated(site,backup)
    manifest=json.loads((backup/'manifest.json').read_text(encoding='utf8'))
    data=target.read_bytes()
    assert sha(data)==manifest['after'] and MARKER.encode() in data
    for anchor in ANCHORS.values(): assert ('id="'+anchor+'"').encode() in data
    print('TRUST_CONTACT_FILE_VERIFIED=yes')

def rollback(site,backup):
    target=validated(site,backup)
    manifest=json.loads((backup/'manifest.json').read_text(encoding='utf8'))
    before=(backup/'before.html').read_bytes()
    assert sha(before)==manifest['before']
    assert sha(target.read_bytes())==manifest['after'],"Concurrent edit; manual review required"
    atomic(target,before)
    assert sha(target.read_bytes())==manifest['before']
    print('TRUST_CONTACT_ROLLBACK=verified')

def selftest():
    fixture=('<html><head></head><body><header class="zm-v7-header"></header>'
             '<main id="main"><section class="zm-v7-information"><div>'+NAV+
             '</section></main><footer class="zm-v7-footer"></footer></body></html>')
    changed=enrich(fixture)
    assert changed.count(MARKER)==1 and changed.count('href="#zm-trust-legal"')==1
    assert len(changed)>len(fixture)
    assert 'align-items:start' in changed and 'min(100%,420px)' in changed
    print('TRUST_CONTACT_SELFTEST=passed')

def main():
    p=argparse.ArgumentParser()
    p.add_argument('mode',choices=['selftest','apply','refine','verify','rollback'])
    p.add_argument('--site',default=str(Path.home()/'public_html'))
    p.add_argument('--backup',default='')
    a=p.parse_args()
    if a.mode=='selftest':return selftest()
    assert a.backup
    return {'apply':apply,'refine':refine,'verify':verify,'rollback':rollback}[a.mode](Path(a.site),Path(a.backup))
if __name__=='__main__':main()
