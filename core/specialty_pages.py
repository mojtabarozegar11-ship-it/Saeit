"""Evidence-led public guides for four Zomorod Melal specialty menu entries.

These are informational guides, not claims that a brokerage, restaurant,
trading desk or product inventory is operating. No database or paid API needed.
"""

from html import escape
from string import Template

from django.http import Http404, HttpResponse
from django.views.decorators.http import require_safe


PAGES = {
    "carpets": {
        "title": "فرش دستباف؛ شناخت، ارزیابی و نگهداری",
        "category": "فرش و صنایع دستی",
        "intro": "شناخت فرش اصیل از بررسی رج‌شمار و نوع گره آغاز می‌شود، اما ارزش‌گذاری حرفه‌ای تنها به این دو شاخص محدود نیست. این راهنما معیارهای فنی و اقتصادی تصمیم‌گیری را در کنار هم قرار می‌دهد.",
        "status": "این صفحه راهنمای تخصصی است؛ موجودی فرش، قیمت قطعی یا امکان خرید آنلاین در این مسیر تأیید نشده است.",
        "pillars": [
            ("شناسه و اصالت", "شناسایی منطقه بافت، نقشه، جنس تار و پود، امضای بافنده و زنجیره مالکیت؛ هر ادعا باید مستند باشد."),
            ("ساختار و کیفیت", "بررسی تراکم گره، یکنواختی بافت، سلامت چله، پرداخت سطح، ابعاد و میزان اعوجاج یا رفو."),
            ("رنگ و مواد اولیه", "تشخیص نوع پشم و ابریشم، کیفیت رنگ، ثبات رنگ و آثار شست‌وشوی نامناسب؛ نتیجه قطعی به بازبینی حضوری نیاز دارد."),
            ("ارزش اقتصادی", "مقایسه نمونه‌های هم‌رده، وضعیت نگهداری، کمیابی طرح و نقدشوندگی؛ قیمت آگهی الزاماً قیمت معامله نیست."),
        ],
        "steps": [
            ("۱. ثبت مشخصات", "ابعاد، عکس پشت و رو، نمای گره، لبه‌ها، شیرازه و سابقه تعمیرات را مستند کنید."),
            ("۲. ارزیابی فنی", "جنس، رنگ، فرسودگی، اصالت احتمالی و هزینه بازسازی را جداگانه بررسی کنید."),
            ("۳. مقایسه بازار", "فقط معاملات قابل قیاس را مبنا قرار دهید؛ برای تصمیم پرهزینه نظر کارشناس مستقل بگیرید."),
        ],
        "checks": ["آیا شناسنامه یا سابقه مالکیت قابل بررسی است؟", "آیا پوسیدگی، بیدزدگی یا رفو روی قیمت اثر گذاشته؟", "آیا عکس پشت فرش برای تشخیص ساختار موجود است؟", "آیا هزینه حمل، بیمه و نگهداری محاسبه شده است؟"],
        "question": "آیا با عکس می‌توان قیمت قطعی داد؟",
        "answer": "خیر. عکس برای غربالگری اولیه مفید است، ولی ارزیابی معتبر به مشاهده بافت، جنس، سلامت و مستندات نیاز دارد.",
        "related": (("صنعت و تولید", "/industry/"), ("دانش‌نامه", "/knowledge/")),
    },
    "real-estate": {
        "title": "املاک و مستغلات؛ امکان‌سنجی اقتصادی",
        "category": "اقتصاد و سرمایه‌گذاری ملکی",
        "intro": "تصمیم ملکی حرفه‌ای با بررسی مالکیت، کاربری و مجوزها آغاز می‌شود و با محاسبه جریان نقدی، هزینه فرصت و سناریوهای ریسک ادامه می‌یابد؛ نه صرفاً مقایسه قیمت هر متر.",
        "status": "این صفحه محتوای تحلیلی است؛ هیچ فایل ملکی، مشاوره حقوقی شخصی، نمایندگی فروش یا معامله فعال در آن اعلام نمی‌شود.",
        "pillars": [
            ("وضعیت حقوقی", "استعلام مالکیت، حدود ملک، بدهی، وثیقه، محدودیت نقل‌وانتقال و انطباق کاربری از مراجع صلاحیت‌دار."),
            ("مکان و تقاضا", "دسترسی، زیرساخت، مخاطب هدف، طرح‌های توسعه منطقه و شواهد معاملات واقعی اطراف."),
            ("محاسبه بازده", "برآورد هزینه تملک و تعمیر، مالیات و عوارض، دوره خالی‌ماندن، جریان اجاره و ارزش فروش در سناریوهای مختلف."),
            ("کنترل ریسک", "حساسیت‌سنجی نسبت به نرخ بهره، رکود، تغییر مقررات، نقدشوندگی و تأخیر ساخت."),
        ],
        "steps": [
            ("۱. تعریف هدف", "استفاده شخصی، اجاره، توسعه یا سرمایه‌گذاری را مشخص و افق زمانی تعیین کنید."),
            ("۲. راستی‌آزمایی", "اسناد و مجوزها باید توسط مراجع رسمی و متخصص دارای صلاحیت بررسی شوند."),
            ("۳. مدل مالی", "بازده خالص و نقطه سر‌به‌سر را در سناریوی محتاطانه، میانه و خوش‌بینانه محاسبه کنید."),
        ],
        "checks": ["سند، کاربری و محدودیت‌های قانونی را بررسی کرده‌اید؟", "هزینه‌های پنهان و دوره بدون درآمد لحاظ شده‌اند؟", "تخمین بازده بر معامله واقعی استوار است؟", "برنامه خروج و نقدشوندگی چگونه است؟"],
        "question": "آیا رشد قیمت آینده تضمین‌شده است؟",
        "answer": "خیر. حتی ملکی با موقعیت مناسب ممکن است کاهش ارزش، وقفه در اجاره یا محدودیت فروش داشته باشد.",
        "related": (("اقتصاد", "/economy/"), ("پژوهش", "/research/")),
    },
    "restaurant": {
        "title": "رستوران و کسب‌وکار غذا؛ مدیریت سودآوری",
        "category": "غذا، خدمات و عملیات",
        "intro": "پایداری یک کسب‌وکار غذایی به طراحی منوی قابل اجرا، کنترل بهای تمام‌شده، ایمنی مواد غذایی، برنامه نیروی انسانی و تجربه مشتری وابسته است. این صفحه چارچوب عملی ارزیابی را ارائه می‌کند.",
        "status": "این صفحه راهنمای کسب‌وکار است؛ رستوران فیزیکی فعال، منوی قابل سفارش یا رزرو میز در این نشانی تأیید نشده است.",
        "pillars": [
            ("مهندسی منو", "برای هر غذا دستور استاندارد، وزن مواد، هزینه واقعی و حاشیه مشارکت را جداگانه ثبت کنید."),
            ("تأمین و انبار", "تأمین‌کننده قابل اعتماد، کنترل تاریخ مصرف، چرخش موجودی و ردیابی ضایعات هزینه را قابل مدیریت می‌کند."),
            ("سلامت و کیفیت", "کنترل دما، آلرژن‌ها، آلودگی متقاطع، نظافت و الزامات بهداشتی محل فعالیت ضروری است."),
            ("فروش و خدمت", "سرعت خدمت، رضایت مشتری، سفارش تکراری، هزینه جذب مشتری و ظرفیت آشپزخانه را همزمان بسنجید."),
        ],
        "steps": [
            ("۱. اندازه‌گیری تقاضا", "مشتری هدف، زمان‌های اوج، سبد متوسط و ظرفیت پاسخ‌گویی را تعریف کنید."),
            ("۲. محاسبه هزینه", "مواد، نیروی کار، اجاره، انرژی، بسته‌بندی، ضایعات و کارمزدهای فروش را جمع کنید."),
            ("۳. کنترل عملیات", "چک‌لیست ایمنی، کیفیت ثابت، موجودی روزانه و سنجش بازخورد را اجرا کنید."),
        ],
        "checks": ["قیمت هر غذا با دستور واقعی محاسبه شده است؟", "حد ضایعات و موجودی اضطراری مشخص است؟", "آموزش آلرژن و کنترل دما وجود دارد؟", "نقطه سربه‌سر ماهانه و ظرفیت خدمت معلوم است؟"],
        "question": "آیا فروش بالا به معنی سود بالا است؟",
        "answer": "خیر. بدون کنترل بهای غذا، هزینه کارکنان، ضایعات و اجاره، فروش بیشتر هم ممکن است زیان را افزایش دهد.",
        "related": (("آموزشگاه", "/amozeshgah/"), ("اقتصاد", "/economy/")),
    },
    "signals": {
        "title": "تحلیل بازار و مدیریت ریسک معاملات",
        "category": "پژوهش بازار؛ آموزش، نه سیگنال خرید",
        "intro": "پیش از هر تصمیم معاملاتی باید منبع داده، افق زمانی، هزینه اجرا، عدم‌قطعیت و حد زیان مشخص باشد. این صفحه روش ارزیابی یک ایده معاملاتی را توضیح می‌دهد، نه دستور خرید یا فروش.",
        "status": "در این صفحه سیگنال زنده، توصیه شخصی، بازده تضمین‌شده یا ربات معامله‌گر فعال عرضه نمی‌شود. اطلاعات صرفاً آموزشی‌اند.",
        "pillars": [
            ("کیفیت داده", "زمان ثبت قیمت، منبع، فاصله خرید و فروش، نقدشوندگی و خطاهای داده را پیش از تحلیل کنترل کنید."),
            ("فرضیه قابل سنجش", "دلیل ورود، شرایط ابطال، بازه زمانی و متغیرهای موثر را پیشاپیش به صورت مکتوب مشخص کنید."),
            ("اندازه ریسک", "میزان زیان قابل تحمل، همبستگی دارایی‌ها، اهرم، کارمزد و لغزش قیمت باید در ارزیابی لحاظ شوند."),
            ("شفافیت نتیجه", "سود و زیان واقعی با کسر کارمزد، افت سرمایه، نمونه‌های ناموفق و امکان تکرارپذیری گزارش شود."),
        ],
        "steps": [
            ("۱. تعریف معیار", "داده و منطق تحلیل را ثبت کنید؛ از انتخاب گزینشی نمونه‌های موفق بپرهیزید."),
            ("۲. اعتبارسنجی مستقل", "شرایط بازار متفاوت و هزینه‌های اجرا را در ارزیابی در نظر بگیرید."),
            ("۳. تصمیم آگاهانه", "هر تصمیم مالی به مسئولیت فرد و در صورت لزوم مشاوره متخصص دارای مجوز است."),
        ],
        "checks": ["منبع داده و زمان آن مشخص است؟", "هزینه اجرا و لغزش قیمت لحاظ شده؟", "حد ریسک و امکان زیان کامل روشن است؟", "ادعای عملکرد پشتوانه حسابرسی‌پذیر دارد؟"],
        "question": "آیا این صفحه سیگنال خرید یا فروش می‌دهد؟",
        "answer": "خیر. تا زمانی که سرویس مستقلی با سوابق قابل راستی‌آزمایی و مجوزهای لازم وجود نداشته باشد، هیچ خروجی معاملاتی زنده ارائه نمی‌شود.",
        "related": (("گزارش‌های اقتصادی", "/economy/"), ("دانش‌نامه", "/knowledge/")),
    },
}


DOCUMENT = Template('''<!doctype html>
<html lang="fa" dir="rtl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>$title | شرکت کشت و صنعت زمرد ملل</title>
<meta name="description" content="$description"><link rel="canonical" href="$canonical">
<meta property="og:title" content="$title"><meta property="og:description" content="$description">
<meta property="og:type" content="article"><meta property="og:url" content="$canonical">
<meta name="theme-color" content="#123b36">
<style>
:root{color-scheme:light;--ink:#17322e;--muted:#586e68;--jade:#0d7261;--line:#d8e6df;--cream:#f5f8f4}
*{box-sizing:border-box}html{scroll-behavior:smooth}body{margin:0;font-family:Tahoma,"Noto Sans Arabic",sans-serif;background:var(--cream);color:var(--ink);line-height:1.85}
a{color:inherit}a:focus-visible{outline:3px solid #efb94c;outline-offset:3px}header{background:#123b36;color:#fff}
.wrap{width:min(1080px,calc(100% - 36px));margin:auto}.top{display:flex;gap:24px;justify-content:space-between;align-items:center;min-height:75px}
.brand{font-weight:800;text-decoration:none;font-size:18px}.nav{display:flex;flex-wrap:wrap;gap:14px;font-size:13px}.nav a{text-decoration:none;color:#d8ebe5}
.hero{padding:56px 0 58px;background:linear-gradient(140deg,#123b36,#086957);color:white}.eyebrow{font-size:12px;letter-spacing:.07em;color:#bce1d6}
h1{font-size:clamp(29px,5vw,48px);line-height:1.4;margin:14px 0 18px}h2{font-size:26px;line-height:1.5;margin:0 0 16px}h3{font-size:18px;margin:0 0 8px}.intro{max-width:850px;font-size:16px;color:#e1f5ee}
.notice{margin-top:26px;padding:16px 19px;background:#e4f4eb;border-right:5px solid #0e8a6c;border-radius:9px;color:#154a3d;font-size:14px}
main{padding-bottom:70px}.section{padding-top:56px}.section p{color:var(--muted)}.grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:17px}
.card{background:#fff;padding:22px;border:1px solid var(--line);border-radius:15px;box-shadow:0 7px 22px #123b3608}.card p{margin:0;font-size:14px}
.steps{display:grid;gap:14px}.step{border-right:4px solid var(--jade)}.checks{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px;list-style:none;margin:0;padding:0}
.checks li{background:#fff;padding:13px 16px;border-radius:10px;border:1px solid var(--line)}.checks li:before{content:"✓";color:#0d8266;font-weight:bold;margin-left:8px}
details{background:#fff;padding:18px 22px;border:1px solid var(--line);border-radius:12px}summary{cursor:pointer;font-weight:700}details p{margin-bottom:0}
.links{display:flex;flex-wrap:wrap;gap:13px;margin-top:22px}.btn{border-radius:100px;padding:10px 20px;text-decoration:none;font-weight:700;background:#0d7261;color:white}.btn.outline{background:white;color:#0d7261;border:1px solid #a7c9bc}
footer{background:#123b36;color:#c9e2da;padding:30px 0;font-size:13px}.footerin{display:flex;gap:15px;justify-content:space-between;flex-wrap:wrap}
@media(max-width:680px){.top{align-items:flex-start;padding:16px 0;flex-direction:column;gap:8px}.nav{gap:12px}.hero{padding:39px 0}.grid,.checks{grid-template-columns:1fr}.section{padding-top:40px}h2{font-size:23px}}
</style></head><body>
<header><div class="wrap top"><a class="brand" href="/">زمرد ملل</a><nav class="nav" aria-label="مسیرهای اصلی"><a href="/services/">خدمات</a><a href="/industry/">صنعت</a><a href="/economy/">اقتصاد</a><a href="/knowledge/">دانش</a><a href="/company/">شرکت</a></nav></div></header>
<div class="hero"><div class="wrap"><div class="eyebrow">$category · راهنمای تخصصی</div><h1>$title</h1><p class="intro">$intro</p></div></div>
<main class="wrap"><aside class="notice" role="note">$status</aside>
<section class="section" aria-labelledby="criteria"><h2 id="criteria">چه چیزهایی باید بررسی شوند؟</h2><div class="grid">$pillars</div></section>
<section class="section" aria-labelledby="process"><h2 id="process">مسیر بررسی گام‌به‌گام</h2><div class="steps">$steps</div></section>
<section class="section" aria-labelledby="checks"><h2 id="checks">چک‌لیست تصمیم‌گیری</h2><ul class="checks">$checks</ul></section>
<section class="section" aria-labelledby="faq"><h2 id="faq">پرسش رایج</h2><details open><summary>$question</summary><p>$answer</p></details></section>
<section class="section" aria-labelledby="continue"><h2 id="continue">مطالعه و بررسی بیشتر</h2><p>مطالب این صفحه برای آشنایی با روش بررسی تدوین شده‌اند؛ برای بررسی شرایط هر پروژه باید داده‌های واقعی و مستندات مربوط به همان مورد گردآوری شود.</p><div class="links">$related<a class="btn outline" href="/company/">درباره شرکت</a></div></section>
</main><footer><div class="wrap footerin"><span>شرکت کشت و صنعت زمرد ملل · محتوای آموزشی و پژوهشی</span><span><a href="/">صفحه اصلی</a> · <a href="/research/">پژوهش</a></span></div></footer>
</body></html>''')


def _cards(items, wrapper):
    return "".join(
        '<article class="card ' + wrapper + '"><h3>' + escape(title) + '</h3><p>'
        + escape(body) + '</p></article>'
        for title, body in items
    )


@require_safe
def specialty_page(request, section):
    if request.get_host().split(":")[0].lower() not in {"zomorodmelal.ir", "www.zomorodmelal.ir"}:
        raise Http404("This guide is specific to Zomorod Melal")
    page = PAGES.get(section)
    if not page:
        raise Http404("Unknown specialty")
    canonical = "https://zomorodmelal.ir/" + section + "/"
    html = DOCUMENT.substitute(
        title=escape(page["title"]),
        description=escape(page["intro"][:155], quote=True),
        canonical=canonical,
        category=escape(page["category"]),
        intro=escape(page["intro"]),
        status=escape(page["status"]),
        pillars=_cards(page["pillars"], ""),
        steps=_cards(page["steps"], "step"),
        checks="".join("<li>" + escape(c) + "</li>" for c in page["checks"]),
        question=escape(page["question"]),
        answer=escape(page["answer"]),
        related="".join('<a class="btn" href="' + escape(url, quote=True) + '">'
                        + escape(label) + '</a>' for label, url in page["related"]),
    )
    response = HttpResponse(html, content_type="text/html; charset=utf-8")
    response["X-Content-Type-Options"] = "nosniff"
    response["Cache-Control"] = "public, max-age=180"
    return response
